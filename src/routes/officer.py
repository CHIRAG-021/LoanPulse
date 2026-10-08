"""Loan Officer routes for LoanPulse (US-03, US-04, US-06)."""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user

from src.models import db, LoanApplication, Assessment, AssessmentRule
from src.routes.auth import role_required
from src.services.assessment_service import assess_application
from src.services.validation_service import ValidationError
from src.services.notification_service import create_status_notification
from src.services.disbursement_service import record_disbursement

officer_bp = Blueprint("officer", __name__)


@officer_bp.route("/officer/queue")
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def queue():
    """US-04: Loan officer application review queue."""
    # List applications, prioritizing those pending review
    applications = LoanApplication.query.order_by(
        db.case(
            (LoanApplication.status == "PENDING_REVIEW", 1),
            (LoanApplication.status == "DRAFT", 2),
            (LoanApplication.status == "PENDING_MANAGER_REVIEW", 3),
            else_=4,
        ),
        LoanApplication.created_at.desc(),
    ).all()
    return render_template("officer/queue.html", applications=applications)


@officer_bp.route("/officer/applications/<application_id>")
@role_required("LOAN_OFFICER", "LOAN_MANAGER")
def review_application(application_id):
    """US-04 / BR-04 / TR-04: View relevant applicant and loan details."""
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
            "created_at": app_record.created_at.isoformat() if app_record.created_at else None,
            "updated_at": app_record.updated_at.isoformat() if app_record.updated_at else None,
        }), 200

    assessments = Assessment.query.filter_by(application_id=application_id).order_by(Assessment.assessed_at.desc()).all()
    active_rule = AssessmentRule.query.filter_by(active=True).first()

    return render_template(
        "officer/review.html",
        app=app_record,
        assessments=assessments,
        active_rule=active_rule,
    )


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

    old_status = app_record.status
    app_record.status = "PENDING_MANAGER_REVIEW"
    app_record.updated_at = date.today()
    db.session.commit()

    # Create notification on status transition (BR-07, TR-07)
    create_status_notification(app_record, old_status=old_status, new_status="PENDING_MANAGER_REVIEW")

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

    raw_date = request.form.get("disbursement_date") or (request.get_json(silent=True) or {}).get("disbursement_date")
    parsed_date = None
    if raw_date and str(raw_date).strip():
        try:
            parsed_date = date.fromisoformat(str(raw_date).strip())
        except ValueError:
            parsed_date = date.today()

    try:
        record_disbursement(app_record, disbursement_date=parsed_date)
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
