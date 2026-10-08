"""Loan Manager routes for LoanPulse (US-05, BR-05, TR-05)."""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user

from src.models import db, LoanApplication, Assessment
from src.routes.auth import role_required

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

    return render_template(
        "manager/queue.html",
        applications=pending_apps,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
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

    old_status = app_record.status
    decision = raw_decision.upper()
    if decision == "APPROVE":
        app_record.status = "APPROVED"
        app_record.approved_amount = app_record.requested_amount
        app_record.disbursement_status = "NOT_DISBURSED"
        app_record.updated_at = date.today()
        flash_msg = f"Application {app_record.application_id} has been APPROVED."
    else:
        app_record.status = "REJECTED"
        app_record.approved_amount = None
        app_record.disbursement_status = "NOT_APPLICABLE"
        app_record.updated_at = date.today()
        flash_msg = f"Application {app_record.application_id} has been REJECTED."

    db.session.commit()

    # Trigger status change notification (BR-07, TR-07)
    from src.services.notification_service import create_status_notification
    create_status_notification(app_record, old_status=old_status, new_status=app_record.status)

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
