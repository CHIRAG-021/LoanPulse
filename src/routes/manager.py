"""Loan Manager routes for LoanPulse (US-05, BR-05, TR-05)."""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user

from src.models import db, LoanApplication, Assessment, LoanProduct, ApplicationAuditLog
from src.routes.auth import role_required
from src.services.validation_service import validate_loan_product
from src.services.workflow_service import transition_application_status, WorkflowError

manager_bp = Blueprint("manager", __name__)


@manager_bp.route("/manager/queue")
@role_required("LOAN_MANAGER")
def queue():
    """US-05 / BR-05 / TR-05: Identify applications requiring manager decision."""
    pending_apps = LoanApplication.query.filter_by(status="PENDING_MANAGER_REVIEW").order_by(LoanApplication.updated_at.desc()).all()

    # TR-05: API query returning applications whose status is PENDING_MANAGER_REVIEW
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "count": len(pending_apps),
            "applications": [
                {
                    "application_id": app.application_id,
                    "customer_id": app.customer_id,
                    "applicant_name": app.applicant_name,
                    "monthly_income": app.monthly_income,
                    "requested_amount": app.requested_amount,
                    "term_months": app.term_months,
                    "status": app.status,
                    "created_at": app.created_at.isoformat() if app.created_at else None,
                    "updated_at": app.updated_at.isoformat() if app.updated_at else None,
                }
                for app in pending_apps
            ]
        }), 200

    # Summary statistics for manager report dashboard (matching wireframe)
    pending_count = len(pending_apps)
    approved_count = LoanApplication.query.filter_by(status="APPROVED").count()
    rejected_count = LoanApplication.query.filter_by(status="REJECTED").count()
    disbursed_count = LoanApplication.query.filter(
        db.or_(LoanApplication.status == "DISBURSED", LoanApplication.disbursement_status == "DISBURSED")
    ).count()
    active_products_count = LoanProduct.query.filter_by(active=True).count()

    return render_template(
        "manager/queue.html",
        applications=pending_apps,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        disbursed_count=disbursed_count,
        active_products_count=active_products_count,
    )


@manager_bp.route("/manager/applications/<application_id>")
@role_required("LOAN_MANAGER")
def review_application(application_id):
    """US-05 / BR-05: View application details and rule assessment for executive lending decision."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        flash(f"Application {application_id} not found.", "danger")
        abort(404)

    assessments = Assessment.query.filter_by(application_id=application_id).order_by(Assessment.assessment_id.desc()).all()
    from src.models import AssessmentRule, User
    active_rule = AssessmentRule.query.filter_by(active=True).first()
    customer_user = db.session.get(User, app_record.customer_id)
    audit_logs = (
        ApplicationAuditLog.query.filter_by(application_id=application_id)
        .order_by(ApplicationAuditLog.created_at.asc())
        .all()
    )

    return render_template(
        "manager/review.html",
        app=app_record,
        assessments=assessments,
        active_rule=active_rule,
        customer_user=customer_user,
        audit_logs=audit_logs,
    )


@manager_bp.route("/manager/applications/<application_id>/decision", methods=["POST"])
@role_required("LOAN_MANAGER")
def record_decision(application_id):
    """Approve or reject a loan application in the manager queue."""
    app_record = db.session.get(LoanApplication, application_id)
    if not app_record:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Application {application_id} not found"}), 404
        flash(f"Application {application_id} not found.", "danger")
        abort(404)

    raw_decision = request.form.get("decision") or (request.get_json(silent=True) or {}).get("decision")
    if not raw_decision or raw_decision.upper() not in ("APPROVE", "REJECT"):
        error_msg = "Decision must be either 'APPROVE' or 'REJECT'."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": error_msg}), 400
        flash(error_msg, "danger")
        return redirect(url_for("manager.queue"))

    decision = raw_decision.upper()
    notes = request.form.get("notes") or (request.get_json(silent=True) or {}).get("notes") or request.form.get("reason")
    try:
        if decision == "APPROVE":
            transition_application_status(
                application=app_record,
                new_status="APPROVED",
                actor=current_user,
                action="MANAGER_APPROVED",
                notes=notes or "Manager executive approval granted.",
            )
            flash_msg = f"Application {app_record.application_id} has been APPROVED."
        else:
            transition_application_status(
                application=app_record,
                new_status="REJECTED",
                actor=current_user,
                action="MANAGER_REJECTED",
                notes=notes or "Application rejected by credit manager.",
            )
            flash_msg = f"Application {app_record.application_id} has been REJECTED."
    except WorkflowError as e:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": str(e)}), 400
        flash(str(e), "danger")
        return redirect(url_for("manager.queue"))

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": flash_msg,
            "application_id": app_record.application_id,
            "status": app_record.status,
            "approved_amount": app_record.approved_amount,
            "disbursement_status": app_record.disbursement_status,
        }), 200

    flash(flash_msg, "success" if decision == "APPROVE" else "info")
    return redirect(url_for("manager.queue"))


# ============================================================================
# Phase 7: Configurable Loan Products Management
# ============================================================================

@manager_bp.route("/manager/loan-products")
@role_required("LOAN_MANAGER")
def loan_products_list():
    """List all configurable loan products in the system."""
    products = LoanProduct.query.order_by(LoanProduct.product_id.asc()).all()
    total_products = len(products)
    active_count = sum(1 for p in products if p.active)
    inactive_count = total_products - active_count

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "total_products": total_products,
            "active_count": active_count,
            "products": [p.to_dict() for p in products],
        }), 200

    return render_template(
        "manager/products.html",
        products=products,
        total_products=total_products,
        active_count=active_count,
        inactive_count=inactive_count,
    )


@manager_bp.route("/manager/loan-products/new", methods=["GET", "POST"])
@role_required("LOAN_MANAGER")
def create_loan_product():
    """Create a new loan product with server-side validation."""
    if request.method == "POST":
        raw_data = request.get_json(silent=True) or request.form.to_dict()
        val_res = validate_loan_product(raw_data)

        # Check uniqueness of product_code
        if val_res.is_valid:
            existing = LoanProduct.query.filter_by(product_code=val_res.cleaned_data["product_code"]).first()
            if existing:
                val_res.is_valid = False
                val_res.errors["product_code"] = f"Product code '{val_res.cleaned_data['product_code']}' is already in use."

        if not val_res.is_valid:
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": "Validation failed", "errors": val_res.errors}), 400
            flash("Please correct the errors on the loan product form.", "danger")
            return render_template(
                "manager/product_form.html",
                product=None,
                errors=val_res.errors,
                form_data=raw_data,
                is_edit=False,
            ), 400

        cleaned = val_res.cleaned_data
        new_prod = LoanProduct(
            product_name=cleaned["product_name"],
            product_code=cleaned["product_code"],
            description=cleaned["description"],
            min_amount=cleaned["min_amount"],
            max_amount=cleaned["max_amount"],
            min_term_months=cleaned["min_term_months"],
            max_term_months=cleaned["max_term_months"],
            annual_interest_rate=cleaned["annual_interest_rate"],
            min_monthly_income=cleaned["min_monthly_income"],
            max_loan_to_income_ratio=cleaned["max_loan_to_income_ratio"],
            active=cleaned["active"],
            created_at=date.today(),
            updated_at=date.today(),
        )
        db.session.add(new_prod)
        db.session.commit()

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": f"Loan product '{new_prod.product_name}' created successfully.",
                "product": new_prod.to_dict(),
            }), 201

        flash(f"Loan product '{new_prod.product_name}' created successfully.", "success")
        return redirect(url_for("manager.loan_products_list"))

    # GET request
    return render_template(
        "manager/product_form.html",
        product=None,
        errors={},
        form_data={},
        is_edit=False,
    )


@manager_bp.route("/manager/loan-products/<int:product_id>/edit", methods=["GET", "POST"])
@role_required("LOAN_MANAGER")
def edit_loan_product(product_id: int):
    """Edit an existing loan product with server-side validation."""
    prod = db.session.get(LoanProduct, product_id)
    if not prod:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Loan product {product_id} not found."}), 404
        flash(f"Loan product #{product_id} not found.", "danger")
        abort(404)

    if request.method == "POST":
        raw_data = request.get_json(silent=True) or request.form.to_dict()
        val_res = validate_loan_product(raw_data)

        # Check uniqueness of product_code if modified
        if val_res.is_valid:
            existing = LoanProduct.query.filter(
                LoanProduct.product_code == val_res.cleaned_data["product_code"],
                LoanProduct.product_id != product_id
            ).first()
            if existing:
                val_res.is_valid = False
                val_res.errors["product_code"] = f"Product code '{val_res.cleaned_data['product_code']}' is already in use by another product."

        if not val_res.is_valid:
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": "Validation failed", "errors": val_res.errors}), 400
            flash("Please correct the errors on the loan product form.", "danger")
            return render_template(
                "manager/product_form.html",
                product=prod,
                errors=val_res.errors,
                form_data=raw_data,
                is_edit=True,
            ), 400

        cleaned = val_res.cleaned_data
        prod.product_name = cleaned["product_name"]
        prod.product_code = cleaned["product_code"]
        prod.description = cleaned["description"]
        prod.min_amount = cleaned["min_amount"]
        prod.max_amount = cleaned["max_amount"]
        prod.min_term_months = cleaned["min_term_months"]
        prod.max_term_months = cleaned["max_term_months"]
        prod.annual_interest_rate = cleaned["annual_interest_rate"]
        prod.min_monthly_income = cleaned["min_monthly_income"]
        prod.max_loan_to_income_ratio = cleaned["max_loan_to_income_ratio"]
        prod.active = cleaned["active"]
        prod.updated_at = date.today()

        db.session.commit()

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": f"Loan product '{prod.product_name}' updated successfully.",
                "product": prod.to_dict(),
            }), 200

        flash(f"Loan product '{prod.product_name}' updated successfully.", "success")
        return redirect(url_for("manager.loan_products_list"))

    # GET request
    form_data = {
        "product_name": prod.product_name,
        "product_code": prod.product_code,
        "description": prod.description or "",
        "min_amount": str(prod.min_amount),
        "max_amount": str(prod.max_amount),
        "min_term_months": str(prod.min_term_months),
        "max_term_months": str(prod.max_term_months),
        "annual_interest_rate": str(prod.annual_interest_rate),
        "min_monthly_income": str(prod.min_monthly_income),
        "max_loan_to_income_ratio": str(prod.max_loan_to_income_ratio),
        "active": prod.active,
    }
    return render_template(
        "manager/product_form.html",
        product=prod,
        errors={},
        form_data=form_data,
        is_edit=True,
    )


@manager_bp.route("/manager/loan-products/<int:product_id>/toggle-status", methods=["POST"])
@role_required("LOAN_MANAGER")
def toggle_product_status(product_id: int):
    """Activate or deactivate a loan product."""
    prod = db.session.get(LoanProduct, product_id)
    if not prod:
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"Loan product {product_id} not found."}), 404
        flash(f"Loan product #{product_id} not found.", "danger")
        abort(404)

    prod.active = not prod.active
    prod.updated_at = date.today()
    db.session.commit()

    status_str = "ACTIVATED" if prod.active else "DEACTIVATED"
    flash_msg = f"Loan product '{prod.product_name}' has been {status_str}."

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "message": flash_msg,
            "product_id": prod.product_id,
            "active": prod.active,
        }), 200

    flash(flash_msg, "success" if prod.active else "warning")
    return redirect(url_for("manager.loan_products_list"))

