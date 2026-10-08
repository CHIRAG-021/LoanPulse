"""Customer routes for LoanPulse (US-01, US-02)."""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user, login_required

from src.models import db, LoanApplication
from src.routes.auth import role_required
from src.services.validation_service import validate_loan_application

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
    """Customer dashboard listing their own submitted applications."""
    applications = LoanApplication.query.filter_by(customer_id=current_user.user_id).order_by(LoanApplication.created_at.desc()).all()
    return render_template("customer/dashboard.html", applications=applications)


@customer_bp.route("/applications/new", methods=["GET", "POST"])
@role_required("CUSTOMER")
def new_application():
    """US-01 / BR-01: Create and save loan application."""
    if request.method == "POST":
        raw_data = request.get_json(silent=True) or request.form.to_dict()

        # If applicant_name is empty and user is logged in, default to current_user full_name
        if not raw_data.get("applicant_name") and current_user.is_authenticated:
            # Let validation handle it if explicitly sent blank or missing in form
            pass

        validation_result = validate_loan_application(raw_data)
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
            ), 400

        cleaned = validation_result.cleaned_data
        app_id = generate_application_id()
        submit_status = "PENDING_REVIEW"

        new_app = LoanApplication(
            application_id=app_id,
            customer_id=current_user.user_id,
            applicant_name=cleaned["applicant_name"],
            monthly_income=cleaned["monthly_income"],
            requested_amount=cleaned["requested_amount"],
            term_months=cleaned["term_months"],
            status=submit_status,
            approved_amount=None,
            disbursement_status="NOT_APPLICABLE",
            disbursement_date=None,
            created_at=date.today(),
            updated_at=date.today(),
        )
        db.session.add(new_app)
        db.session.commit()

        # Generate initial status notification (BR-07, TR-07)
        from src.services.notification_service import create_status_notification
        create_status_notification(new_app, old_status=None, new_status=submit_status)

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": "Application created successfully",
                "application_id": app_id,
                "status": submit_status,
                "applicant_name": new_app.applicant_name,
                "requested_amount": new_app.requested_amount,
                "term_months": new_app.term_months,
            }), 201

        flash(f"Application {app_id} submitted successfully and sent for review.", "success")
        return redirect(url_for("customer.application_status", application_id=app_id))

    # GET request: render empty application form
    default_form = {
        "applicant_name": current_user.full_name,
        "monthly_income": "60000",
        "requested_amount": "200000",
        "term_months": "24",
    }
    return render_template("customer/apply.html", errors={}, form_data=default_form)


@customer_bp.route("/applications/<application_id>/status")
@login_required
def application_status(application_id):
    """US-02 / BR-02 / TR-02: View current application status."""
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
        return jsonify({
            "application_id": app_record.application_id,
            "status": app_record.status,
            "applicant_name": app_record.applicant_name,
            "monthly_income": app_record.monthly_income,
            "requested_amount": app_record.requested_amount,
            "term_months": app_record.term_months,
            "created_at": app_record.created_at.isoformat() if app_record.created_at else None,
            "updated_at": app_record.updated_at.isoformat() if app_record.updated_at else None,
        }), 200

    return render_template("customer/status.html", app=app_record)


@customer_bp.route("/applications/<application_id>")
@login_required
def application_detail(application_id):
    """Direct application lookup redirecting or rendering status view."""
    return application_status(application_id)
