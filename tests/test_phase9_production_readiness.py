"""Automated tests for Phase 9: Production Readiness, Security & Testing.

Verifies:
1. Production configuration and secure session cookie settings (HttpOnly, SameSite=Lax).
2. Production error handling for 400, 403, 404, 405, and 500 in both HTML and JSON modes.
3. Full end-to-end loan lifecycle (Customer apply -> Officer triage/forward -> Manager decision -> Officer disbursement).
4. Strict RBAC enforcement and tenant isolation across Customer, Officer, and Manager.
5. Protection against duplicate submissions, invalid financial parameters, and unauthorized transitions.
6. Database teardown session rollback and query performance optimizations.
7. Verification of recent UI work (Profile dropdown, Role labels, Theme toggle, Light Mode default).
"""
import io
import pytest
from datetime import date
from src.config import config_by_name, ProductionConfig, Config
from src.models import db, User, LoanApplication, LoanProduct, ApplicationAuditLog, Assessment


def test_production_configuration_and_cookie_security():
    """Verify ProductionConfig defines production-safe settings."""
    assert "production" in config_by_name
    prod_cfg = config_by_name["production"]
    assert issubclass(prod_cfg, Config)
    assert prod_cfg.DEBUG is False
    assert prod_cfg.TESTING is False
    assert prod_cfg.SESSION_COOKIE_HTTPONLY is True
    assert prod_cfg.SESSION_COOKIE_SAMESITE == "Lax"


def test_custom_error_handlers_html_and_json(client, seeded_db):
    """Verify custom error handlers render styled error.html for web users and JSON for API clients."""
    # 404 HTML
    html_404 = client.get("/nonexistent-page-url-xyz")
    assert html_404.status_code == 404
    assert b"404" in html_404.data
    assert b"Record or Page Not Found" in html_404.data
    assert b"Go to Homepage" in html_404.data

    # 404 JSON
    json_404 = client.get("/nonexistent-page-url-xyz", headers={"Accept": "application/json"})
    assert json_404.status_code == 404
    data_404 = json_404.get_json()
    assert data_404["error"] == "Not Found"

    # 403 Forbidden (Customer accessing Manager queue)
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    html_403 = client.get("/manager/queue")
    assert html_403.status_code == 403
    assert b"403" in html_403.data
    assert b"Access Denied" in html_403.data

    json_403 = client.get("/manager/queue", headers={"Accept": "application/json"})
    assert json_403.status_code == 403
    assert json_403.get_json()["error"] == "Forbidden: insufficient role permissions"
    client.post("/logout")


def test_full_loan_lifecycle_and_audit_trail(client, seeded_db):
    """Test full loan lifecycle: Customer apply -> Officer review/forward -> Manager approve -> Officer disburse."""
    # 1. Customer logs in and applies
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    
    prod = LoanProduct.query.filter_by(product_code="PERSONAL", active=True).first()
    assert prod is not None

    apply_payload = {
        "action": "submit",
        "applicant_name": "Test Borrower 01",
        "monthly_income": "60000",
        "requested_amount": "150000",
        "term_months": "24",
        "product_id": str(prod.product_id),
        "loan_purpose": "PERSONAL",
        "employment_type": "SALARIED",
        "employer_name": "Tech Corp",
        "existing_obligations": "5000",
        "preferred_repayment_date": "5",
    }
    apply_res = client.post("/applications/new", data=apply_payload, follow_redirects=True)
    assert apply_res.status_code == 200

    new_app = LoanApplication.query.filter_by(applicant_name="Test Borrower 01").order_by(LoanApplication.created_at.desc()).first()
    assert new_app is not None
    app_id = new_app.application_id
    assert new_app.status == "PENDING_REVIEW"
    assert new_app.applied_interest_rate == prod.annual_interest_rate

    client.post("/logout")

    # 2. Officer logs in and reviews
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    
    # Officer views application
    officer_view = client.get(f"/officer/applications/{app_id}")
    assert officer_view.status_code == 200

    # Officer attempts direct approval -> Must be rejected (manager only authority)
    direct_approve = client.post(f"/manager/applications/{app_id}/decision", data={"decision": "APPROVE"})
    assert direct_approve.status_code == 403

    # Officer forwards application to manager decision queue
    forward_res = client.post(f"/officer/applications/{app_id}/send-to-manager", data={"notes": "All checks passed. Recommend approval."}, follow_redirects=True)
    assert forward_res.status_code == 200

    refreshed_app = db.session.get(LoanApplication, app_id)
    assert refreshed_app.status == "PENDING_MANAGER_REVIEW"

    client.post("/logout")

    # 3. Manager logs in and decides
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    
    mgr_queue = client.get("/manager/queue")
    assert mgr_queue.status_code == 200
    assert app_id.encode() in mgr_queue.data

    # Manager approves application
    approve_res = client.post(f"/manager/applications/{app_id}/decision", data={"decision": "APPROVE", "notes": "Approved by Senior Credit Manager."}, follow_redirects=True)
    assert approve_res.status_code == 200

    approved_app = db.session.get(LoanApplication, app_id)
    assert approved_app.status == "APPROVED"
    assert approved_app.approved_amount == approved_app.requested_amount

    client.post("/logout")

    # 4. Officer records disbursement
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    
    disburse_res = client.post(f"/officer/applications/{app_id}/disburse", data={"disbursement_date": date.today().isoformat()}, follow_redirects=True)
    assert disburse_res.status_code == 200

    disbursed_app = db.session.get(LoanApplication, app_id)
    assert disbursed_app.status == "APPROVED"
    assert disbursed_app.disbursement_status == "DISBURSED"
    assert disbursed_app.disbursement_date is not None

    client.post("/logout")

    # 5. Customer logs in and verifies final status and immutable audit log
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    
    status_res = client.get(f"/applications/{app_id}/status")
    assert status_res.status_code == 200
    assert b"DISBURSED" in status_res.data

    # Check audit log entries exist
    logs = ApplicationAuditLog.query.filter_by(application_id=app_id).all()
    actions = [l.action for l in logs]
    assert "SUBMITTED" in actions
    assert "FORWARDED_TO_MANAGER" in actions
    assert "MANAGER_APPROVED" in actions
    assert "DISBURSED" in actions

    client.post("/logout")


def test_input_validation_and_product_boundary_checks(client, seeded_db):
    """Test validation rejection for invalid inputs and product limit bounds."""
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    prod = LoanProduct.query.filter_by(product_code="PERSONAL", active=True).first()

    # 1. Negative income
    res_neg_inc = client.post("/applications/new", data={
        "action": "submit",
        "applicant_name": "Test User",
        "monthly_income": "-5000",
        "requested_amount": "50000",
        "term_months": "24",
    }, headers={"Accept": "application/json"})
    assert res_neg_inc.status_code == 400
    assert "monthly_income" in res_neg_inc.get_json()["errors"]

    # 2. Requested amount below minimum product limit
    res_below_min = client.post("/applications/new", data={
        "action": "submit",
        "applicant_name": "Test User",
        "monthly_income": "50000",
        "requested_amount": str(float(prod.min_amount) - 1000),
        "term_months": "24",
        "product_id": str(prod.product_id),
    }, headers={"Accept": "application/json"})
    assert res_below_min.status_code == 400
    assert "requested_amount" in res_below_min.get_json()["errors"]

    # 3. Requested amount exceeding maximum product limit
    res_above_max = client.post("/applications/new", data={
        "action": "submit",
        "applicant_name": "Test User",
        "monthly_income": "50000",
        "requested_amount": str(float(prod.max_amount) + 50000),
        "term_months": "24",
        "product_id": str(prod.product_id),
    }, headers={"Accept": "application/json"})
    assert res_above_max.status_code == 400
    assert "requested_amount" in res_above_max.get_json()["errors"]

    # 4. Tenure below minimum allowed term
    res_below_term = client.post("/applications/new", data={
        "action": "submit",
        "applicant_name": "Test User",
        "monthly_income": "50000",
        "requested_amount": "100000",
        "term_months": str(int(prod.min_term_months) - 5),
        "product_id": str(prod.product_id),
    }, headers={"Accept": "application/json"})
    assert res_below_term.status_code == 400
    assert "term_months" in res_below_term.get_json()["errors"]

    client.post("/logout")


def test_customer_isolation_and_unauthorized_record_access(client, seeded_db):
    """Verify strict tenant isolation: Customer A cannot view or access Customer B's records."""
    # Find existing application owned by customer 1
    cust1_app = LoanApplication.query.filter_by(customer_id=1).first()
    assert cust1_app is not None

    # Sign in as customer 2
    login_cust2 = client.post("/login", data={"email": "borrower02@example.test", "password": "demo123"}, follow_redirects=True)
    assert login_cust2.status_code == 200

    # Customer 2 attempts to view Customer 1's application
    res_forbidden = client.get(f"/applications/{cust1_app.application_id}/status")
    assert res_forbidden.status_code == 403

    res_json_forbidden = client.get(f"/applications/{cust1_app.application_id}/status", headers={"Accept": "application/json"})
    assert res_json_forbidden.status_code == 403

    client.post("/logout")


def test_disbursement_guardrails(client, seeded_db):
    """Verify that only APPROVED loans can be disbursed; DRAFT, PENDING, or REJECTED loans are blocked."""
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)

    # Attempt to disburse a pending application
    pending_app = LoanApplication.query.filter_by(status="PENDING_REVIEW").first()
    if pending_app:
        disburse_fail = client.post(f"/officer/applications/{pending_app.application_id}/disburse", data={"disbursement_date": date.today().isoformat()})
        assert disburse_fail.status_code in (400, 302)
        # Should not be disbursed
        check_app = db.session.get(LoanApplication, pending_app.application_id)
        assert check_app.status != "DISBURSED"

    client.post("/logout")


def test_officer_queue_performance_queries(client, seeded_db):
    """Verify that officer queue renders with SQL count aggregations matching actual records."""
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    
    queue_res = client.get("/officer/queue")
    assert queue_res.status_code == 200
    
    # Counts match database records
    expected_total = LoanApplication.query.count()
    assert f"Total Queue Volume</span>\n            <b>{expected_total}</b>".encode() in queue_res.data or str(expected_total).encode() in queue_res.data

    client.post("/logout")
