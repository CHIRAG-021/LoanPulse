"""Notification service for LoanPulse (US-07, BR-07, TR-07).

Handles generation and management of status-change notification records.
"""
from datetime import date
from typing import List, Optional

from src.models import db, Notification, LoanApplication


def create_status_notification(
    application: LoanApplication,
    old_status: Optional[str],
    new_status: str,
    message: Optional[str] = None,
    session=None,
) -> Optional[Notification]:
    """Create a notification record when an application's status changes.
    
    TC-15: If old_status equals new_status, no update record is created.
    """
    if old_status is not None and old_status == new_status:
        return None

    s = session or db.session
    msg = message or f"Loan application {application.application_id} status changed to {new_status}."

    notification = Notification(
        application_id=application.application_id,
        recipient_user_id=application.customer_id,
        old_status=old_status,
        new_status=new_status,
        message=msg,
        created_at=date.today(),
        is_read=False,
    )
    s.add(notification)
    s.commit()
    return notification


def process_status_change(
    application: LoanApplication,
    new_status: str,
    message: Optional[str] = None,
    session=None,
) -> Optional[Notification]:
    """Process a status change for an application and generate a notification if changed.
    
    Used by TC-14 and TC-15.
    """
    s = session or db.session
    old_status = application.status
    if old_status == new_status:
        return None

    application.status = new_status
    application.updated_at = date.today()
    return create_status_notification(
        application=application,
        old_status=old_status,
        new_status=new_status,
        message=message,
        session=s,
    )


def get_user_notifications(user_id: int, unread_only: bool = False, session=None) -> List[Notification]:
    """Retrieve notifications for a specified user."""
    s = session or db.session
    query = s.query(Notification).filter_by(recipient_user_id=user_id)
    if unread_only:
        query = query.filter_by(is_read=False)
    return query.order_by(Notification.created_at.desc(), Notification.notification_id.desc()).all()


def mark_notifications_as_read(user_id: int, notification_ids: Optional[List[int]] = None, session=None) -> int:
    """Mark notifications as read for a user. Returns count of records updated."""
    s = session or db.session
    query = s.query(Notification).filter_by(recipient_user_id=user_id, is_read=False)
    if notification_ids:
        query = query.filter(Notification.notification_id.in_(notification_ids))

    updated_count = query.update({"is_read": True}, synchronize_session=False)
    s.commit()
    return updated_count
