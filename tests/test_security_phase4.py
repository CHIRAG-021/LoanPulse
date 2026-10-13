"""Targeted security verification tests for Phase 4 remediation:
- LP-VULN-06: Standardized login error messages (no role/account disclosure oracle)
- LP-VULN-07: Window-scoped session parameter handling & Referrer-Policy leakage protection
- LP-VULN-08: Cross-Site Request Forgery (CSRF) protection & POST-only /logout
- LP-VULN-09: Clickjacking defense & defensive HTTP security headers
"""
import re
import pytest
from flask import g
from src.app import create_app
from src.models import db, User, LoanApplication, LoanProduct


# ============================================================================
# 1. LP-VULN-08: CSRF Protection & POST /logout
# ============================================================================

def test_get_logout_rejected_with_405(client):
    """Verify GET /logout returns 405 Method Not Allowed (LP-VULN-08)."""
    res = client.get("/logout")
    assert res.status_code == 405


def test_post_logout_successfully_terminates_session(client, seeded_db):
    """Verify POST /logout terminates the session and redirects to login (LP-VULN-08)."""
    # Log in
    login_res = client.post(
        "/login",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert login_res.status_code == 200
    assert client.get("/customer/dashboard").status_code == 200

    # Logout via POST
    logout_res = client.post("/logout", follow_redirects=True)
    assert logout_res.status_code == 200

    # Subsequent access to protected dashboard is blocked
    dash_res = client.get("/customer/dashboard", follow_redirects=False)
    assert dash_res.status_code in (302, 401)


def test_csrf_token_present_in_forms_and_meta():
    """Verify CSRF token meta tag and hidden form inputs are rendered in HTML templates."""
    # Create test app with CSRF enabled
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    with app.test_client() as client:
        # Check login page
        res = client.get("/login/user")
        assert res.status_code == 200
        assert b'<meta name="csrf-token"' in res.data
        assert b'name="csrf_token"' in res.data

        # Check admin login page
        res_admin = client.get("/login/admin")
        assert res_admin.status_code == 200
        assert b'name="csrf_token"' in res_admin.data

        # Check signup page
        res_signup = client.get("/signup")
        assert res_signup.status_code == 200
        assert b'name="csrf_token"' in res_signup.data


def test_csrf_protection_rejects_missing_token_when_enabled():
    """Verify mutating POST request without CSRF token is rejected with 400 Bad Request (LP-VULN-08)."""
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        # Setup in-memory db
        db.create_all()
        from src.seed import seed_database
        seed_database()

        with app.test_client() as csrf_client:
            # Attempt login without CSRF token -> Rejected with 400
            res = csrf_client.post(
                "/login/user",
                data={"email": "borrower01@example.test", "password": "demo123"},
            )
            assert res.status_code == 400
            assert b"session security token is missing or invalid" in res.data or b"CSRF" in res.data


def test_csrf_protection_accepts_valid_token_in_form_and_header():
    """Verify mutating POST request with valid CSRF token succeeds (LP-VULN-08)."""
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        db.create_all()
        from src.seed import seed_database
        seed_database()

        with app.test_client() as csrf_client:
            # 1. Fetch login page to extract generated CSRF token
            get_res = csrf_client.get("/login/user")
            assert get_res.status_code == 200
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_res.data.decode())
            assert match is not None, "CSRF token hidden input not found in form"
            csrf_token = match.group(1)

            # 2. Submit form with valid csrf_token
            post_res = csrf_client.post(
                "/login/user",
                data={
                    "email": "borrower01@example.test",
                    "password": "demo123",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )
            assert post_res.status_code == 302
            assert "/customer/dashboard" in post_res.location

            # 3. Post with X-CSRFToken header also works
            header_res = csrf_client.post(
                "/logout",
                headers={"X-CSRFToken": csrf_token},
                follow_redirects=True,
            )
            assert header_res.status_code == 200


# ============================================================================
# 2. LP-VULN-06: Standardized Login Error Messages (No Role Oracle)
# ============================================================================

def test_login_error_messages_standardized_across_failure_modes(client, seeded_db):
    """Verify that wrong password, non-existent user, and wrong portal return identical 401 message (LP-VULN-06)."""
    expected_error = b"Invalid email or password."

    # 1. Wrong portal: Customer trying to log in via Administration portal
    res_portal_admin = client.post(
        "/login/admin",
        data={"email": "borrower01@example.test", "password": "demo123"},
    )
    assert res_portal_admin.status_code == 401
    assert expected_error in res_portal_admin.data
    # Must NOT disclose account role or tell them which portal to use
    assert b"These credentials belong to a User account" not in res_portal_admin.data
    assert b"CUSTOMER" not in res_portal_admin.data

    # 2. Wrong portal: Officer trying to log in via User portal
    res_portal_user_off = client.post(
        "/login/user",
        data={"email": "officer01@example.test", "password": "demo123"},
    )
    assert res_portal_user_off.status_code == 401
    assert expected_error in res_portal_user_off.data
    assert b"These credentials belong to an Administration account" not in res_portal_user_off.data
    assert b"LOAN_OFFICER" not in res_portal_user_off.data

    # 3. Wrong portal: Manager trying to log in via User portal
    res_portal_user_mgr = client.post(
        "/login/user",
        data={"email": "manager01@example.test", "password": "demo123"},
    )
    assert res_portal_user_mgr.status_code == 401
    assert expected_error in res_portal_user_mgr.data
    assert b"These credentials belong to an Administration account" not in res_portal_user_mgr.data
    assert b"LOAN_MANAGER" not in res_portal_user_mgr.data

    # 4. Wrong password for existing user
    res_wrong_pw = client.post(
        "/login/user",
        data={"email": "borrower01@example.test", "password": "incorrectpassword"},
    )
    assert res_wrong_pw.status_code == 401
    assert expected_error in res_wrong_pw.data

    # 5. Completely non-existent user email
    res_nonexistent = client.post(
        "/login/user",
        data={"email": "doesnotexist@example.test", "password": "demo123"},
    )
    assert res_nonexistent.status_code == 401
    assert expected_error in res_nonexistent.data


def test_login_json_api_error_standardized(client, seeded_db):
    """Verify JSON API login returns standardized error message across all failure modes."""
    # Wrong portal JSON
    res_json_portal = client.post(
        "/login/admin",
        json={"email": "borrower01@example.test", "password": "demo123"},
        headers={"Accept": "application/json"},
    )
    assert res_json_portal.status_code == 401
    assert res_json_portal.get_json() == {"error": "Invalid email or password."}

    # Wrong password JSON
    res_json_pw = client.post(
        "/login/user",
        json={"email": "borrower01@example.test", "password": "wrong"},
        headers={"Accept": "application/json"},
    )
    assert res_json_pw.status_code == 401
    assert res_json_pw.get_json() == {"error": "Invalid email or password."}


# ============================================================================
# 3. LP-VULN-07: Window-Scoped Session Handling & Leakage Prevention
# ============================================================================

def test_window_session_isolation_and_parameter_propagation(client, seeded_db):
    """Verify window sessions isolate multiple tabs without cross-window privilege leaking (LP-VULN-07)."""
    # 1. Customer in window A
    res_win_a = client.post(
        "/login?wid=win_cust_1",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert res_win_a.status_code == 200

    # Window A has access
    assert client.get("/customer/dashboard?wid=win_cust_1").status_code == 200

    # Window B with unknown wid has NO access (not logged in)
    assert client.get("/customer/dashboard?wid=win_unknown").status_code in (302, 401)

    # 2. Officer in window B
    res_win_b = client.post(
        "/login?wid=win_off_1",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert res_win_b.status_code == 200

    # Both windows maintain isolated identities
    dash_a = client.get("/customer/dashboard?wid=win_cust_1")
    assert dash_a.status_code == 200
    assert "borrower01@example.test" in dash_a.data.decode() or "Test Borrower 01" in dash_a.data.decode()

    queue_b = client.get("/officer/queue?wid=win_off_1")
    assert queue_b.status_code == 200
    assert "officer01@example.test" in queue_b.data.decode() or "Test Officer 01" in queue_b.data.decode()

    # Window A cannot access Officer queue (RBAC check)
    assert client.get("/officer/queue?wid=win_cust_1").status_code == 403

    # Clean up
    client.post("/logout?wid=win_cust_1")
    client.post("/logout?wid=win_off_1")


def test_referrer_policy_and_link_attributes_prevent_wid_leakage(client):
    """Verify Referrer-Policy header and external font link prevent wid URL parameter leakage (LP-VULN-07)."""
    res = client.get("/login?wid=test_secret_wid_123")
    assert res.status_code == 200

    # Strict Referrer-Policy header prevents leaking query parameters across origins
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # External font stylesheet link specifies referrerpolicy="no-referrer"
    html = res.data.decode()
    assert 'rel="stylesheet"' in html
    assert 'fonts.googleapis.com' in html
    assert 'referrerpolicy="no-referrer"' in html


# ============================================================================
# 4. LP-VULN-09: Clickjacking Defense & HTTP Security Headers
# ============================================================================

def test_defensive_http_security_headers_present_on_all_responses(client, seeded_db):
    """Verify security headers are attached to responses (LP-VULN-09)."""
    endpoints = [
        "/",
        "/login",
        "/login/user",
        "/login/admin",
        "/signup",
    ]
    for endpoint in endpoints:
        res = client.get(endpoint)
        assert res.status_code == 200, f"Endpoint {endpoint} failed with {res.status_code}"

        # 1. Anti-clickjacking / framing prevention
        assert res.headers.get("X-Frame-Options") == "DENY"

        # 2. MIME-sniffing prevention
        assert res.headers.get("X-Content-Type-Options") == "nosniff"

        # 3. Referrer-Policy
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

        # 4. Permissions-Policy
        assert "geolocation=()" in res.headers.get("Permissions-Policy", "")
        assert "camera=()" in res.headers.get("Permissions-Policy", "")
        assert "microphone=()" in res.headers.get("Permissions-Policy", "")

        # 5. Content Security Policy
        csp = res.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in csp
        assert "default-src 'self'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp

        # 6. Cache-Control for non-static pages
        assert "no-cache" in res.headers.get("Cache-Control", "")
        assert "no-store" in res.headers.get("Cache-Control", "")
