"""Application lifecycle state machine and audit trail service for LoanPulse (Phase 8).

Enforces allowed status transitions, role permissions, and immutable audit logging.
"""
from datetime import datetime, date
from typing import Any
from src.models import db, LoanApplication, ApplicationAuditLog, User
from src.services.notification_service import create_status_notification


class WorkflowError(Exception):
    """Raised when an application status transition or workflow action violates business rules."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# Allowed status transitions mapped to authorized roles
ALLOWED_TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "DRAFT": {
        "PENDING_REVIEW": {"CUSTOMER", "LOAN_OFFICER", "LOAN_MANAGER"},
        "REJECTED": {"CUSTOMER", "LOAN_OFFICER", "LOAN_MANAGER"},
    },
    "PENDING_REVIEW": {
        "UNDER_REVIEW": {"LOAN_OFFICER", "LOAN_MANAGER"},
        "DOCUMENTS_REQUIRED": {"LOAN_OFFICER", "LOAN_MANAGER"},
        "PENDING_MANAGER_REVIEW": {"LOAN_OFFICER", "LOAN_MANAGER"},
        "REJECTED": {"LOAN_OFFICER", "LOAN_MANAGER"},
    },
    "UNDER_REVIEW": {
        "DOCUMENTS_REQUIRED": {"LOAN_OFFICER", "LOAN_MANAGER"},
        "PENDING_MANAGER_REVIEW": {"LOAN_OFFICER", "LOAN_MANAGER"},
        "REJECTED": {"LOAN_OFFICER", "LOAN_MANAGER"},
    },
    "DOCUMENTS_REQUIRED": {
        "UNDER_REVIEW": {"CUSTOMER", "LOAN_OFFICER", "LOAN_MANAGER"},
        "PENDING_REVIEW": {"CUSTOMER", "LOAN_OFFICER", "LOAN_MANAGER"},
        "REJECTED": {"LOAN_OFFICER", "LOAN_MANAGER"},
    },
    "PENDING_MANAGER_REVIEW": {
        "APPROVED": {"LOAN_MANAGER"},  # Exclusive executive authority
        "REJECTED": {"LOAN_MANAGER"},
        "DOCUMENTS_REQUIRED": {"LOAN_OFFICER", "LOAN_MANAGER"},
    },
    "APPROVED": {
        "DISBURSED": {"LOAN_OFFICER", "LOAN_MANAGER"},
    },
    "REJECTED": {},   # Terminal state
    "DISBURSED": {},  # Terminal state
}


def can_transition(from_status: str, to_status: str, role: str) -> bool:
    """Check whether a status transition is permitted for a given user role."""
    if from_status == to_status:
        return True
    if role == "SYSTEM":
        return True
    allowed_for_status = ALLOWED_TRANSITIONS.get(from_status, {})
    allowed_roles = allowed_for_status.get(to_status, set())
    return role in allowed_roles


def record_application_audit(
    application: LoanApplication,
    actor: Any,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    notes: str | None = None,
    session=None,
    commit: bool = True,
) -> ApplicationAuditLog:
    """Record an immutable audit log entry for any significant loan application event."""
    s = session or db.session
    actor_id = getattr(actor, "user_id", None)
    actor_name = getattr(actor, "full_name", "System")
    actor_role = getattr(actor, "role", "SYSTEM")

    audit_entry = ApplicationAuditLog(
        application_id=application.application_id,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        from_status=from_status or application.status,
        to_status=to_status or application.status,
        action=action,
        notes=notes,
        created_at=datetime.utcnow(),
    )
    s.add(audit_entry)
    if commit:
        s.commit()
    return audit_entry


def transition_application_status(
    application: LoanApplication,
    new_status: str,
    actor: Any,
    action: str | None = None,
    notes: str | None = None,
    session=None,
    commit: bool = True,
) -> ApplicationAuditLog:
    """Validate and execute a transactional status transition with audit logging and notifications.
    
    Raises:
        WorkflowError: If the transition is illegal or unauthorized for the actor's role.
    """
    s = session or db.session
    role = getattr(actor, "role", "SYSTEM")
    old_status = application.status

    if old_status == new_status:
        # No state change, but record action if specified
        act = action or "STATUS_CONFIRMED"
        audit = record_application_audit(
            application=application,
            actor=actor,
            action=act,
            from_status=old_status,
            to_status=new_status,
            notes=notes,
            session=s,
            commit=commit,
        )
        return audit

    # Enforce state machine rules and role authorization
    if not can_transition(old_status, new_status, role):
        if role == "LOAN_OFFICER" and new_status == "APPROVED":
            raise WorkflowError(
                "Loan Officers are not authorized to approve loans. Executive Manager approval is required.",
                status_code=403,
            )
        if role == "CUSTOMER" and new_status not in ("PENDING_REVIEW", "UNDER_REVIEW"):
            raise WorkflowError(
                f"Customers cannot transition application status to {new_status}.",
                status_code=403,
            )
        raise WorkflowError(
            f"Invalid transition from '{old_status}' to '{new_status}' for role '{role}'.",
            status_code=400,
        )

    # Apply application updates
    application.status = new_status
    application.updated_at = date.today()

    if notes:
        application.review_notes = notes

    if new_status == "REJECTED" and notes:
        application.rejection_reason = notes
        application.approved_amount = None
        application.disbursement_status = "NOT_APPLICABLE"
    elif new_status == "APPROVED":
        application.approved_amount = application.requested_amount
        application.disbursement_status = "NOT_DISBURSED"
    elif new_status == "DISBURSED":
        application.disbursement_status = "DISBURSED"
        if not application.disbursement_date:
            application.disbursement_date = date.today()

    act = action or f"TRANSITION_TO_{new_status}"
    audit = record_application_audit(
        application=application,
        actor=actor,
        action=act,
        from_status=old_status,
        to_status=new_status,
        notes=notes,
        session=s,
        commit=False,
    )

    # Generate customer in-app notification
    create_status_notification(application, old_status=old_status, new_status=new_status)

    if commit:
        s.commit()

    return audit
