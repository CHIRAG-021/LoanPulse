"""Automated tests for Window-Scoped Login and Single Active Session Overhaul.

Covers:
1. Public landing page at root / accessible to logged-out and logged-in users.
2. Login and logout for Customer, Loan Officer, and Loan Manager.
3. A new window requiring its own login (cookie alone not sufficient).
4. Same-window refresh and navigation retaining valid authentication.
5. Logging in with the same account from a second window invalidating the first session.
6. Logging in from a different browser/device invalidating the previous session.
7. Invalidated session denied access to protected HTML routes and APIs.
8. Invalidated session unable to perform mutations (e.g. loan application submission).
9. Logging out from an old invalidated session not affecting the newer session.
10. Invalid credentials, expired sessions, direct dashboard URLs, and role-based access control.
11. Multi-role lifecycle workflows retaining security guarantees.
"""
import pytest
from src.models import LoanApplication, User, db


def test_landing_page_logged_out_and_logged_in(client, seeded_db):
    """1. The landing page is always accessible at / for logged-out and logged-in users."""
    # Logged out
    res_out = client.get("/")
    assert res_out.status_code == 200
    assert b"LoanPulse" in res_out.data
    assert b"Log In" in res_out.data
    assert b"Sign Up" in res_out.data

    # Logged in as Customer - visiting / still shows public landing page, not a forced redirect
    client.post(
        "/login?demo_role=CUSTOMER",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    res_cust = client.get("/", follow_redirects=False)
    assert res_cust.status_code == 200
    assert b"LoanPulse" in res_cust.data
    client.post("/logout?demo_role=CUSTOMER")

    # Logged in as Officer - visiting / shows public landing page
    client.post(
        "/login?demo_role=LOAN_OFFICER",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    res_off = client.get("/", follow_redirects=False)
    assert res_off.status_code == 200
    assert b"LoanPulse" in res_off.data
    client.post("/logout?demo_role=LOAN_OFFICER")

    # Logged in as Manager - visiting / shows public landing page
    client.post(
        "/login?demo_role=LOAN_MANAGER",
        data={"email": "manager01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    res_mgr = client.get("/", follow_redirects=False)
    assert res_mgr.status_code == 200
    assert b"LoanPulse" in res_mgr.data
    client.post("/logout?demo_role=LOAN_MANAGER")


def test_login_and_logout_lifecycle_all_roles(client, seeded_db):
    """2. Login and logout lifecycle across Customer, Loan Officer, and Loan Manager."""
    # Customer
    r_c_login = client.post(
        "/login/user",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r_c_login.status_code == 200
    assert "borrower01@example.test" in r_c_login.data.decode() or "Test Borrower 01" in r_c_login.data.decode()

    dash_c = client.get("/customer/dashboard")
    assert dash_c.status_code == 200

    r_c_logout = client.post("/logout", follow_redirects=True)
    assert r_c_logout.status_code == 200
    assert client.get("/customer/dashboard").status_code in (302, 401)

    # Loan Officer
    r_o_login = client.post(
        "/login/admin",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r_o_login.status_code == 200
    assert "officer01@example.test" in r_o_login.data.decode() or "Test Officer 01" in r_o_login.data.decode()

    queue_o = client.get("/officer/queue")
    assert queue_o.status_code == 200

    r_o_logout = client.post("/logout", follow_redirects=True)
    assert r_o_logout.status_code == 200
    assert client.get("/officer/queue").status_code in (302, 401)

    # Loan Manager
    r_m_login = client.post(
        "/login/admin",
        data={"email": "manager01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r_m_login.status_code == 200
    assert "manager01@example.test" in r_m_login.data.decode() or "Test Manager 01" in r_m_login.data.decode()

    queue_m = client.get("/manager/queue")
    assert queue_m.status_code == 200

    r_m_logout = client.post("/logout", follow_redirects=True)
    assert r_m_logout.status_code == 200
    assert client.get("/manager/queue").status_code in (302, 401)


def test_new_window_requires_its_own_login(client, seeded_db):
    """3. A new window requires its own login; shared browser cookies alone do not authenticate it."""
    # Window 1 authenticates with window identifier win_1
    r_w1 = client.post(
        "/login?wid=win_1",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r_w1.status_code == 200

    # Window 1 can access protected dashboard
    r_w1_dash = client.get("/customer/dashboard?wid=win_1")
    assert r_w1_dash.status_code == 200
    assert "Test Borrower 01" in r_w1_dash.data.decode()

    # Window 2 (in same cookie jar) requests dashboard with a new unauthenticated window identifier
    r_w2_dash = client.get("/customer/dashboard?wid=win_2")
    assert r_w2_dash.status_code in (302, 401)

    # Window 2 requesting without wid (e.g. typing dashboard URL directly in new tab address bar)
    r_w2_direct = client.get("/customer/dashboard")
    assert r_w2_direct.status_code in (302, 401)

    # Window 2 visiting root URL sees public landing page
    r_w2_root = client.get("/")
    assert r_w2_root.status_code == 200
    assert b"LoanPulse" in r_w2_root.data

    # Window 2 visiting login sees login form, not automatic dashboard
    r_w2_login = client.get("/login?wid=win_2")
    assert r_w2_login.status_code == 200


def test_same_window_refresh_and_navigation(client, seeded_db):
    """4. Same-window refresh and navigation retains authentication."""
    r_login = client.post(
        "/login?wid=win_persist",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r_login.status_code == 200

    # Refresh dashboard in same window
    r_refresh = client.get("/customer/dashboard?wid=win_persist")
    assert r_refresh.status_code == 200
    assert "Test Borrower 01" in r_refresh.data.decode()

    # Navigate to My Applications in same window
    r_apps = client.get("/customer/applications?wid=win_persist")
    assert r_apps.status_code == 200

    # Navigate to Profile in same window
    r_profile = client.get("/customer/profile?wid=win_persist")
    assert r_profile.status_code == 200

    # Second refresh retains valid session
    r_refresh2 = client.get("/customer/dashboard?wid=win_persist")
    assert r_refresh2.status_code == 200


def test_second_window_login_invalidates_first_window(client, seeded_db):
    """5. Logging in with the same account from a second window invalidates the first session."""
    # Window 1 logs in
    r1 = client.post(
        "/login?wid=w_alpha",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r1.status_code == 200
    assert client.get("/customer/dashboard?wid=w_alpha").status_code == 200

    # Window 2 logs in with the SAME account
    r2 = client.post(
        "/login?wid=w_beta",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert r2.status_code == 200
    assert client.get("/customer/dashboard?wid=w_beta").status_code == 200

    # Window 1 now attempts access -> MUST be rejected because its token is stale
    r1_after = client.get("/customer/dashboard?wid=w_alpha", follow_redirects=False)
    assert r1_after.status_code in (302, 401)
    if r1_after.status_code == 302:
        assert "/login" in r1_after.location

    # Window 2 remains fully active
    r2_check = client.get("/customer/dashboard?wid=w_beta")
    assert r2_check.status_code == 200
    assert "Test Borrower 01" in r2_check.data.decode()


def test_different_device_login_invalidates_previous_device(app, seeded_db):
    """6. Logging in from a different browser/device invalidates the previous session."""
    device1 = app.test_client()
    device2 = app.test_client()

    # Device 1 logs in
    d1_res = device1.post(
        "/login",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert d1_res.status_code == 200
    assert device1.get("/officer/queue").status_code == 200

    # Device 2 logs in with the same officer account
    d2_res = device2.post(
        "/login",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert d2_res.status_code == 200
    assert device2.get("/officer/queue").status_code == 200

    # Device 1 is now invalidated
    d1_check = device1.get("/officer/queue", follow_redirects=False)
    assert d1_check.status_code in (302, 401)
    if d1_check.status_code == 302:
        assert "/login" in d1_check.location

    # Device 2 remains active
    assert device2.get("/officer/queue").status_code == 200


def test_invalidated_session_denied_html_and_api_access(app, seeded_db):
    """7. An invalidated session is denied access to protected HTML routes and JSON APIs."""
    c1 = app.test_client()
    c2 = app.test_client()

    # c1 logs in as customer
    c1.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert c1.get("/customer/dashboard").status_code == 200

    # c2 logs in with same account, invalidating c1
    c2.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)

    # c1 denied HTML route access -> redirects to login
    r_html = c1.get("/customer/dashboard", follow_redirects=False)
    assert r_html.status_code in (302, 401)

    # c1 denied JSON API access -> returns 401 Unauthorized
    r_api = c1.get("/notifications", headers={"Accept": "application/json"})
    assert r_api.status_code == 401
    assert "error" in r_api.get_json()


def test_invalidated_session_cannot_perform_mutations(app, seeded_db):
    """8. An invalidated session cannot perform mutations like loan application submissions."""
    c1 = app.test_client()
    c2 = app.test_client()

    c1.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    initial_app_count = LoanApplication.query.count()

    # Invalidate c1 by logging in elsewhere
    c2.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)

    # c1 attempts to submit a new loan application
    payload = {
        "applicant_name": "Test Borrower 01",
        "monthly_income": "90000",
        "requested_amount": "250000",
        "term_months": "24",
    }
    r_mutate = c1.post("/applications/new", data=payload, follow_redirects=False)

    # Must be denied access (redirected to login or 401)
    assert r_mutate.status_code in (302, 401)

    # Verify database state: no application was created by c1
    after_app_count = LoanApplication.query.count()
    assert after_app_count == initial_app_count


def test_logout_from_invalidated_session_does_not_affect_newer_session(app, seeded_db):
    """9. Logging out from an old invalidated session does NOT terminate the newer active session."""
    c_old = app.test_client()
    c_new = app.test_client()

    c_old.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)

    # c_new logs in, superseding c_old
    c_new.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert c_new.get("/customer/dashboard").status_code == 200

    # User in c_old clicks Logout
    r_old_logout = c_old.post("/logout", follow_redirects=True)
    assert r_old_logout.status_code == 200

    # c_new MUST still be fully active and authenticated
    r_new_check = c_new.get("/customer/dashboard")
    assert r_new_check.status_code == 200
    assert "Test Borrower 01" in r_new_check.data.decode()


def test_invalid_credentials_and_rbac(client, seeded_db):
    """10. Invalid credentials, wrong login portal, direct URLs, and role-based access control."""
    # Invalid password
    r_bad_pw = client.post(
        "/login",
        data={"email": "borrower01@example.test", "password": "wrongpassword"},
    )
    assert r_bad_pw.status_code == 401

    # Wrong portal: Customer attempting Admin login
    r_wrong_portal = client.post(
        "/login/admin",
        data={"email": "borrower01@example.test", "password": "demo123"},
    )
    assert r_wrong_portal.status_code == 401

    # Wrong portal: Officer attempting User login
    r_wrong_portal2 = client.post(
        "/login/user",
        data={"email": "officer01@example.test", "password": "demo123"},
    )
    assert r_wrong_portal2.status_code == 401

    # Direct dashboard access unauthenticated
    client.post("/logout")
    assert client.get("/customer/dashboard").status_code in (302, 401)
    assert client.get("/officer/queue").status_code in (302, 401)
    assert client.get("/manager/queue").status_code in (302, 401)

    # Customer RBAC checks
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert client.get("/officer/queue").status_code == 403
    assert client.get("/manager/queue").status_code == 403
    assert client.get("/officer/kyc").status_code == 403
    client.post("/logout")

    # Officer RBAC checks
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    assert client.get("/manager/queue").status_code == 403
    client.post("/logout")


def test_window_scoped_multi_role_workflow(client, seeded_db):
    """11. Multi-role end-to-end workflow executing with window-scoped sessions across roles."""
    # 1. Customer Window
    client.post(
        "/login?wid=w_cust",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    # 2. Officer Window
    client.post(
        "/login?wid=w_officer",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    # 3. Manager Window
    client.post(
        "/login?wid=w_manager",
        data={"email": "manager01@example.test", "password": "demo123"},
        follow_redirects=True,
    )

    # Customer submits application
    payload = {
        "applicant_name": "Test Borrower 01",
        "monthly_income": "85000",
        "requested_amount": "200000",
        "term_months": "24",
    }
    r_apply = client.post("/applications/new?wid=w_cust", data=payload, follow_redirects=True)
    assert r_apply.status_code == 200

    # Officer reviews and assesses
    r_review = client.get("/officer/applications/APP-0041?wid=w_officer")
    assert r_review.status_code == 200

    r_assess = client.post("/officer/applications/APP-0041/assess?wid=w_officer", follow_redirects=True)
    assert r_assess.status_code == 200

    r_fwd = client.post("/officer/applications/APP-0041/send-to-manager?wid=w_officer", follow_redirects=True)
    assert r_fwd.status_code == 200

    # Manager decides
    r_decide = client.post(
        "/manager/applications/APP-0041/decision?wid=w_manager",
        data={"decision": "APPROVE", "notes": "Approved in window scoped workflow"},
        follow_redirects=True,
    )
    assert r_decide.status_code == 200

    # Officer disburses
    r_disburse = client.post("/officer/applications/APP-0041/disburse?wid=w_officer", follow_redirects=True)
    assert r_disburse.status_code == 200

    # Customer views status
    r_status = client.get("/applications/APP-0041/status?wid=w_cust")
    assert r_status.status_code == 200
    assert "APPROVED" in r_status.data.decode()

