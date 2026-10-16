"""Customer routes for LoanPulse (US-01, US-02, Phase 6 Profile & KYC)."""
import os
from datetime import date
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
    current_app,
    send_file,
)
from flask_login import current_user, login_required

from src.models import (
    db,
    User,
    LoanApplication,
    CustomerDocument,
    Notification,
    AssessmentRule,
    LoanProduct,
    ApplicationAuditLog,
    Assessment,
)
from src.routes.auth import role_required
from src.services.validation_service import (
    validate_loan_application,
    validate_application_against_product,
    validate_customer_profile,
)
from src.services.financial_service import calculate_emi
from src.services.document_service import (
    save_customer_document,
    delete_customer_document,
    can_access_document,
    submit_customer_kyc,
    ALLOWED_DOCUMENT_TYPES,
)
from src.services.workflow_service import (
    transition_application_status,
    record_application_audit,
    WorkflowError,
)
from src.services.assessment_service import assess_application

customer_bp = Blueprint("customer", __name__)


def generate_application_id() -> str:
    """Generate next sequential application ID like APP-0041."""
    apps = LoanApplication.query.with_entities(LoanApplication.application_id).all()
    max_num = 0
    for (app_id,) in apps:
        if app_id and app_id.startswith("APP-") and app_id[4:].isdigit():
            try:
                max_num = max(max_num, int(app_id[4:]))
            except ValueError:
                pass
    return f"APP-{max_num + 1:04d}"


@customer_bp.route("/customer/dashboard")
@role_required("CUSTOMER")
def dashboard():
    """Customer dashboard listing their own submitted applications and KYC status card."""
    applications = (
        LoanApplication.query.filter_by(customer_id=current_user.user_id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )

    recent_notifications = (
        Notification.query.filter_by(recipient_user_id=current_user.user_id)
        .order_by(Notification.created_at.desc(), Notification.notification_id.desc())
        .limit(5)
        .all()
    )
    unread_count = Notification.query.filter_by(
        recipient_user_id=current_user.user_id, is_read=False
    ).count()

    total_count = len(applications)
    pending_count = len([a for a in applications if a.status in ("PENDING_REVIEW", "PENDING_MANAGER_REVIEW", "DRAFT")])
    approved_count = len([a for a in applications if a.status == "APPROVED"])
    disbursed_count = len([a for a in applications if a.status == "DISBURSED" or a.disbursement_status == "DISBURSED"])

    # Phase 6: Profile & KYC metrics
    kyc_status = current_user.kyc_status or "NOT_STARTED"
    completion_pct = current_user.profile_completion_percentage
    documents_count = CustomerDocument.query.filter_by(customer_id=current_user.user_id).count()

    # Phase 7: Active loan products for customer dashboard
    active_products = LoanProduct.query.filter_by(active=True).order_by(LoanProduct.product_id.asc()).all()

    return render_template(
        "customer/dashboard.html",
        applications=applications,
        notifications=recent_notifications,
        unread_count=unread_count,
        total_count=total_count,
        pending_count=pending_count,
        approved_count=approved_count,
        disbursed_count=disbursed_count,
        kyc_status=kyc_status,
        completion_pct=completion_pct,
        documents_count=documents_count,
        active_products=active_products,
    )


@customer_bp.route("/customer/applications")
@role_required("CUSTOMER")
def applications_list():
    """List of all loan applications submitted by the customer."""
    applications = (
        LoanApplication.query.filter_by(customer_id=current_user.user_id)
        .order_by(LoanApplication.created_at.desc())
        .all()
    )
    return render_template("customer/applications.html", applications=applications)


@customer_bp.route("/customer/profile", methods=["GET", "POST"])
@role_required("CUSTOMER")
def profile():
    """US-Phase 6: Customer profile view and update."""
    if request.method == "POST":
        raw_data = request.form.to_dict()
        val_res = validate_customer_profile(raw_data)
        if not val_res.is_valid:
            flash("Please correct the errors in the profile form.", "danger")
            return render_template(
                "customer/profile.html",
                user=current_user,
                errors=val_res.errors,
                form_data=raw_data,
                completion_pct=current_user.profile_completion_percentage,
            ), 400

        cleaned = val_res.cleaned_data
        current_user.phone_number = cleaned["phone_number"]
        current_user.date_of_birth = cleaned["date_of_birth"]
        current_user.address = cleaned["address"]
        current_user.city = cleaned["city"]
        current_user.state = cleaned["state"]
        current_user.employment_type = cleaned["employment_type"]
        current_user.employer_name = cleaned["employer_name"]
        current_user.monthly_income = cleaned["monthly_income"]

        db.session.commit()
        flash("Your profile has been successfully updated.", "success")
        return redirect(url_for("customer.profile"))

    # GET request
    form_data = {
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone_number": current_user.phone_number or "",
        "date_of_birth": current_user.date_of_birth.isoformat() if current_user.date_of_birth else "",
        "address": current_user.address or "",
        "city": current_user.city or "",
        "state": current_user.state or "",
        "employment_type": current_user.employment_type or "",
        "employer_name": current_user.employer_name or "",
        "monthly_income": str(current_user.monthly_income) if current_user.monthly_income is not None else "",
    }
    return render_template(
        "customer/profile.html",
        user=current_user,
        errors={},
        form_data=form_data,
        completion_pct=current_user.profile_completion_percentage,
    )


@customer_bp.route("/customer/kyc")
@role_required("CUSTOMER")
def kyc():
    """US-Phase 6: Customer KYC status and document upload workspace."""
    documents = (
        CustomerDocument.query.filter_by(customer_id=current_user.user_id)
        .order_by(CustomerDocument.uploaded_at.desc(), CustomerDocument.document_id.desc())
        .all()
    )
    return render_template(
        "customer/kyc.html",
        user=current_user,
        kyc_status=current_user.kyc_status or "NOT_STARTED",
        documents=documents,
        document_types=ALLOWED_DOCUMENT_TYPES,
    )


@customer_bp.route("/customer/documents/upload", methods=["POST"])
@role_required("CUSTOMER")
def upload_document():
    """Upload a new or replacement KYC document."""
    file_storage = request.files.get("file")
    doc_type = request.form.get("document_type")

    if not doc_type or doc_type not in ALLOWED_DOCUMENT_TYPES:
        flash("Invalid or missing document type selected.", "danger")
        return redirect(url_for("customer.kyc"))

    if not file_storage or not file_storage.filename:
        flash("Please select a file to upload.", "danger")
        return redirect(url_for("customer.kyc"))

    upload_folder = current_app.config.get(
        "UPLOAD_FOLDER", os.path.join(current_app.root_path, "..", "uploads", "documents")
    )

    try:
        doc = save_customer_document(
            customer_id=current_user.user_id,
            document_type=doc_type,
            file_storage=file_storage,
            upload_folder=upload_folder,
        )
        flash(f"Document '{doc.original_filename}' uploaded successfully.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Failed to upload document: {str(e)}", "danger")

    return redirect(url_for("customer.kyc"))


@customer_bp.route("/customer/documents/<int:document_id>/download")
@login_required
def download_document(document_id):
    """Securely download an uploaded document with strict access control."""
    doc = db.session.get(CustomerDocument, document_id)
    if not doc:
        abort(404)

    if not can_access_document(current_user, doc):
        abort(403)

    if not os.path.exists(doc.file_path):
        flash("Document file not found on disk.", "danger")
        abort(404)

    return send_file(
        doc.file_path,
        as_attachment=True,
        download_name=doc.original_filename,
        mimetype=doc.mime_type,
    )


@customer_bp.route("/customer/documents/<int:document_id>/delete", methods=["POST"])
@role_required("CUSTOMER")
def delete_document(document_id):
    """Delete an uploaded document if not verified."""
    doc = db.session.get(CustomerDocument, document_id)
    if not doc or doc.customer_id != current_user.user_id:
        abort(404)

    if doc.verification_status == "VERIFIED":
        flash("Cannot delete an already verified document.", "warning")
        return redirect(url_for("customer.kyc"))

    delete_customer_document(document_id, current_user.user_id)
    flash(f"Document '{doc.original_filename}' deleted.", "info")
    return redirect(url_for("customer.kyc"))


@customer_bp.route("/customer/kyc/submit", methods=["POST"])
@role_required("CUSTOMER")
def submit_kyc():
    """Submit uploaded documents for loan officer KYC verification."""
    success, message = submit_customer_kyc(current_user)
    if success:
        flash(message, "success")
    else:
        flash(message, "warning")
    return redirect(url_for("customer.kyc"))


@customer_bp.route("/applications/new", methods=["GET", "POST"])
@role_required("CUSTOMER")
def new_application():
    """US-01 / BR-01 / Phase 6, 7 & 8: Create, draft, preview, and submit loan application with product selection."""
    active_products = LoanProduct.query.filter_by(active=True).order_by(LoanProduct.product_id.asc()).all()

    if request.method == "POST":
        raw_data = request.get_json(silent=True) or request.form.to_dict()
        action = (raw_data.get("action") or "submit").strip().lower()
        draft_id = (raw_data.get("draft_id") or raw_data.get("application_id") or "").strip()

        # ---------------------------------------------------------
        # Case A: Save / Update Draft Application
        # ---------------------------------------------------------
        if action == "draft":
            target_draft = None
            if draft_id:
                target_draft = db.session.get(LoanApplication, draft_id)
                if not target_draft:
                    if request.is_json or request.headers.get("Accept") == "application/json":
                        return jsonify({"error": f"Draft {draft_id} not found"}), 404
                    flash(f"Draft {draft_id} not found.", "danger")
                    return redirect(url_for("customer.dashboard"))
                if target_draft.customer_id != current_user.user_id:
                    abort(403)
                if target_draft.status != "DRAFT":
                    flash(f"Application {draft_id} is not in draft status.", "warning")
                    return redirect(url_for("customer.application_status", application_id=draft_id))

            is_new_draft = target_draft is None
            app_id = target_draft.application_id if target_draft else generate_application_id()

            # Parse draft fields with graceful fallbacks
            applicant_name = (raw_data.get("applicant_name") or current_user.full_name or "Draft Applicant").strip()
            try:
                monthly_income = float(raw_data.get("monthly_income") or current_user.monthly_income or 30000.0)
            except (ValueError, TypeError):
                monthly_income = float(current_user.monthly_income or 30000.0)

            try:
                requested_amount = float(raw_data.get("requested_amount") or raw_data.get("loan_amount") or 100000.0)
            except (ValueError, TypeError):
                requested_amount = 100000.0

            try:
                term_months = int(raw_data.get("term_months") or 24)
            except (ValueError, TypeError):
                term_months = 24

            prod_id_raw = raw_data.get("product_id")
            selected_product = None
            if prod_id_raw:
                try:
                    selected_product = db.session.get(LoanProduct, int(prod_id_raw))
                except (ValueError, TypeError):
                    selected_product = None
            if not selected_product and active_products:
                selected_product = active_products[0]

            applied_rate = float(selected_product.annual_interest_rate) if selected_product else 11.5
            try:
                emi_res = calculate_emi(requested_amount, applied_rate, term_months)
                est_emi = emi_res["monthly_emi"]
            except Exception:
                est_emi = round(requested_amount / term_months, 2) if term_months > 0 else 0.0

            try:
                ob_val = float(raw_data.get("existing_obligations") or 0.0)
            except (ValueError, TypeError):
                ob_val = 0.0

            if is_new_draft:
                target_draft = LoanApplication(
                    application_id=app_id,
                    customer_id=current_user.user_id,
                    applicant_name=applicant_name,
                    monthly_income=monthly_income,
                    requested_amount=requested_amount,
                    term_months=term_months,
                    status="DRAFT",
                    approved_amount=None,
                    disbursement_status="NOT_APPLICABLE",
                    disbursement_date=None,
                    created_at=date.today(),
                    updated_at=date.today(),
                    loan_purpose=raw_data.get("loan_purpose", "PERSONAL"),
                    loan_purpose_other=raw_data.get("loan_purpose_other"),
                    employment_type=raw_data.get("employment_type") or current_user.employment_type or "SALARIED",
                    employer_name=raw_data.get("employer_name") or current_user.employer_name,
                    existing_obligations=ob_val,
                    preferred_repayment_date=raw_data.get("preferred_repayment_date", "5"),
                    product_id=selected_product.product_id if selected_product else None,
                    applied_interest_rate=applied_rate,
                    estimated_monthly_emi=est_emi,
                )
                db.session.add(target_draft)
                db.session.commit()
                record_application_audit(
                    target_draft,
                    current_user,
                    action="CREATED_DRAFT",
                    from_status="NEW",
                    to_status="DRAFT",
                    notes="Application draft saved by borrower.",
                )
            else:
                target_draft.applicant_name = applicant_name
                target_draft.monthly_income = monthly_income
                target_draft.requested_amount = requested_amount
                target_draft.term_months = term_months
                target_draft.loan_purpose = raw_data.get("loan_purpose", "PERSONAL")
                target_draft.loan_purpose_other = raw_data.get("loan_purpose_other")
                target_draft.employment_type = raw_data.get("employment_type") or current_user.employment_type or "SALARIED"
                target_draft.employer_name = raw_data.get("employer_name") or current_user.employer_name
                target_draft.existing_obligations = ob_val
                target_draft.preferred_repayment_date = raw_data.get("preferred_repayment_date", "5")
                target_draft.product_id = selected_product.product_id if selected_product else None
                target_draft.applied_interest_rate = applied_rate
                target_draft.estimated_monthly_emi = est_emi
                target_draft.updated_at = date.today()
                db.session.commit()
                record_application_audit(
                    target_draft,
                    current_user,
                    action="DRAFT_UPDATED",
                    from_status="DRAFT",
                    to_status="DRAFT",
                    notes="Application draft updated by borrower.",
                )

            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({
                    "message": "Draft application saved successfully",
                    "application_id": target_draft.application_id,
                    "status": "DRAFT",
                    "applicant_name": target_draft.applicant_name,
                    "requested_amount": target_draft.requested_amount,
                    "term_months": target_draft.term_months,
                    "product_id": target_draft.product_id,
                }), 201

            flash(f"Draft application {target_draft.application_id} saved successfully.", "info")
            return redirect(url_for("customer.dashboard"))

        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # Case B: Full Validation & Submission / Preview
        # ---------------------------------------------------------
        is_api_request = request.is_json or request.headers.get("Accept") == "application/json"
        validation_result = validate_loan_application(raw_data, require_product_id=is_api_request)

        product = None
        applied_interest_rate = None
        estimated_monthly_emi = None
        emi_info = None

        cleaned = validation_result.cleaned_data if validation_result.is_valid else {}

        # Validate product selection strictly for full submission / preview
        product_id = raw_data.get("product_id") or cleaned.get("product_id")
        if not product_id or str(product_id).strip() == "":
            if is_api_request:
                validation_result.is_valid = False
                validation_result.errors["product_id"] = "A valid loan product must be selected."
            else:
                default_prod = LoanProduct.query.filter_by(active=True).order_by(LoanProduct.product_id.asc()).first()
                if default_prod:
                    product = default_prod
                    product_id = default_prod.product_id
                else:
                    validation_result.is_valid = False
                    validation_result.errors["product_id"] = "No active loan product available."

        if product_id and not product:
            try:
                pid = int(str(product_id).strip())
                product = db.session.get(LoanProduct, pid)
                if not product:
                    validation_result.is_valid = False
                    validation_result.errors["product_id"] = f"Loan product with ID {pid} does not exist."
                elif not product.active:
                    validation_result.is_valid = False
                    validation_result.errors["product_id"] = "Selected loan product is currently inactive."
            except (ValueError, TypeError):
                validation_result.is_valid = False
                validation_result.errors["product_id"] = "Product ID must be a valid integer."

        if product and validation_result.is_valid:
            # Enforce server-side product limits on amount and tenure
            product_errors = validate_application_against_product(cleaned, product)
            if product_errors:
                validation_result.is_valid = False
                validation_result.errors.update(product_errors)
            else:
                applied_interest_rate = float(product.annual_interest_rate)
                try:
                    emi_info = calculate_emi(cleaned["requested_amount"], product.annual_interest_rate, cleaned["term_months"])
                    estimated_monthly_emi = emi_info["monthly_emi"]
                except Exception:
                    estimated_monthly_emi = round(cleaned["requested_amount"] / cleaned["term_months"], 2)

        if not validation_result.is_valid:
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({
                    "error": "Validation failed",
                    "errors": validation_result.errors,
                }), 400

            flash("Application submission failed: please correct the highlighted fields.", "danger")
            return render_template(
                "customer/apply.html",
                errors=validation_result.errors,
                form_data=raw_data,
                active_products=active_products,
                draft_id=draft_id,
            ), 400

        cleaned = validation_result.cleaned_data

        # If user clicked "Review / Preview Application"
        if action == "preview" or raw_data.get("preview_mode") == "1":
            return render_template(
                "customer/apply_summary.html",
                data=cleaned,
                form_data=raw_data,
                product=product,
                applied_interest_rate=applied_interest_rate,
                estimated_monthly_emi=estimated_monthly_emi,
                emi_info=emi_info,
                draft_id=draft_id,
            )

        # ---------------------------------------------------------
        # Final Commit & Deterministic Underwriting Assessment
        # ---------------------------------------------------------
        target_app = None
        if draft_id:
            target_app = db.session.get(LoanApplication, draft_id)
            if not target_app or target_app.customer_id != current_user.user_id:
                abort(403)
            if target_app.status != "DRAFT":
                flash(f"Application {draft_id} has already been submitted.", "warning")
                return redirect(url_for("customer.application_status", application_id=draft_id))

            # Update existing draft record
            target_app.applicant_name = cleaned["applicant_name"]
            target_app.monthly_income = cleaned["monthly_income"]
            target_app.requested_amount = cleaned["requested_amount"]
            target_app.term_months = cleaned["term_months"]
            target_app.loan_purpose = cleaned.get("loan_purpose", "PERSONAL")
            target_app.loan_purpose_other = cleaned.get("loan_purpose_other")
            target_app.employment_type = cleaned.get("employment_type")
            target_app.employer_name = cleaned.get("employer_name")
            target_app.existing_obligations = cleaned.get("existing_obligations", 0.0)
            target_app.preferred_repayment_date = cleaned.get("preferred_repayment_date")
            target_app.product_id = product.product_id if product else None
            target_app.applied_interest_rate = applied_interest_rate
            target_app.estimated_monthly_emi = estimated_monthly_emi
            target_app.updated_at = date.today()

            # Transition from DRAFT to PENDING_REVIEW
            transition_application_status(
                application=target_app,
                new_status="PENDING_REVIEW",
                actor=current_user,
                action="SUBMITTED",
                notes="Draft application submitted for officer review.",
            )
        else:
            app_id = generate_application_id()
            target_app = LoanApplication(
                application_id=app_id,
                customer_id=current_user.user_id,
                applicant_name=cleaned["applicant_name"],
                monthly_income=cleaned["monthly_income"],
                requested_amount=cleaned["requested_amount"],
                term_months=cleaned["term_months"],
                status="PENDING_REVIEW",
                approved_amount=None,
                disbursement_status="NOT_APPLICABLE",
                disbursement_date=None,
                created_at=date.today(),
                updated_at=date.today(),
                loan_purpose=cleaned.get("loan_purpose", "PERSONAL"),
                loan_purpose_other=cleaned.get("loan_purpose_other"),
                employment_type=cleaned.get("employment_type"),
                employer_name=cleaned.get("employer_name"),
                existing_obligations=cleaned.get("existing_obligations", 0.0),
                preferred_repayment_date=cleaned.get("preferred_repayment_date"),
                product_id=product.product_id if product else None,
                applied_interest_rate=applied_interest_rate,
                estimated_monthly_emi=estimated_monthly_emi,
            )
            db.session.add(target_app)
            db.session.commit()

            record_application_audit(
                target_app,
                current_user,
                action="SUBMITTED",
                from_status="NEW",
                to_status="PENDING_REVIEW",
                notes="New application submitted for officer review.",
            )
            from src.services.notification_service import create_status_notification
            create_status_notification(target_app, old_status=None, new_status="PENDING_REVIEW")

        # Execute deterministic underwriting engine (Phase 7 / 8 requirement)
        assessment_result_label = "PENDING_OFFICER_REVIEW"
        try:
            assessment = assess_application(target_app, product=product, save=True)
            assessment_result_label = assessment.assessment_result
            record_application_audit(
                target_app,
                current_user,
                action="ASSESSED",
                notes=f"Deterministic underwriting evaluation completed: {assessment.assessment_result} (LTI Ratio: {assessment.calculated_ratio:.2f}x, Affordability: {assessment.affordability_ratio:.2f})",
            )
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error(f"Automatic underwriting evaluation failed for {target_app.application_id}: {e}")
            try:
                record_application_audit(
                    target_app,
                    current_user,
                    action="ASSESSMENT_PENDING",
                    notes="Automated rule assessment postponed; application queued for manual loan officer review.",
                )
            except Exception as audit_err:
                current_app.logger.error(f"Fallback audit recording failed: {audit_err}")
                try:
                    db.session.rollback()
                except Exception:
                    pass

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": "Application created successfully",
                "application_id": target_app.application_id,
                "status": target_app.status,
                "applicant_name": target_app.applicant_name,
                "requested_amount": target_app.requested_amount,
                "term_months": target_app.term_months,
                "product_id": target_app.product_id,
                "applied_interest_rate": target_app.applied_interest_rate,
                "estimated_monthly_emi": target_app.estimated_monthly_emi,
                "assessment_result": assessment_result_label,
            }), 201

        flash(f"Application {target_app.application_id} submitted successfully and sent for review.", "success")
        return redirect(url_for("customer.application_status", application_id=target_app.application_id))

    # GET request: render pre-filled application form from customer profile
    default_prod_id = str(active_products[0].product_id) if active_products else ""
    default_form = {
        "applicant_name": current_user.full_name,
        "monthly_income": str(int(current_user.monthly_income)) if current_user.monthly_income else "60000",
        "requested_amount": "200000",
        "term_months": "24",
        "loan_purpose": "PERSONAL",
        "loan_purpose_other": "",
        "employment_type": current_user.employment_type or "SALARIED",
        "employer_name": current_user.employer_name or "",
        "existing_obligations": "0",
        "preferred_repayment_date": "5",
        "product_id": default_prod_id,
    }
    return render_template(
        "customer/apply.html",
        errors={},
        form_data=default_form,
        active_products=active_products,
        draft_id=None,
    )


@customer_bp.route("/applications/<application_id>/edit", methods=["GET", "POST"])
@role_required("CUSTOMER")
def edit_draft(application_id):
    """Resume and edit an existing DRAFT loan application."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        flash(f"Application {application_id} not found.", "danger")
        abort(404)

    if app_record.customer_id != current_user.user_id:
        abort(403)

    if app_record.status != "DRAFT":
        flash("Only draft applications can be edited.", "warning")
        return redirect(url_for("customer.application_status", application_id=application_id))

    active_products = LoanProduct.query.filter_by(active=True).order_by(LoanProduct.product_id.asc()).all()

    if request.method == "POST":
        # Forward form handling through new_application logic with draft_id preset
        return new_application()

    # Pre-populate form with existing draft values
    form_data = {
        "applicant_name": app_record.applicant_name or "",
        "monthly_income": str(int(app_record.monthly_income)) if app_record.monthly_income else "",
        "requested_amount": str(int(app_record.requested_amount)) if app_record.requested_amount else "",
        "term_months": str(app_record.term_months) if app_record.term_months else "",
        "loan_purpose": app_record.loan_purpose or "PERSONAL",
        "loan_purpose_other": app_record.loan_purpose_other or "",
        "employment_type": app_record.employment_type or "SALARIED",
        "employer_name": app_record.employer_name or "",
        "existing_obligations": str(int(app_record.existing_obligations or 0)),
        "preferred_repayment_date": str(app_record.preferred_repayment_date or "5"),
        "product_id": str(app_record.product_id or (active_products[0].product_id if active_products else "")),
    }

    return render_template(
        "customer/apply.html",
        errors={},
        form_data=form_data,
        active_products=active_products,
        draft_id=app_record.application_id,
    )


@customer_bp.route("/applications/<application_id>/resubmit-documents", methods=["POST"])
@role_required("CUSTOMER")
def resubmit_documents(application_id):
    """Resubmit application after uploading requested additional documents."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        abort(404)

    if app_record.customer_id != current_user.user_id:
        abort(403)

    if app_record.status != "DOCUMENTS_REQUIRED":
        msg = f"Application is currently in status '{app_record.status}' and does not require document resubmission."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": msg}), 400
        flash(msg, "warning")
        return redirect(url_for("customer.application_status", application_id=application_id))

    raw_notes = request.form.get("notes") or (request.get_json(silent=True) or {}).get("notes")
    notes = (raw_notes or "Applicant uploaded and resubmitted requested documentation.").strip()

    try:
        transition_application_status(
            application=app_record,
            new_status="UNDER_REVIEW",
            actor=current_user,
            action="DOCUMENTS_RESUBMITTED",
            notes=notes,
        )
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": "Documents resubmitted successfully. Application is back under review.",
                "application_id": app_record.application_id,
                "status": app_record.status,
            }), 200
        flash("Your documents have been resubmitted for review. A loan officer will continue evaluation.", "success")
    except WorkflowError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        flash(str(e), "danger")

    return redirect(url_for("customer.application_status", application_id=application_id))


@customer_bp.route("/applications/<application_id>/status")
@login_required
def application_status(application_id):
    """US-02 / BR-02 / TR-02: View current application status and audit history."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        flash(f"Application {application_id} not found.", "danger")
        abort(404)

    # Ownership check: Customers can only view their own applications
    if current_user.role == "CUSTOMER" and app_record.customer_id != current_user.user_id:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Forbidden: Access to another customer's record is denied"}), 403
        abort(403)

    if request.is_json or request.headers.get("Accept") == "application/json":
        customer_review_notes = (
            app_record.review_notes
            if (current_user.role != "CUSTOMER" or app_record.status == "DOCUMENTS_REQUIRED")
            else None
        )
        return jsonify({
            "application_id": app_record.application_id,
            "status": app_record.status,
            "applicant_name": app_record.applicant_name,
            "monthly_income": app_record.monthly_income,
            "requested_amount": app_record.requested_amount,
            "term_months": app_record.term_months,
            "review_notes": customer_review_notes,
            "rejection_reason": app_record.rejection_reason,
            "created_at": app_record.created_at.isoformat() if app_record.created_at else None,
            "updated_at": app_record.updated_at.isoformat() if app_record.updated_at else None,
        }), 200

    active_rule = AssessmentRule.query.filter_by(active=True).first()
    all_audit_logs = (
        ApplicationAuditLog.query.filter_by(application_id=application_id)
        .order_by(ApplicationAuditLog.created_at.asc())
        .all()
    )
    if current_user.role == "CUSTOMER":
        audit_logs = [log for log in all_audit_logs if log.action != "NOTE_ADDED"]
    else:
        audit_logs = all_audit_logs
    assessments = (
        Assessment.query.filter_by(application_id=application_id)
        .order_by(Assessment.assessment_id.desc())
        .all()
    )
    customer_docs = (
        CustomerDocument.query.filter_by(customer_id=app_record.customer_id)
        .order_by(CustomerDocument.uploaded_at.desc())
        .all()
    )

    return render_template(
        "customer/status.html",
        app=app_record,
        active_rule=active_rule,
        audit_logs=audit_logs,
        assessments=assessments,
        customer_docs=customer_docs,
    )


# ============================================================================
# Phase 7: EMI Calculator (Public and Customer)
# ============================================================================

@customer_bp.route("/calculator")
@customer_bp.route("/customer/calculator")
def emi_calculator():
    """Phase 7: Interactive Reducing-Balance Loan EMI Calculator."""
    amount_str = request.args.get("loan_amount", "200000")
    rate_str = request.args.get("interest_rate", "11.5")
    term_str = request.args.get("term_months", "24")

    calc_result = None
    error_msg = None

    try:
        calc_result = calculate_emi(amount_str, rate_str, term_str)
    except Exception as e:
        error_msg = str(e)

    if request.is_json or request.headers.get("Accept") == "application/json":
        if calc_result:
            return jsonify({"status": "ok", "calculation": calc_result}), 200
        return jsonify({"status": "error", "message": error_msg}), 400

    active_products = LoanProduct.query.filter_by(active=True).order_by(LoanProduct.product_id.asc()).all()

    return render_template(
        "calculator.html",
        loan_amount=amount_str,
        interest_rate=rate_str,
        term_months=term_str,
        calc_result=calc_result,
        error_msg=error_msg,
        active_products=active_products,
    )


@customer_bp.route("/api/calculate-emi")
def api_calculate_emi():
    """API endpoint for dynamic client-side EMI calculation."""
    amount = request.args.get("amount") or request.args.get("principal") or request.args.get("loan_amount")
    rate = request.args.get("rate") or request.args.get("interest_rate") or request.args.get("annual_interest_rate")
    term = request.args.get("term") or request.args.get("tenure") or request.args.get("term_months")

    try:
        res = calculate_emi(amount, rate, term)
        return jsonify({
            "status": "success",
            "success": True,
            "monthly_emi": res["monthly_emi"],
            "principal": res["principal"],
            "tenure_months": res["term_months"],
            "total_interest": res["total_interest"],
            "total_payable": res["total_payable"],
            "data": res,
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 400



@customer_bp.route("/applications/<application_id>")
@login_required
def application_detail(application_id):
    """Direct application lookup redirecting or rendering status view."""
    return application_status(application_id)
