"""Tests for Phase 3: End-to-end customer, officer, and manager flows, authentication, and RBAC.

Implements test cases:
- TC-01 (Save complete loan application)
- TC-02 (Submit application with required field missing)
- TC-03 (View existing application status)
- TC-04 (Request status for nonexistent application)
- TC-08 (View relevant application information for existing application)
- TC-09 (Open application that does not exist)
- TC-10 (View applications requiring manager decision)
- TC-11 (Pending decision view with no matching applications)
- RBAC, ownership, and decision workflow tests
"""
import pytest
from src.models import LoanApplication, Assessment


def login_as(client, email, password="demo123"):
    """Helper to authenticate a test client session."""
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ============================================================================
# Authentication and RBAC tests
# ============================================================================
def test_auth_login_logout(client, seeded_db):
    """Verify login and logout session management."""
    # Successful login
    res = login_as(client, "borrower01@example.test")
    assert res.status_code == 200
    assert b"borrower01@example.test" in res.data or b"Test Borrower 01" in res.data

    # Logout
    res_logout = client.get("/logout", follow_redirects=True)
    assert res_logout.status_code == 200
    assert b"Login" in res_logout.data


def test_auth_invalid_credentials(client, seeded_db):
    """Verify login failure on bad password."""
    res = client.post("/login", data={"email": "borrower01@example.test", "password": "wrongpassword"})
    assert res.status_code == 401
    assert b"Invalid email or password" in res.data


def test_rbac_restrictions(client, seeded_db):
    """Verify role-based access control restrictions across customer, officer, manager."""
    # 1. Customer cannot access officer or manager queues
    login_as(client, "borrower01@example.test")
    res_officer = client.get("/officer/queue")
    assert res_officer.status_code == 403

    res_manager = client.get("/manager/queue")
    assert res_manager.status_code == 403

    client.get("/logout")

    # 2. Officer cannot access manager queue
    login_as(client, "officer01@example.test")
    res_mgr_queue = client.get("/manager/queue")
    assert res_mgr_queue.status_code == 403


# ============================================================================
# TC-01: Save a complete loan application (happy path)
# ============================================================================
def test_tc_01_save_complete_application(client, seeded_db):
    """TC-01: Customer enters required values and saves application; new reference displayed and stored."""
    # Sign in as customer 1
    login_as(client, "borrower01@example.test")

    payload = {
        "applicant_name": "Test Borrower",
        "monthly_income": "60000",
        "requested_amount": "200000",
        "term_months": "24",
    }
    response = client.post("/applications/new", data=payload, follow_redirects=True)
    assert response.status_code == 200

    # A new application reference is displayed (e.g. APP-0041)
    assert b"APP-0041" in response.data or b"Application Details" in response.data

    # Verify the application values are stored in the database
    new_app = seeded_db.query(LoanApplication).filter_by(applicant_name="Test Borrower", requested_amount=200000.0).first()
    assert new_app is not None
    assert new_app.customer_id == 1
    assert new_app.monthly_income == 60000.0
    assert new_app.term_months == 24
    assert new_app.status == "PENDING_REVIEW"


# ============================================================================
# TC-02: Submit application with a required field missing (invalid input)
# ============================================================================
def test_tc_02_submit_application_missing_income(client, seeded_db):
    """TC-02: Income is blank; submission rejected and income field identified as required."""
    login_as(client, "borrower01@example.test")

    # Monthly income is blank
    payload = {
        "applicant_name": "Test Borrower",
        "monthly_income": "",
        "requested_amount": "200000",
        "term_months": "24",
    }
    initial_count = seeded_db.query(LoanApplication).count()

    response = client.post("/applications/new", data=payload)
    assert response.status_code == 400

    # The income field is identified as required
    assert b"Monthly income is required" in response.data

    # Application is not submitted/stored
    assert seeded_db.query(LoanApplication).count() == initial_count


# ============================================================================
# TC-03: View an existing application's status (happy path)
# ============================================================================
def test_tc_03_view_existing_application_status(client, seeded_db):
    """TC-03: Sign in as application owner; open application; status is displayed."""
    # In seeded data, customer_id=1 owns APP-0002 with status PENDING_REVIEW
    login_as(client, "borrower01@example.test")

    response = client.get("/applications/APP-0002/status")
    assert response.status_code == 200
    assert b"PENDING_REVIEW" in response.data
    assert b"APP-0002" in response.data

    # API response also matches TR-02
    api_res = client.get("/applications/APP-0002/status", headers={"Accept": "application/json"})
    assert api_res.status_code == 200
    json_data = api_res.get_json()
    assert json_data["application_id"] == "APP-0002"
    assert json_data["status"] == "PENDING_REVIEW"


# ============================================================================
# TC-04: Request status for a nonexistent application (invalid input)
# ============================================================================
def test_tc_04_request_status_nonexistent_application(client, seeded_db):
    """TC-04: Request status for nonexistent ID APP-9999; system displays not-found message."""
    login_as(client, "borrower01@example.test")

    response = client.get("/applications/APP-9999/status")
    assert response.status_code == 404

    # API test for APP-9999
    api_res = client.get("/applications/APP-9999/status", headers={"Accept": "application/json"})
    assert api_res.status_code == 404
    assert "not found" in api_res.get_json()["error"].lower()


# ============================================================================
# Customer Ownership Restriction
# ============================================================================
def test_customer_cannot_view_other_customer_application(client, seeded_db):
    """Customer cannot view status of another customer's application."""
    # Customer 1 owns APP-0002; Customer 5 owns APP-0003
    login_as(client, "borrower01@example.test")  # User ID 1

    # Attempt to open APP-0003 (owned by Customer 5)
    response = client.get("/applications/APP-0003/status")
    assert response.status_code == 403


# ============================================================================
# TC-08: View relevant information for an existing application (happy path)
# ============================================================================
def test_tc_08_officer_view_existing_application(client, seeded_db):
    """TC-08: Sign in as loan officer; open APP-0001; applicant and loan details displayed."""
    login_as(client, "officer01@example.test")

    response = client.get("/officer/applications/APP-0001")
    assert response.status_code == 200
    assert b"APP-0001" in response.data
    assert b"Test Borrower 01" in response.data or b"Applicant Details" in response.data

    # TR-04: API endpoint returns applicant and loan fields
    api_res = client.get("/officer/applications/APP-0001", headers={"Accept": "application/json"})
    assert api_res.status_code == 200
    data = api_res.get_json()
    assert data["application_id"] == "APP-0001"
    assert "monthly_income" in data
    assert "requested_amount" in data
    assert "term_months" in data


# ============================================================================
# TC-09: Open an application that does not exist (invalid input)
# ============================================================================
def test_tc_09_officer_open_nonexistent_application(client, seeded_db):
    """TC-09: Sign in as loan officer; open APP-9999; displays not-found message."""
    login_as(client, "officer01@example.test")

    response = client.get("/officer/applications/APP-9999")
    assert response.status_code == 404

    api_res = client.get("/officer/applications/APP-9999", headers={"Accept": "application/json"})
    assert api_res.status_code == 404


# ============================================================================
# Officer assessment and workflow transition
# ============================================================================
def test_officer_assess_and_forward_workflow(client, seeded_db):
    """Officer runs assessment on APP-0003, creates Assessment, forwards to manager."""
    login_as(client, "officer01@example.test")

    # Run assessment
    res_assess = client.post("/officer/applications/APP-0003/assess", follow_redirects=True)
    assert res_assess.status_code == 200
    assert b"ELIGIBLE" in res_assess.data

    # Forward to manager
    res_fwd = client.post("/officer/applications/APP-0003/send-to-manager", follow_redirects=True)
    assert res_fwd.status_code == 200

    app_0003 = seeded_db.get(LoanApplication, "APP-0003")
    assert app_0003.status == "PENDING_MANAGER_REVIEW"


# ============================================================================
# TC-10: View applications requiring manager decision (happy path)
# ============================================================================
def test_tc_10_manager_view_pending_applications(client, seeded_db):
    """TC-10: Sign in as loan manager; APP-0010 (pending) is listed; APP-0003 (not pending) is not."""
    # Ensure APP-0010 has status PENDING_MANAGER_REVIEW and APP-0003 does not
    app_10 = seeded_db.get(LoanApplication, "APP-0010")
    app_03 = seeded_db.get(LoanApplication, "APP-0003")
    assert app_10.status == "PENDING_MANAGER_REVIEW"
    assert app_03.status != "PENDING_MANAGER_REVIEW"

    login_as(client, "manager01@example.test")

    response = client.get("/manager/queue")
    assert response.status_code == 200
    assert b"APP-0010" in response.data
    assert b"APP-0003" not in response.data

    # TR-05: API query returns applications with status PENDING_MANAGER_REVIEW
    api_res = client.get("/manager/queue", headers={"Accept": "application/json"})
    assert api_res.status_code == 200
    pending_ids = [a["application_id"] for a in api_res.get_json()["applications"]]
    assert "APP-0010" in pending_ids
    assert "APP-0003" not in pending_ids


# ============================================================================
# TC-11: Pending-decision view has no matching applications (empty state)
# ============================================================================
def test_tc_11_manager_empty_decision_view(client, seeded_db):
    """TC-11: No application has PENDING_MANAGER_REVIEW; view displays empty-state message and no rows."""
    # Clear all PENDING_MANAGER_REVIEW statuses
    seeded_db.query(LoanApplication).filter_by(status="PENDING_MANAGER_REVIEW").update({"status": "APPROVED"})
    seeded_db.commit()

    login_as(client, "manager01@example.test")

    response = client.get("/manager/queue")
    assert response.status_code == 200
    # Empty-state message displayed
    assert b"No applications currently require a manager decision" in response.data
    assert b"pending-applications-table" not in response.data


# ============================================================================
# Manager Decision Actions (Approve and Reject)
# ============================================================================
def test_manager_approve_and_reject_actions(client, seeded_db):
    """Manager approves one application and rejects another."""
    login_as(client, "manager01@example.test")

    # Approve APP-0010
    res_approve = client.post("/manager/applications/APP-0010/decision", data={"decision": "APPROVE"}, follow_redirects=True)
    assert res_approve.status_code == 200
    app_10 = seeded_db.get(LoanApplication, "APP-0010")
    assert app_10.status == "APPROVED"
    assert app_10.approved_amount == app_10.requested_amount
    assert app_10.disbursement_status == "NOT_DISBURSED"

    # Reject APP-0011
    res_reject = client.post("/manager/applications/APP-0011/decision", data={"decision": "REJECT"}, follow_redirects=True)
    assert res_reject.status_code == 200
    app_11 = seeded_db.get(LoanApplication, "APP-0011")
    assert app_11.status == "REJECTED"
    assert app_11.approved_amount is None
    assert app_11.disbursement_status == "NOT_APPLICABLE"
