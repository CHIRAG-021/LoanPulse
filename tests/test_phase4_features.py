"""Tests for Phase 4: Disbursement tracking, notifications, and RBAC integration.

Implements test cases:
- TC-12 (Record disbursement for approved loan)
- TC-13 (Attempt disbursement for approved loan with NOT_DISBURSED fixture)
- TC-14 (Create status update after status change)
- TC-15 (Do not create status update when no status change occurs)
- TC-18 (Authorized role accesses permitted loan record)
- TC-19 (Unauthorized role accesses protected loan record)
- Disbursement edge cases (non-approved loan rejection)
- Notifications read/unread workflow
- RBAC permissions matrix checks
"""
from datetime import date
import pytest

from src.models import LoanApplication, Notification, RolePermission
from src.services.disbursement_service import record_disbursement
from src.services.notification_service import (
    create_status_notification,
    process_status_change,
    get_user_notifications,
    mark_notifications_as_read,
)
from src.services.rbac_service import has_permission


def login_as(client, email, password="demo123"):
    """Helper to authenticate test client."""
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ============================================================================
# TC-12: Record disbursement for an approved loan (happy path)
# ============================================================================
def test_tc_12_record_disbursement_for_approved_loan(client, seeded_db):
    """TC-12: Sign in as loan officer; open APP-0015 (APPROVED); record disbursement.
    APP-0015 shows DISBURSED and stored disbursement date.
    """
    app_15 = seeded_db.get(LoanApplication, "APP-0015")
    assert app_15 is not None
    # Ensure APP-0015 is APPROVED
    app_15.status = "APPROVED"
    app_15.approved_amount = 250000.0
    app_15.disbursement_status = "NOT_DISBURSED"
    app_15.disbursement_date = None
    seeded_db.commit()

    login_as(client, "officer01@example.test")

    # Record disbursement with date 2026-10-10
    target_date = "2026-10-10"
    response = client.post(
        f"/officer/applications/{app_15.application_id}/disburse",
        data={"disbursement_date": target_date},
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify database record
    seeded_db.refresh(app_15)
    assert app_15.disbursement_status == "DISBURSED"
    assert app_15.disbursement_date == date.fromisoformat(target_date)

    # API verification
    api_res = client.get(f"/officer/applications/{app_15.application_id}", headers={"Accept": "application/json"})
    assert api_res.status_code == 200


# ============================================================================
# TC-13: Attempt disbursement for approved loan with no disbursement record (edge)
# ============================================================================
def test_tc_13_disburse_approved_loan_edge_fixture(client, seeded_db):
    """TC-13: Sign in as loan officer; open APP-EDGE-NO-DISBURSEMENT (APPROVED, NOT_DISBURSED);
    System accepts approved application and records DISBURSED with a disbursement date.
    """
    # Create or ensure edge-case fixture from data/fixtures/application_edge_cases.csv
    edge_app = seeded_db.get(LoanApplication, "APP-EDGE-NO-DISBURSEMENT")
    if not edge_app:
        edge_app = LoanApplication(
            application_id="APP-EDGE-NO-DISBURSEMENT",
            customer_id=3,
            applicant_name="Test Borrower 03",
            monthly_income=60000.0,
            requested_amount=200000.0,
            term_months=24,
            status="APPROVED",
            approved_amount=200000.0,
            disbursement_status="NOT_DISBURSED",
            disbursement_date=None,
            created_at=date.today(),
            updated_at=date.today(),
        )
        seeded_db.add(edge_app)
        seeded_db.commit()

    login_as(client, "officer01@example.test")

    response = client.post(
        f"/officer/applications/{edge_app.application_id}/disburse",
        data={"disbursement_date": "2026-10-12"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["disbursement_status"] == "DISBURSED"
    assert json_data["disbursement_date"] == "2026-10-12"

    seeded_db.refresh(edge_app)
    assert edge_app.disbursement_status == "DISBURSED"
    assert edge_app.disbursement_date == date(2026, 10, 12)


def test_disbursement_rejected_for_non_approved_loan(client, seeded_db):
    """Disbursement must be rejected if application status is not APPROVED."""
    # APP-0002 has status PENDING_REVIEW
    app_02 = seeded_db.get(LoanApplication, "APP-0002")
    assert app_02.status != "APPROVED"

    login_as(client, "officer01@example.test")

    response = client.post(
        f"/officer/applications/{app_02.application_id}/disburse",
        data={"disbursement_date": "2026-10-10"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert "must be approved" in response.get_json()["error"].lower()

    # Direct service call must raise ValueError
    with pytest.raises(ValueError):
        record_disbursement(app_02, session=seeded_db)


# ============================================================================
# TC-14: Create a status update after a status change (happy path)
# ============================================================================
def test_tc_14_create_notification_after_status_change(seeded_db):
    """TC-14: APP-0006 changes from PENDING_REVIEW to APPROVED;
    An update record for APP-0006 is created and identifies the new status as APPROVED.
    """
    app_06 = seeded_db.get(LoanApplication, "APP-0006")
    assert app_06 is not None
    app_06.status = "PENDING_REVIEW"
    seeded_db.commit()

    initial_notifs = seeded_db.query(Notification).filter_by(application_id="APP-0006").count()

    # Process status change to APPROVED
    notif = process_status_change(app_06, new_status="APPROVED", session=seeded_db)

    assert notif is not None
    assert notif.application_id == "APP-0006"
    assert notif.new_status == "APPROVED"
    assert notif.old_status == "PENDING_REVIEW"
    assert "APPROVED" in notif.message

    # Verify record was stored
    after_notifs = seeded_db.query(Notification).filter_by(application_id="APP-0006").count()
    assert after_notifs == initial_notifs + 1


# ============================================================================
# TC-15: Do not create a status update when no status change occurs (edge)
# ============================================================================
def test_tc_15_no_notification_when_status_unchanged(seeded_db):
    """TC-15: APP-0007 remains PENDING_REVIEW;
    No new status-change update is created for APP-0007.
    """
    app_07 = seeded_db.get(LoanApplication, "APP-0007")
    assert app_07 is not None
    app_07.status = "PENDING_REVIEW"
    seeded_db.commit()

    initial_notifs = seeded_db.query(Notification).filter_by(application_id="APP-0007").count()

    # Process APP-0007 without changing status
    notif = process_status_change(app_07, new_status="PENDING_REVIEW", session=seeded_db)

    assert notif is None

    # Verify no new record was created
    after_notifs = seeded_db.query(Notification).filter_by(application_id="APP-0007").count()
    assert after_notifs == initial_notifs


# ============================================================================
# Notifications list and read/unread workflow
# ============================================================================
def test_notifications_view_and_mark_read(client, seeded_db):
    """Customer views their updates and marks them as read."""
    # Seeded user 1 (borrower01@example.test) has notifications
    login_as(client, "borrower01@example.test")

    response = client.get("/notifications")
    assert response.status_code == 200
    assert b"Status Updates History" in response.data

    # Mark as read
    res_mark = client.post("/notifications/mark-read", follow_redirects=True)
    assert res_mark.status_code == 200

    # API check: unread_count is 0
    api_res = client.get("/notifications", headers={"Accept": "application/json"})
    assert api_res.status_code == 200
    assert api_res.get_json()["unread_count"] == 0


# ============================================================================
# TC-18: Authorized role accesses a permitted loan record (happy path)
# ============================================================================
def test_tc_18_authorized_role_accesses_permitted_record(client, seeded_db):
    """TC-18: User role='Loan Officer'; APP-0001 is permitted for the role.
    Sign in as loan officer; open APP-0001; APP-0001 is displayed to authorized officer.
    """
    login_as(client, "officer01@example.test")

    response = client.get("/officer/applications/APP-0001")
    assert response.status_code == 200
    assert b"APP-0001" in response.data


# ============================================================================
# TC-19: Unauthorized role accesses a protected loan record (invalid input)
# ============================================================================
def test_tc_19_unauthorized_role_denied_access(client, seeded_db):
    """TC-19: User role='Customer'; protected staff record APP-0001.
    Sign in as customer; request protected staff record; access is denied (403).
    """
    # Customer 1 attempts to access officer review route for APP-0001
    login_as(client, "borrower01@example.test")

    response = client.get("/officer/applications/APP-0001")
    assert response.status_code == 403

    # API request also denied
    api_res = client.get("/officer/applications/APP-0001", headers={"Accept": "application/json"})
    assert api_res.status_code == 403


# ============================================================================
# RBAC Matrix and RolePermission database checks
# ============================================================================
def test_rbac_database_permissions(seeded_db):
    """Verify role_permissions table matches data/fixtures/unauthorized_access.csv."""
    # CUSTOMER, STAFF_REPORT -> DENY (can_view=False)
    assert has_permission("CUSTOMER", "STAFF_REPORT", session=seeded_db) is False

    # CUSTOMER, OWN_APPLICATION -> ALLOW (can_view=True)
    assert has_permission("CUSTOMER", "OWN_APPLICATION", session=seeded_db) is True

    # LOAN_OFFICER, APPLICATION -> ALLOW (can_view=True)
    assert has_permission("LOAN_OFFICER", "APPLICATION", session=seeded_db) is True

    # LOAN_OFFICER, ASSESSMENT -> ALLOW (can_view=True)
    assert has_permission("LOAN_OFFICER", "ASSESSMENT", session=seeded_db) is True

    # LOAN_MANAGER, PENDING_DECISION_REPORT -> ALLOW (can_view=True)
    assert has_permission("LOAN_MANAGER", "PENDING_DECISION_REPORT", session=seeded_db) is True
