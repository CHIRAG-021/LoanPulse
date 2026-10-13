"""Loan Officer routes for LoanPulse (US-03, US-04, US-06, Phase 8 Workflow)."""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user

from src.models import (
    db,
    LoanApplication,
    Assessment,
    AssessmentRule,
    User,
    CustomerDocument,
    LoanProduct,
    ApplicationAuditLog,
)
from src.routes.auth import role_required
from src.services.assessment_service import assess_application
from src.services.validation_service import ValidationError
from src.services.notification_service import create_status_notification
from src.services.disbursement_service import record_disbursement
from src.services.document_service import review_customer_kyc, can_access_document
from src.services.workflow_service import (
    transition_application_status,
    record_application_audit,
    WorkflowError,
)

officer_bp = Blueprint("officer", __name__)


@officer_bp.route("/officer/queue")
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def queue():
    """US-04 / Phase 8: Loan officer application review queue with search, filtering, and pagination."""
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    product_filter = request.args.get("product_id", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)

    # Global summary statistics using efficient SQL count aggregations (Phase 9 Performance Optimization)
    total_volume = LoanApplication.query.count()
    pending_officer_count = LoanApplication.query.filter(
        LoanApplication.status.in_(["PENDING_REVIEW", "UNDER_REVIEW", "DOCUMENTS_REQUIRED"])
    ).count()
    forwarded_manager_count = LoanApplication.query.filter_by(status="PENDING_MANAGER_REVIEW").count()
    approved_count = LoanApplication.query.filter_by(status="APPROVED").count()
    disbursed_count = LoanApplication.query.filter(
        db.or_(LoanApplication.status == "DISBURSED", LoanApplication.disbursement_status == "DISBURSED")
    ).count()

    # Build filtered query
    query = LoanApplication.query

    if q:
        query = query.filter(
            db.or_(
                LoanApplication.applicant_name.ilike(f"%{q}%"),
                LoanApplication.application_id.ilike(f"%{q}%"),
            )
        )

    if status_filter:
        query = query.filter(LoanApplication.status == status_filter)

    if product_filter:
        try:
            query = query.filter(LoanApplication.product_id == int(product_filter))
        except (ValueError, TypeError):
            pass

    query = query.order_by(
        db.case(
            (LoanApplication.status == "PENDING_REVIEW", 1),
            (LoanApplication.status == "UNDER_REVIEW", 2),
            (LoanApplication.status == "DOCUMENTS_REQUIRED", 3),
            (LoanApplication.status == "PENDING_MANAGER_REVIEW", 4),
            (LoanApplication.status == "DRAFT", 5),
            else_=6,
        ),
        LoanApplication.created_at.desc(),
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    applications = pagination.items
    active_products = LoanProduct.query.filter_by(active=True).order_by(LoanProduct.product_name.asc()).all()

    return render_template(
        "officer/queue.html",
        applications=applications,
        pagination=pagination,
        active_products=active_products,
        total_volume=total_volume,
        pending_officer_count=pending_officer_count,
        forwarded_manager_count=forwarded_manager_count,
        approved_count=approved_count,
        disbursed_count=disbursed_count,
        q=q,
        status_filter=status_filter,
        product_filter=product_filter,
    )


@officer_bp.route("/officer/applications/<application_id>")
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def review_application(application_id):
    """US-04 / BR-04 / TR-04 / Phase 8: View relevant applicant, loan, and underwriting audit details."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        flash(f"Application {application_id} not found.", "danger")
        abort(404)

    # TR-04: Expose applicant and loan fields through authenticated API endpoint
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "application_id": app_record.application_id,
            "customer_id": app_record.customer_id,
            "applicant_name": app_record.applicant_name,
            "monthly_income": app_record.monthly_income,
            "requested_amount": app_record.requested_amount,
            "term_months": app_record.term_months,
            "status": app_record.status,
            "review_notes": app_record.review_notes,
            "rejection_reason": app_record.rejection_reason,
            "created_at": app_record.created_at.isoformat() if app_record.created_at else None,
            "updated_at": app_record.updated_at.isoformat() if app_record.updated_at else None,
        }), 200

    assessments = Assessment.query.filter_by(application_id=application_id).order_by(Assessment.assessment_id.desc()).all()
    active_rule = AssessmentRule.query.filter_by(active=True).first()
    applicant_user = db.session.get(User, app_record.customer_id)
    applicant_docs = (
        CustomerDocument.query.filter_by(customer_id=app_record.customer_id).all()
        if applicant_user
        else []
    )
    audit_logs = (
        ApplicationAuditLog.query.filter_by(application_id=application_id)
        .order_by(ApplicationAuditLog.created_at.asc())
        .all()
    )

    return render_template(
        "officer/review.html",
        app=app_record,
        assessments=assessments,
        active_rule=active_rule,
        applicant_user=applicant_user,
        applicant_docs=applicant_docs,
        audit_logs=audit_logs,
    )


@officer_bp.route("/officer/applications/<application_id>/start-review", methods=["POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def start_review(application_id):
    """Transition application from PENDING_REVIEW to UNDER_REVIEW."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        abort(404)

    if app_record.status == "PENDING_REVIEW":
        try:
            transition_application_status(
                application=app_record,
                new_status="UNDER_REVIEW",
                actor=current_user,
                action="STARTED_REVIEW",
                notes="Officer commenced underwriting review.",
            )
            flash(f"Application {app_record.application_id} is now UNDER_REVIEW.", "info")
        except WorkflowError as e:
            flash(str(e), "danger")

    return redirect(url_for("officer.review_application", application_id=application_id))


@officer_bp.route("/officer/applications/<application_id>/notes", methods=["POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def add_review_notes(application_id):
    """Add officer review notes and record in the application audit log."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        abort(404)

    raw_notes = request.form.get("notes") or (request.get_json(silent=True) or {}).get("notes")
    if not raw_notes or not raw_notes.strip():
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Note text cannot be blank."}), 400
        flash("Review note cannot be blank.", "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    note_text = raw_notes.strip()
    app_record.review_notes = note_text
    app_record.updated_at = date.today()
    record_application_audit(
        app_record,
        actor=current_user,
        action="NOTE_ADDED",
        notes=note_text,
    )

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": "Review note recorded successfully",
            "application_id": app_record.application_id,
            "review_notes": app_record.review_notes,
        }), 200

    flash("Review note recorded in application audit trail.", "success")
    return redirect(url_for("officer.review_application", application_id=application_id))


@officer_bp.route("/officer/applications/<application_id>/request-documents", methods=["POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def request_documents(application_id):
    """Transition application to DOCUMENTS_REQUIRED and specify missing document requirements."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        abort(404)

    raw_notes = request.form.get("notes") or (request.get_json(silent=True) or {}).get("notes")
    note_text = (raw_notes or "Additional documentation required for underwriting verification.").strip()

    try:
        transition_application_status(
            application=app_record,
            new_status="DOCUMENTS_REQUIRED",
            actor=current_user,
            action="DOCUMENTS_REQUESTED",
            notes=note_text,
        )
    except WorkflowError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        flash(str(e), "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": "Additional documents requested",
            "application_id": app_record.application_id,
            "status": app_record.status,
            "notes": note_text,
        }), 200

    flash(f"Application {app_record.application_id} marked as DOCUMENTS_REQUIRED. Applicant notified.", "warning")
    return redirect(url_for("officer.review_application", application_id=application_id))


@officer_bp.route("/officer/applications/<application_id>/reject", methods=["POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def reject_application(application_id):
    """Reject application with mandatory documented reason."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        abort(404)

    raw_reason = request.form.get("reason") or (request.get_json(silent=True) or {}).get("reason")
    if not raw_reason or not raw_reason.strip():
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Rejection reason is required."}), 400
        flash("Rejection reason is required when rejecting an application.", "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    reason_text = raw_reason.strip()
    try:
        transition_application_status(
            application=app_record,
            new_status="REJECTED",
            actor=current_user,
            action="OFFICER_REJECTED",
            notes=reason_text,
        )
    except WorkflowError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        flash(str(e), "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": "Application rejected",
            "application_id": app_record.application_id,
            "status": app_record.status,
            "rejection_reason": app_record.rejection_reason,
        }), 200

    flash(f"Application {app_record.application_id} has been rejected.", "danger")
    return redirect(url_for("officer.queue"))


@officer_bp.route("/officer/applications/<application_id>/assess", methods=["POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def run_assessment_route(application_id):
    """US-03 / BR-03: Execute deterministic rule assessment for an application."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        abort(404)

    try:
        assessment = assess_application(app_record, save=True)
        record_application_audit(
            app_record,
            actor=current_user,
            action="ASSESSED",
            notes=f"Officer re-assessed application: {assessment.assessment_result} (Ratio: {assessment.calculated_ratio:.2f})",
        )
    except ValidationError as e:
        error_msg = f"Cannot assess application: {e.message}"
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": error_msg, "details": e.errors}), 400
        flash(error_msg, "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": "Assessment completed",
            "assessment_id": assessment.assessment_id,
            "application_id": assessment.application_id,
            "assessment_result": assessment.assessment_result,
            "calculated_ratio": assessment.calculated_ratio,
            "assessed_at": assessment.assessed_at.isoformat(),
        }), 200

    flash(
        f"Assessment completed: Result = {assessment.assessment_result} (Loan-to-income ratio: {assessment.calculated_ratio:.2f})",
        "success" if assessment.assessment_result == "ELIGIBLE" else "info",
    )
    return redirect(url_for("officer.review_application", application_id=application_id))


@officer_bp.route("/officer/applications/<application_id>/send-to-manager", methods=["POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def send_to_manager(application_id):
    """Transition application status to PENDING_MANAGER_REVIEW and notify customer."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        abort(404)

    raw_notes = request.form.get("notes") or (request.get_json(silent=True) or {}).get("notes")
    notes = (raw_notes or "Forwarded to manager for final lending approval decision.").strip()

    try:
        transition_application_status(
            application=app_record,
            new_status="PENDING_MANAGER_REVIEW",
            actor=current_user,
            action="FORWARDED_TO_MANAGER",
            notes=notes,
        )
    except WorkflowError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        flash(str(e), "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": "Application forwarded to manager decision queue",
            "application_id": app_record.application_id,
            "status": app_record.status,
        }), 200

    flash(f"Application {app_record.application_id} forwarded to manager decision queue.", "success")
    return redirect(url_for("officer.review_application", application_id=application_id))


@officer_bp.route("/officer/disbursements")
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def disbursements_view():
    """US-06 / BR-06 / TR-06: View approved loans and disbursement tracking queue."""
    approved_apps = LoanApplication.query.filter_by(status="APPROVED").order_by(LoanApplication.updated_at.desc()).all()
    return render_template("officer/disbursements.html", applications=approved_apps)


@officer_bp.route("/officer/applications/<application_id>/disburse", methods=["POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def disburse_loan(application_id):
    """US-06 / BR-06 / TR-06: Record disbursement for an approved loan."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        abort(404)

    if app_record.status != "APPROVED":
        error_msg = f"Cannot disburse application {application_id}: status is {app_record.status}, but must be APPROVED."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": error_msg}), 400
        flash(error_msg, "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    if app_record.disbursement_status == "DISBURSED":
        error_msg = f"Application {application_id} has already been disbursed."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": error_msg}), 400
        flash(error_msg, "warning")
        return redirect(url_for("officer.disbursements_view"))

    raw_date = request.form.get("disbursement_date") or (request.get_json(silent=True) or {}).get("disbursement_date")
    parsed_date = None
    if raw_date and str(raw_date).strip():
        try:
            parsed_date = date.fromisoformat(str(raw_date).strip())
        except ValueError:
            parsed_date = date.today()

    try:
        record_disbursement(app_record, disbursement_date=parsed_date)
        record_application_audit(
            app_record,
            actor=current_user,
            action="DISBURSED",
            notes=f"Funds disbursement of ₹{app_record.approved_amount or app_record.requested_amount:,.2f} recorded.",
        )
    except ValueError as e:
        error_msg = str(e)
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": error_msg}), 400
        flash(error_msg, "danger")
        return redirect(url_for("officer.review_application", application_id=application_id))

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": f"Disbursement recorded for {app_record.application_id}",
            "application_id": app_record.application_id,
            "disbursement_status": app_record.disbursement_status,
            "disbursement_date": app_record.disbursement_date.isoformat(),
        }), 200

    flash(
        f"Disbursement recorded for application {app_record.application_id} (Status: {app_record.disbursement_status}, Date: {app_record.disbursement_date}).",
        "success",
    )
    return redirect(url_for("officer.disbursements_view"))


@officer_bp.route("/officer/kyc")
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def kyc_queue():
    """US-Phase 6: Loan officer KYC review workspace and customer queue."""
    customers = (
        User.query.filter_by(role="CUSTOMER")
        .order_by(
            db.case(
                (User.kyc_status == "PENDING", 1),
                (User.kyc_status == "REJECTED", 2),
                (User.kyc_status == "VERIFIED", 3),
                else_=4,
            ),
            User.user_id.desc(),
        )
        .all()
    )

    total_customers = len(customers)
    pending_kyc_count = len([c for c in customers if c.kyc_status == "PENDING"])
    verified_kyc_count = len([c for c in customers if c.kyc_status == "VERIFIED"])
    rejected_kyc_count = len([c for c in customers if c.kyc_status == "REJECTED"])

    return render_template(
        "officer/kyc_queue.html",
        customers=customers,
        total_customers=total_customers,
        pending_kyc_count=pending_kyc_count,
        verified_kyc_count=verified_kyc_count,
        rejected_kyc_count=rejected_kyc_count,
    )


@officer_bp.route("/officer/kyc/<int:customer_id>", methods=["GET", "POST"])
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def kyc_review(customer_id):
    """US-Phase 6: Loan officer KYC review and decision on documents."""
    customer = db.session.get(User, customer_id)
    if not customer or customer.role != "CUSTOMER":
        flash("Customer not found.", "danger")
        abort(404)

    if request.method == "POST":
        action = request.form.get("action", "").upper()
        rejection_reason = request.form.get("rejection_reason")

        success, message = review_customer_kyc(
            customer=customer,
            officer=current_user,
            action=action,
            rejection_reason=rejection_reason,
        )

        if success:
            flash(message, "success")
            return redirect(url_for("officer.kyc_queue"))
        else:
            flash(message, "danger")

    documents = (
        CustomerDocument.query.filter_by(customer_id=customer_id)
        .order_by(CustomerDocument.uploaded_at.desc(), CustomerDocument.document_id.desc())
        .all()
    )

    return render_template(
        "officer/kyc_review.html",
        customer=customer,
        documents=documents,
    )


@officer_bp.route("/officer/loan-products")
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def loan_products_view():
    """Read-only view of active loan products for loan officers."""
    products = LoanProduct.query.filter_by(active=True).order_by(LoanProduct.product_id.asc()).all()
    return render_template("officer/products.html", products=products)
