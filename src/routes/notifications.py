"""Notification routes for LoanPulse (US-07, BR-07, TR-07)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required

from src.models import db, Notification
from src.services.notification_service import mark_notifications_as_read

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications")
@login_required
def list_notifications():
    """US-07 / BR-07 / TR-07: View status updates and notifications."""
    if current_user.role == "CUSTOMER":
        query = Notification.query.filter_by(recipient_user_id=current_user.user_id)
    else:
        # Loan staff view system notifications
        query = Notification.query

    notifications = query.order_by(Notification.created_at.desc(), Notification.notification_id.desc()).all()
    unread_count = sum(1 for n in notifications if not n.is_read)

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({
            "unread_count": unread_count,
            "notifications": [
                {
                    "notification_id": n.notification_id,
                    "application_id": n.application_id,
                    "recipient_user_id": n.recipient_user_id,
                    "old_status": n.old_status,
                    "new_status": n.new_status,
                    "message": n.message,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                    "is_read": n.is_read,
                }
                for n in notifications
            ]
        }), 200

    return render_template(
        "notifications/index.html",
        notifications=notifications,
        unread_count=unread_count,
    )


@notifications_bp.route("/notifications/mark-read", methods=["POST"])
@login_required
def mark_read():
    """Mark visible notifications as read."""
    if current_user.role == "CUSTOMER":
        mark_notifications_as_read(user_id=current_user.user_id)
    else:
        Notification.query.filter_by(is_read=False).update({"is_read": True})
        db.session.commit()

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"message": "Notifications marked as read"}), 200

    flash("Visible updates marked as read.", "success")
    return redirect(url_for("notifications.list_notifications"))
