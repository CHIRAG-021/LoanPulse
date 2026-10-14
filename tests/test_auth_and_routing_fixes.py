"""Comprehensive automated tests for LoanPulse Authentication, Session Management, and Dashboard Routing Fixes.

Covers:
1. Public root URL / displays public landing page regardless of whether user is authenticated or logged out.
2. Unauthenticated access to protected routes redirects to /login with proper next parameter.
3. Post-login redirects directly and cleanly to authoritative role dashboards without query parameters.
4. Strict role authorization on the backend preventing cross-role access (Customer -> Officer/Manager 403; Officer -> Manager 403).
5. URL tampering (e.g. appending ?demo_role= to a protected route) never overrides backend RBAC.
6. Authoritative logout invalidates the database token, clears all session state, and redirects cleanly to /login.
7. Post-logout navigation and refresh on protected routes is blocked and redirected to /login.
8. Single active session enforcement across browsers/devices invalidates earlier sessions.
9. Security cache headers (no-cache, no-store, must-revalidate) present on protected views.
"""
import pytest
from src.models import db, User


def test_public_root_url_always_accessible(client, seeded_db):
    """1. The public root URL / must display the landing page, regardless of whether a user is already logged in."""
    # Logged out
    res_unauth = client.get("/", follow_redirects=False)
    assert res_unauth.status_code == 200
    assert b"LoanPulse" in res_unauth.data
    assert b"Sign Up" in res_unauth.data
    assert b"Log In" in res_unauth.data

    # Logged in as Customer: root URL / still displays public landing page without Active Workspaces section
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust = client.get("/", follow_redirects=False)
    assert res_cust.status_code == 200
    assert b"LoanPulse" in res_cust.data
    assert b"Active Workspaces" not in res_cust.data
    client.post("/logout")

    # Logged in as Loan Officer: root URL / still displays public landing page without Active Workspaces section
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off = client.get("/", follow_redirects=False)
    assert res_off.status_code == 200
    assert b"LoanPulse" in res_off.data
    assert b"Active Workspaces" not in res_off.data
    client.post("/logout")

    # Logged in as Loan Manager: root URL / still displays public landing page without Active Workspaces section
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res_mgr = client.get("/", follow_redirects=False)
    assert res_mgr.status_code == 200
    assert b"LoanPulse" in res_mgr.data
    assert b"Active Workspaces" not in res_mgr.data
    client.post("/logout")


def test_protected_urls_require_authentication(client, seeded_db):
    """2. Protected URLs must require authentication. If unauthenticated, redirect to /login."""
    protected_urls = [
        "/customer/dashboard",
        "/customer/applications",
        "/customer/profile",
        "/customer/kyc",
        "/officer/queue",
        "/officer/kyc",
        "/officer/disbursements",
        "/manager/queue",
        "/manager/loan-products",
        "/notifications",
    ]
    for url in protected_urls:
        res = client.get(url, follow_redirects=False)
        assert res.status_code == 302, f"Expected 302 redirect for {url}, got {res.status_code}"
        assert "/login" in res.headers.get("Location")

        # JSON clients receive 401 Unauthorized
        res_json = client.get(url, headers={"Accept": "application/json"})
        assert res_json.status_code == 401, f"Expected 401 for JSON request to {url}, got {res_json.status_code}"


def test_login_redirects_cleanly_to_authoritative_dashboard(client, seeded_db):
    """3. After login, redirect the user to the correct dashboard according to role, with clean URLs."""
    # Customer -> /customer/dashboard
    r_cust = client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=False)
    assert r_cust.status_code == 302
    assert r_cust.headers.get("Location") == "/customer/dashboard"
    client.post("/logout")

    # Officer -> /officer/queue
    r_off = client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=False)
    assert r_off.status_code == 302
    assert r_off.headers.get("Location") == "/officer/queue"
    client.post("/logout")

    # Manager -> /manager/queue
    r_mgr = client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=False)
    assert r_mgr.status_code == 302
    assert r_mgr.headers.get("Location") == "/manager/queue"
    client.post("/logout")


def test_strict_role_based_access_control(client, seeded_db):
    """4 & 5. Enforce role-based authorization: Customer cannot access Officer/Manager; Officer cannot access Manager."""
    # Customer logged in
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert client.get("/customer/dashboard").status_code == 200
    assert client.get("/officer/queue").status_code == 403
    assert client.get("/officer/kyc").status_code == 403
    assert client.get("/officer/disbursements").status_code == 403
    assert client.get("/manager/queue").status_code == 403
    assert client.get("/manager/loan-products").status_code == 403
    client.post("/logout")

    # Officer logged in
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    assert client.get("/officer/queue").status_code == 200
    # Customer routes redirect to login in new tab context rather than displaying confusing 403
    assert client.get("/customer/dashboard").status_code in (302, 401)
    assert client.get("/customer/applications").status_code in (302, 401)
    # Administrative staff privilege escalation is forbidden with 403
    assert client.get("/manager/queue").status_code == 403
    client.post("/logout")


def test_url_query_tampering_cannot_override_rbac(client, seeded_db):
    """Tampering with URL query parameters (e.g. ?demo_role=CUSTOMER) cannot bypass backend authorization."""
    # Officer logs in
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)

    # Officer attempts to access Customer dashboard by injecting ?demo_role=CUSTOMER
    res_tampered = client.get("/customer/dashboard?demo_role=CUSTOMER")
    assert res_tampered.status_code in (302, 401, 403)

    # Officer attempts to access Manager queue by injecting ?demo_role=LOAN_MANAGER
    res_mgr_tampered = client.get("/manager/queue?demo_role=LOAN_MANAGER")
    assert res_mgr_tampered.status_code in (302, 401, 403)
    client.post("/logout")


def test_logout_completely_invalidates_session(client, seeded_db):
    """6. Logging out must invalidate the current authenticated session and prevent access on back/refresh."""
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert client.get("/customer/dashboard").status_code == 200

    # User in DB has active session token
    user = User.query.filter_by(email="borrower01@example.test").first()
    assert user.active_session_token is not None

    # Perform logout
    res_logout = client.post("/logout", follow_redirects=False)
    assert res_logout.status_code == 302
    assert res_logout.headers.get("Location") == "/login"

    # User in DB has token cleared
    user = User.query.filter_by(email="borrower01@example.test").first()
    assert user.active_session_token is None

    # Subsequent access to protected dashboard returns 302 to /login
    dash_after = client.get("/customer/dashboard", follow_redirects=False)
    assert dash_after.status_code == 302
    assert "/login" in dash_after.headers.get("Location")

    # Refreshing or re-requesting continues to be blocked
    dash_refresh = client.get("/customer/dashboard", follow_redirects=False)
    assert dash_refresh.status_code == 302


def test_single_active_session_invalidation_across_devices(app, seeded_db):
    """8. A second login with the same account invalidates the previous session server-side."""
    dev1 = app.test_client()
    dev2 = app.test_client()

    # Device 1 logs in
    dev1.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert dev1.get("/customer/dashboard").status_code == 200

    # Device 2 logs in with the SAME account
    dev2.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert dev2.get("/customer/dashboard").status_code == 200

    # Device 1's session is now invalidated and redirected to login
    d1_check = dev1.get("/customer/dashboard", follow_redirects=False)
    assert d1_check.status_code == 302
    assert "/login" in d1_check.headers.get("Location")

    # Device 2 remains active
    assert dev2.get("/customer/dashboard").status_code == 200


def test_cache_control_headers_on_protected_views(client, seeded_db):
    """Protected views send no-cache, no-store, must-revalidate headers to prevent back-button disclosure."""
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/customer/dashboard")
    assert res.status_code == 200
    cache_header = res.headers.get("Cache-Control", "")
    assert "no-cache" in cache_header
    assert "no-store" in cache_header
    assert "must-revalidate" in cache_header
    client.post("/logout")


def test_new_tab_pasting_dashboard_url_does_not_throw_403(client, seeded_db):
    """When a dashboard URL is opened in a new tab without that role being authenticated, it redirects to login without 403."""
    # Manager logs in
    r_mgr = client.post("/login/admin", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    assert r_mgr.status_code == 200
    assert client.get("/manager/queue").status_code == 200

    # User opens copied Customer dashboard URL in a new tab (sharing the browser session)
    r_new_tab = client.get("/customer/dashboard", follow_redirects=False)
    # Must redirect to login, NOT throw 403 Access Denied
    assert r_new_tab.status_code in (302, 401)
    assert "/login" in r_new_tab.headers.get("Location", "")

    # Following redirect lands cleanly on login page
    r_login_page = client.get("/customer/dashboard", follow_redirects=True)
    assert r_login_page.status_code == 200
    assert "Sign In" in r_login_page.data.decode()
    assert "Access Denied" not in r_login_page.data.decode()
    assert "Return to Manager Queue" not in r_login_page.data.decode()

    # Original Manager tab remains logged in and functioning
    assert client.get("/manager/queue").status_code == 200
    client.post("/logout")


def test_error_page_navigation_and_links(client, seeded_db):
    """403 Access Denied page displays role-appropriate context, safe navigation, and no unintended target tabs."""
    # 1. Customer attempts to access Officer Queue -> 403 Forbidden
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust_viol = client.get("/officer/queue")
    assert res_cust_viol.status_code == 403
    html = res_cust_viol.data.decode()

    # Must contain safe, role-appropriate navigation
    assert "Back to Customer Workspace" in html
    assert "Sign In / Switch Account" in html
    assert "Go to Homepage" in html
    # Must NOT contain confusing cross-role buttons
    assert "Return to Officer Queue" not in html
    assert "Return to Manager Queue" not in html
    # Must navigate in same tab
    assert 'target="_blank"' not in html
    client.post("/logout")

    # 2. Officer attempts to access Manager Queue -> 403 Forbidden
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off_viol = client.get("/manager/queue")
    assert res_off_viol.status_code == 403
    html_off = res_off_viol.data.decode()

    # Must contain safe, role-appropriate navigation
    assert "Back to Officer Workspace" in html_off
    assert "Sign In / Switch Account" in html_off
    assert "Go to Homepage" in html_off
    # Must NOT contain Manager return button
    assert "Return to Manager Queue" not in html_off
    assert "Back to Manager Workspace" not in html_off
    assert 'target="_blank"' not in html_off
    client.post("/logout")


def test_concurrent_multi_role_tabs_in_same_browser(client, seeded_db):
    """Customer, Officer, and Manager sessions can coexist concurrently without cross-tab session clobbering."""
    # Step 1: Customer signs in
    r_c = client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert r_c.status_code == 200

    # Step 2: Officer signs in (same browser cookie jar)
    r_o = client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    assert r_o.status_code == 200

    # Step 3: Manager signs in (same browser cookie jar)
    r_m = client.post("/login/admin", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    assert r_m.status_code == 200

    # Step 4: Verify all three roles can access their respective dashboards concurrently
    dash_c = client.get("/customer/dashboard")
    assert dash_c.status_code == 200
    assert "Test Borrower 01" in dash_c.data.decode() or "borrower01@example.test" in dash_c.data.decode()

    queue_o = client.get("/officer/queue")
    assert queue_o.status_code == 200
    assert "Test Officer 01" in queue_o.data.decode() or "officer01@example.test" in queue_o.data.decode()

    queue_m = client.get("/manager/queue")
    assert queue_m.status_code == 200
    assert "Test Manager 01" in queue_m.data.decode() or "manager01@example.test" in queue_m.data.decode()

    # Step 5: Logging out of Customer portal does not log out Officer or Manager
    r_logout_c = client.post("/logout", headers={"Referer": "http://localhost/customer/dashboard"}, follow_redirects=True)
    assert r_logout_c.status_code == 200
    assert client.get("/customer/dashboard").status_code in (302, 401)
    assert client.get("/officer/queue").status_code == 200
    assert client.get("/manager/queue").status_code == 200

    # Step 6: Global logout cleans all remaining sessions
    client.post("/logout")
    assert client.get("/officer/queue").status_code in (302, 401)
    assert client.get("/manager/queue").status_code in (302, 401)

