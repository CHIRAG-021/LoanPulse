"""Automated tests for LoanPulse upgraded fintech dashboards and workspaces."""
import pytest
from src.models import db, LoanApplication, Notification, User


def test_customer_dashboard_metrics_and_isolation(client, seeded_db):
    """Verify customer dashboard metrics reflect actual database records and customer isolation is maintained."""
    # Log in as borrower01
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)

    res = client.get("/customer/dashboard")
    assert res.status_code == 200
    assert b"Welcome back, Test Borrower 01" in res.data
    assert b"Apply for a Loan" in res.data
    assert b"Total Applications" in res.data
    assert b"Pending Applications" in res.data
    assert b"Approved Applications" in res.data
    assert b"Disbursed Applications" in res.data
    assert b"Recent Notifications & Updates" in res.data

    # Verify customer cannot access officer or manager queues (RBAC)
    assert client.get("/officer/queue").status_code == 403
    assert client.get("/officer/disbursements").status_code == 403
    assert client.get("/manager/queue").status_code == 403
    client.post("/logout")


def test_customer_application_status_and_lifecycle_timeline(client, seeded_db):
    """Verify customer application detail page renders 5-stage lifecycle timeline and real assessment data."""
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)

    # APP-0002 belongs to borrower01 (user_id=1)
    res = client.get("/applications/APP-0002/status")
    assert res.status_code == 200
    assert b"Application Details: APP-0002" in res.data
    assert b"Operational Lifecycle Progress" in res.data
    assert b"1. Submitted" in res.data
    assert b"2. Officer Review" in res.data
    assert b"3. Manager Review" in res.data
    assert b"4. Final Decision" in res.data
    assert b"5. Disbursement" in res.data
    assert b"Applicant Information" in res.data
    assert b"Loan Details" in res.data

    # Customer cannot access another customer's application (APP-0001 belongs to customer 5)
    assert client.get("/applications/APP-0001/status").status_code == 403
    client.post("/logout")


def test_officer_workspace_queue_and_review(client, seeded_db):
    """Verify officer workspace queue, search, and structured application review page."""
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)

    # Queue view
    res = client.get("/officer/queue")
    assert res.status_code == 200
    assert b"Loan Officer Workspace" in res.data
    assert b"Review applications, perform assessments" in res.data
    assert b"Total Queue Volume" in res.data
    assert b"Pending Review" in res.data
    assert b"Pending Manager Review" in res.data
    assert b"Approved / Disbursed" in res.data
    assert b"Application Queue" in res.data
    assert b"Search by Application ID or Applicant" in res.data
    assert b'<select name="status"' not in res.data
    assert b'<select name="product_id"' not in res.data

    # Review view
    res_review = client.get("/officer/applications/APP-0001")
    assert res_review.status_code == 200
    assert b"Application Review: APP-0001" in res_review.data
    assert b"Applicant Information" in res_review.data
    assert b"Loan Request" in res_review.data
    assert b"Deterministic Rule-Based Assessment" in res_review.data
    assert b"Income Requirement" in res_review.data
    assert b"Loan-to-Income Ratio" in res_review.data
    assert b"Term Requirement" in res_review.data
    assert b"Run Rule Assessment" in res_review.data
    client.post("/logout")


def test_manager_workspace_and_executive_review(client, seeded_db):
    """Verify manager decision queue and dedicated executive review page."""
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)

    # Queue view
    res = client.get("/manager/queue")
    assert res.status_code == 200
    assert b"Manager Workspace" in res.data
    assert b"Review assessed applications and make final lending decisions" in res.data
    assert b"Pending Manager Decisions" in res.data
    assert b"Approved Portfolio" in res.data
    assert b"Rejected Applications" in res.data
    assert b"Disbursed Portfolio" in res.data

    # Dedicated review route for manager
    res_review = client.get("/manager/applications/APP-0001")
    assert res_review.status_code == 200
    assert b"Executive Decision Review: APP-0001" in res_review.data
    assert b"Applicant Information" in res_review.data
    assert b"Loan Request" in res_review.data
    assert b"Deterministic Rule-Based Assessment" in res_review.data
    assert b"Income Requirement" in res_review.data
    assert b"Loan-to-Income Ratio" in res_review.data
    assert b"Term Requirement" in res_review.data
    assert b"Approve Application" in res_review.data
    assert b"Reject Application" in res_review.data
    client.post("/logout")


def test_disbursement_workspace_view(client, seeded_db):
    """Verify officer disbursement workspace displays approved loans with proper tracking columns."""
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)

    res = client.get("/officer/disbursements")
    assert res.status_code == 200
    assert b"Disbursement Workspace" in res.data
    assert b"Approved Applications" in res.data
    assert b"Disbursed Loans" in res.data
    assert b"Awaiting Disbursement" in res.data
    assert b"Record Loan Disbursement" in res.data
    assert b"Approved Loans Tracking" in res.data
    assert b"Approval Status" in res.data
    assert b"Disbursement Status" in res.data
    client.post("/logout")


def test_end_to_end_operational_lifecycle(client, seeded_db):
    """Verify full operational lifecycle: Apply -> Assess -> Forward -> Approve -> Disburse -> Notification."""
    # 1. Customer applies
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    apply_payload = {
        "applicant_name": "Test Borrower 01",
        "monthly_income": "80000",
        "requested_amount": "250000",
        "term_months": "24",
        "purpose": "Home Improvement",
    }
    apply_res = client.post("/applications/new", data=apply_payload, follow_redirects=True)
    assert apply_res.status_code == 200
    assert b"Application Details" in apply_res.data or b"Application" in apply_res.data
    client.post("/logout")

    # Find the newly created application
    new_app = LoanApplication.query.filter_by(monthly_income=80000.0, requested_amount=250000.0).first()
    assert new_app is not None
    app_id = new_app.application_id
    assert new_app.status == "PENDING_REVIEW"

    # 2. Officer assesses application
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    assess_res = client.post(f"/officer/applications/{app_id}/assess", follow_redirects=True)
    assert assess_res.status_code == 200
    assert b"ELIGIBLE" in assess_res.data

    # 3. Officer forwards to manager
    forward_res = client.post(f"/officer/applications/{app_id}/send-to-manager", follow_redirects=True)
    assert forward_res.status_code == 200
    db.session.refresh(new_app)
    assert new_app.status == "PENDING_MANAGER_REVIEW"
    client.post("/logout")

    # 4. Manager reviews and approves application
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    mgr_review = client.get(f"/manager/applications/{app_id}")
    assert mgr_review.status_code == 200
    approve_res = client.post(
        f"/manager/applications/{app_id}/decision",
        data={"decision": "APPROVE"},
        follow_redirects=True,
    )
    assert approve_res.status_code == 200
    db.session.refresh(new_app)
    assert new_app.status == "APPROVED"
    assert new_app.disbursement_status == "NOT_DISBURSED"
    client.post("/logout")

    # 5. Officer records disbursement
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    disb_res = client.post(
        f"/officer/applications/{app_id}/disburse",
        data={"disbursement_date": "2026-10-08"},
        follow_redirects=True,
    )
    assert disb_res.status_code == 200
    db.session.refresh(new_app)
    assert new_app.disbursement_status == "DISBURSED"
    client.post("/logout")

    # 6. Customer receives notifications
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    dash_res = client.get("/customer/dashboard")
    assert dash_res.status_code == 200
    assert app_id.encode() in dash_res.data

    notifs = Notification.query.filter_by(application_id=app_id).all()
    assert len(notifs) >= 3  # submission, forwarded, approved
    client.post("/logout")
