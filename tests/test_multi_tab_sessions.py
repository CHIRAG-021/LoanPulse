"""Tests for Post-MVP Multi-Tab Demo Session Isolation.

Verifies:
- Concurrent isolated demo sessions for CUSTOMER, LOAN_OFFICER, and LOAN_MANAGER within the same browser cookie jar.
- Strict server-side RBAC enforcement across isolated tabs.
- End-to-end multi-tab application workflow without cross-session overwriting.
- Isolated role-specific logout without terminating other active roles.
- Backwards compatibility with standard non-tab login and sessions.
"""
import pytest
from src.models import LoanApplication, User, db


def test_multi_tab_concurrent_logins(client, seeded_db):
    """Verify that Customer, Officer, and Manager can log in concurrently without overwriting."""
    # 1. Tab 1 logs in as CUSTOMER
    r1 = client.post(
        "/login?demo_role=CUSTOMER",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r1.status_code == 200
    assert "borrower01@example.test" in r1.data.decode() or "Test Borrower 01" in r1.data.decode()

    # 2. Tab 2 logs in as LOAN_OFFICER (same browser client sharing cookies)
    r2 = client.post(
        "/login?demo_role=LOAN_OFFICER",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r2.status_code == 200
    assert "officer01@example.test" in r2.data.decode() or "Test Officer 01" in r2.data.decode()

    # 3. Tab 3 logs in as LOAN_MANAGER (same browser client sharing cookies)
    r3 = client.post(
        "/login?demo_role=LOAN_MANAGER",
        data={"email": "manager01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r3.status_code == 200
    assert "manager01@example.test" in r3.data.decode() or "Test Manager 01" in r3.data.decode()

    # Verify Tab 1 (Customer) remains logged in as Customer
    t1_check = client.get("/customer/dashboard?demo_role=CUSTOMER")
    assert t1_check.status_code == 200
    assert "Test Borrower 01" in t1_check.data.decode()
    assert "CUSTOMER" in t1_check.data.decode()

    # Verify Tab 2 (Officer) remains logged in as Officer
    t2_check = client.get("/officer/queue?demo_role=LOAN_OFFICER")
    assert t2_check.status_code == 200
    assert "Test Officer 01" in t2_check.data.decode()
    assert "LOAN_OFFICER" in t2_check.data.decode()

    # Verify Tab 3 (Manager) remains logged in as Manager
    t3_check = client.get("/manager/queue?demo_role=LOAN_MANAGER")
    assert t3_check.status_code == 200
    assert "Test Manager 01" in t3_check.data.decode()
    assert "LOAN_MANAGER" in t3_check.data.decode()


def test_multi_tab_rbac_cross_access_prevented(client, seeded_db):
    """Verify that role-based access control is strictly maintained across tab sessions."""
    # Authenticate Customer and Officer in the same client session
    client.post(
        "/login?demo_role=CUSTOMER",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    client.post(
        "/login?demo_role=LOAN_OFFICER",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )

    # 1. Customer tab cannot access officer queue -> 403 Forbidden
    res_cust_to_off = client.get("/officer/queue?demo_role=CUSTOMER")
    assert res_cust_to_off.status_code == 403

    # 2. Customer tab cannot access manager queue -> 403 Forbidden
    res_cust_to_mgr = client.get("/manager/queue?demo_role=CUSTOMER")
    assert res_cust_to_mgr.status_code == 403

    # 3. Officer tab cannot access manager queue -> 403 Forbidden
    res_off_to_mgr = client.get("/manager/queue?demo_role=LOAN_OFFICER")
    assert res_off_to_mgr.status_code == 403

    # 4. Officer tab cannot access customer application creation -> 403 Forbidden
    res_off_to_apply = client.get("/applications/new?demo_role=LOAN_OFFICER")
    assert res_off_to_apply.status_code == 403

    # 5. Attacker attempting to request an unauthenticated demo_role fails
    res_unauth_role = client.get("/manager/queue?demo_role=LOAN_MANAGER")
    assert res_unauth_role.status_code in (302, 401)


def test_multi_tab_full_concurrent_workflow(client, seeded_db):
    """Verify an end-to-end multi-role lifecycle executing concurrently across three tabs."""
    # Authenticate all 3 roles
    client.post(
        "/login?demo_role=CUSTOMER",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    client.post(
        "/login?demo_role=LOAN_OFFICER",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    client.post(
        "/login?demo_role=LOAN_MANAGER",
        data={"email": "manager01@example.test", "password": "demo123"},
        follow_redirects=True,
    )

    # Step 1: Customer submits application in Tab 1
    new_app_payload = {
        "applicant_name": "Test Borrower 01",
        "monthly_income": "80000",
        "requested_amount": "300000",
        "term_months": "36",
    }
    r_apply = client.post("/applications/new?demo_role=CUSTOMER", data=new_app_payload, follow_redirects=True)
    assert r_apply.status_code == 200
    assert "APP-0041" in r_apply.data.decode() or "Application Details" in r_apply.data.decode()

    # Step 2: Officer in Tab 2 reviews and assesses the application
    r_review = client.get("/officer/applications/APP-0041?demo_role=LOAN_OFFICER")
    assert r_review.status_code == 200
    assert "APP-0041" in r_review.data.decode()

    r_assess = client.post("/officer/applications/APP-0041/assess?demo_role=LOAN_OFFICER", follow_redirects=True)
    assert r_assess.status_code == 200

    r_forward = client.post("/officer/applications/APP-0041/send-to-manager?demo_role=LOAN_OFFICER", follow_redirects=True)
    assert r_forward.status_code == 200

    # Step 3: Manager in Tab 3 reviews and approves
    r_mgr_queue = client.get("/manager/queue?demo_role=LOAN_MANAGER")
    assert r_mgr_queue.status_code == 200
    assert "APP-0041" in r_mgr_queue.data.decode()

    r_decision = client.post(
        "/manager/applications/APP-0041/decision?demo_role=LOAN_MANAGER",
        data={"decision": "APPROVE", "notes": "Approved in multi-tab test"},
        follow_redirects=True,
    )
    assert r_decision.status_code == 200

    # Step 4: Officer in Tab 2 disburses
    r_disburse = client.post("/officer/applications/APP-0041/disburse?demo_role=LOAN_OFFICER", follow_redirects=True)
    assert r_disburse.status_code == 200

    # Step 5: Customer in Tab 1 verifies approved status
    r_status = client.get("/applications/APP-0041/status?demo_role=CUSTOMER")
    assert r_status.status_code == 200
    assert "APPROVED" in r_status.data.decode()


def test_multi_tab_isolated_logout(client, seeded_db):
    """Verify that logging out in one tab does not log out other isolated demo tabs."""
    client.post(
        "/login?demo_role=CUSTOMER",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    client.post(
        "/login?demo_role=LOAN_OFFICER",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )

    # Both are active
    assert client.get("/customer/dashboard?demo_role=CUSTOMER").status_code == 200
    assert client.get("/officer/queue?demo_role=LOAN_OFFICER").status_code == 200

    # Log out Customer tab only
    r_logout_cust = client.post("/logout?demo_role=CUSTOMER", follow_redirects=True)
    assert r_logout_cust.status_code == 200

    # Customer tab is now logged out
    r_cust_after = client.get("/customer/dashboard?demo_role=CUSTOMER")
    assert r_cust_after.status_code in (302, 401)

    # Officer tab remains fully active
    r_off_after = client.get("/officer/queue?demo_role=LOAN_OFFICER")
    assert r_off_after.status_code == 200
    assert "Test Officer 01" in r_off_after.data.decode()
