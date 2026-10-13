"""Disbursement tracking service for LoanPulse (US-06, BR-06, TR-06).

Manages post-approval loan disbursement tracking using documented enum values:
NOT_APPLICABLE, NOT_DISBURSED, DISBURSED.
"""
from datetime import date
from typing import Optional

from src.models import db, LoanApplication
from src.services.notification_service import create_status_notification


def record_disbursement(
    application: LoanApplication,
    disbursement_date: Optional[date] = None,
    session=None,
) -> LoanApplication:
    """Record disbursement for an approved loan application.
    
    Raises ValueError if application is not in APPROVED status or is already DISBURSED.
    Updates disbursement_status to DISBURSED and stores disbursement_date.
    Protects against duplicate/concurrent disbursements via atomic query filtering.
    """
    if application.status != "APPROVED":
        raise ValueError(
            f"Cannot disburse application {application.application_id}: status is {application.status}, but must be APPROVED."
        )
    if application.disbursement_status == "DISBURSED":
        raise ValueError(
            f"Application {application.application_id} has already been disbursed."
        )

    s = session or db.session
    actual_date = disbursement_date or date.today()

    # Atomic conditional update protects against concurrent duplicate requests
    updated_rows = (
        s.query(LoanApplication)
        .filter(
            LoanApplication.application_id == application.application_id,
            LoanApplication.status == "APPROVED",
            LoanApplication.disbursement_status != "DISBURSED",
        )
        .update(
            {
                "disbursement_status": "DISBURSED",
                "disbursement_date": actual_date,
                "updated_at": date.today(),
            },
            synchronize_session=False,
        )
    )

    if updated_rows == 0:
        s.refresh(application)
        if application.disbursement_status == "DISBURSED":
            raise ValueError(
                f"Application {application.application_id} has already been disbursed."
            )
        raise ValueError(
            f"Cannot disburse application {application.application_id}: status is {application.status}, but must be APPROVED."
        )

    s.commit()
    s.refresh(application)

    # Create notification for disbursement
    create_status_notification(
        application=application,
        old_status="APPROVED",
        new_status="DISBURSED",
        message=f"Loan {application.application_id} has been disbursed on {actual_date.isoformat()}.",
        session=s,
    )

    return application
