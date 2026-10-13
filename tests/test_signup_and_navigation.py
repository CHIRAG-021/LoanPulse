import re
import pytest
from src.models import db, User


def get_brand_logo_href(html_content: str) -> str:
    """Extract href attribute of the LoanPulse brand logo link in the navbar."""
    match = re.search(r'<a\s+href="([^"]+)"\s+class="brand"', html_content)
    if not match:
        match = re.search(r'class="brand"[^>]*href="([^"]+)"', html_content)
    assert match is not None, "Brand logo link with class 'brand' not found in navbar"
    return match.group(1)


def test_signup_page_loads(client, seeded_db):
    """Verify signup page loads with 200 OK and proper customer onboarding inputs."""
    res = client.get("/signup")
    assert res.status_code == 200
    assert b"Create Customer Account" in res.data
    assert b"full_name" in res.data
    assert b"email" in res.data
    assert b"password" in res.data
    assert b"confirm_password" in res.data
    # Assert NO role selector exists on the page
    assert b"role" not in res.data.lower() or b"role-pill" not in res.data
    assert b"<select name=\"role\"" not in res.data
    assert b"<input type=\"radio\" name=\"role\"" not in res.data


def test_valid_signup_creates_customer(client, seeded_db):
    """Verify valid signup creates user with CUSTOMER role and redirects to login."""
    payload = {
        "full_name": "Alice Borrower",
        "email": "alice.borrower@example.test",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    res = client.post("/signup", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert b"Account created successfully" in res.data

    # Query created user from DB
    user = User.query.filter_by(email="alice.borrower@example.test").first()
    assert user is not None
    assert user.full_name == "Alice Borrower"
    assert user.role == "CUSTOMER"
    assert user.is_active is True
    assert user.password_hash != "Password123!"
    assert user.check_password("Password123!") is True

    # Verify newly created user can log in and access customer dashboard
    login_res = client.post(
        "/login",
        data={"email": "alice.borrower@example.test", "password": "Password123!"},
        follow_redirects=True,
    )
    assert login_res.status_code == 200
    assert b"My Applications" in login_res.data
    assert b"Alice Borrower" in login_res.data
    client.post("/logout")


def test_signup_duplicate_email_rejected(client, seeded_db):
    """Verify registering with an existing email is rejected with 400 error."""
    payload = {
        "full_name": "Duplicate Tester",
        "email": "borrower01@example.test",  # Already exists in seeded data
        "password": "password123",
        "confirm_password": "password123",
    }
    # Form submission
    res = client.post("/signup", data=payload)
    assert res.status_code == 400
    assert b"already exists" in res.data

    # JSON submission
    api_res = client.post("/signup", json=payload, headers={"Accept": "application/json"})
    assert api_res.status_code == 400
    json_data = api_res.get_json()
    assert "email" in json_data["errors"]


def test_signup_missing_required_fields_rejected(client, seeded_db):
    """Verify missing required fields return 400 validation error."""
    # Missing full name
    r1 = client.post("/signup", data={"full_name": "", "email": "a@test.com", "password": "pass123", "confirm_password": "pass123"})
    assert r1.status_code == 400
    assert b"Full name is required" in r1.data

    # Missing email
    r2 = client.post("/signup", data={"full_name": "Test", "email": "", "password": "pass123", "confirm_password": "pass123"})
    assert r2.status_code == 400
    assert b"Email address is required" in r2.data

    # Invalid email format
    r3 = client.post("/signup", data={"full_name": "Test", "email": "notanemail", "password": "pass123", "confirm_password": "pass123"})
    assert r3.status_code == 400
    assert b"valid email" in r3.data

    # Missing password
    r4 = client.post("/signup", data={"full_name": "Test", "email": "valid@test.com", "password": "", "confirm_password": ""})
    assert r4.status_code == 400
    assert b"Password is required" in r4.data


def test_signup_password_mismatch_rejected(client, seeded_db):
    """Verify password and confirmation mismatch returns 400."""
    payload = {
        "full_name": "Mismatch Tester",
        "email": "mismatch@example.test",
        "password": "secretpassword1",
        "confirm_password": "secretpassword2",
    }
    res = client.post("/signup", data=payload)
    assert res.status_code == 400
    assert b"Passwords do not match" in res.data

    # Verify user was NOT created
    assert User.query.filter_by(email="mismatch@example.test").first() is None


def test_signup_password_not_stored_as_plaintext(client, seeded_db):
    """Verify passwords are never stored in plaintext in the database."""
    secret = "TopSecretPassword123!"
    payload = {
        "full_name": "Crypto Test",
        "email": "crypto@example.test",
        "password": secret,
        "confirm_password": secret,
    }
    res = client.post("/signup", data=payload)
    assert res.status_code == 302

    user = User.query.filter_by(email="crypto@example.test").first()
    assert user is not None
    assert user.password_hash != secret
    assert secret not in user.password_hash
    assert user.check_password(secret) is True
    assert user.check_password("WrongPassword") is False


def test_signup_privilege_escalation_prevented(client, seeded_db):
    """Security/RBAC: Attempting to submit role=LOAN_MANAGER or role=LOAN_OFFICER MUST NOT grant staff role."""
    # Malicious payload trying to inject LOAN_MANAGER role
    payload_mgr = {
        "full_name": "Attacker Manager",
        "email": "hacker.mgr@example.test",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "role": "LOAN_MANAGER",
    }
    res_mgr = client.post("/signup", data=payload_mgr)
    assert res_mgr.status_code == 302

    user_mgr = User.query.filter_by(email="hacker.mgr@example.test").first()
    assert user_mgr is not None
    # STRICT ASSERTION: Server explicitly set CUSTOMER
    assert user_mgr.role == "CUSTOMER"
    assert user_mgr.role != "LOAN_MANAGER"

    # Malicious payload trying to inject LOAN_OFFICER role via JSON API
    payload_off = {
        "full_name": "Attacker Officer",
        "email": "hacker.off@example.test",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "role": "LOAN_OFFICER",
    }
    res_off = client.post("/signup", json=payload_off)
    assert res_off.status_code == 201

    user_off = User.query.filter_by(email="hacker.off@example.test").first()
    assert user_off is not None
    # STRICT ASSERTION: Server explicitly set CUSTOMER
    assert user_off.role == "CUSTOMER"
    assert user_off.role != "LOAN_OFFICER"

    # Verify this customer CANNOT access officer or manager queues (RBAC check)
    client.post("/login", data={"email": "hacker.mgr@example.test", "password": "Password123!"}, follow_redirects=True)
    assert client.get("/manager/queue").status_code == 403
    assert client.get("/officer/queue").status_code == 403
    client.post("/logout")


def test_navbar_logo_navigation_logged_out(client, seeded_db):
    """Verify logged-out user sees logo navigating to / (landing page)."""
    res = client.get("/")
    assert res.status_code == 200
    logo_href = get_brand_logo_href(res.data.decode())
    assert logo_href == "/"

    res_login = client.get("/login")
    assert res_login.status_code == 200
    assert get_brand_logo_href(res_login.data.decode()) == "/"

    res_signup = client.get("/signup")
    assert res_signup.status_code == 200
    assert get_brand_logo_href(res_signup.data.decode()) == "/"


def test_navbar_logo_navigation_customer(client, seeded_db):
    """Verify Customer sees logo navigating directly to /customer/dashboard."""
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/customer/dashboard")
    assert res.status_code == 200
    logo_href = get_brand_logo_href(res.data.decode())
    assert "/customer/dashboard" in logo_href

    # Directly visiting / renders public landing page without automatically redirecting
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code == 200
    assert b"LoanPulse" in res_root.data
    client.post("/logout")


def test_navbar_logo_navigation_officer(client, seeded_db):
    """Verify Loan Officer sees logo navigating directly to /officer/queue."""
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/officer/queue")
    assert res.status_code == 200
    logo_href = get_brand_logo_href(res.data.decode())
    assert "/officer/queue" in logo_href

    # Directly visiting / renders public landing page without automatically redirecting
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code == 200
    assert b"LoanPulse" in res_root.data
    client.post("/logout")


def test_navbar_logo_navigation_manager(client, seeded_db):
    """Verify Loan Manager sees logo navigating directly to /manager/queue."""
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/manager/queue")
    assert res.status_code == 200
    logo_href = get_brand_logo_href(res.data.decode())
    assert "/manager/queue" in logo_href

    # Directly visiting / renders public landing page without automatically redirecting
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code == 200
    assert b"LoanPulse" in res_root.data
    client.post("/logout")


def test_navigation_signup_links_present(client, seeded_db):
    """Verify signup links exist on landing page, login page, and navbar when logged out."""
    # Landing page
    res_landing = client.get("/")
    assert res_landing.status_code == 200
    assert b"/signup" in res_landing.data
    assert b"Sign Up" in res_landing.data
    assert b"Create your LoanPulse account to apply for and track your loans." in res_landing.data

    # Login page
    res_login = client.get("/login")
    assert res_login.status_code == 200
    assert b"/signup" in res_login.data
    assert b"Don't have an account? " in res_login.data
    assert b"Sign up" in res_login.data


def test_login_portal_selection_page(client, seeded_db):
    """Verify loading /login renders 2-portal selection page with User and Administration cards."""
    res = client.get("/login")
    assert res.status_code == 200
    assert b"Sign In to LoanPulse" in res.data
    assert b"User" in res.data
    assert b"For customers who want to apply for and track loans." in res.data
    assert b"Continue as User" in res.data
    assert b"/login/user" in res.data
    assert b"Administration" in res.data
    assert b"For authorized Loan Officers and Loan Managers." in res.data
    assert b"Continue to Administration" in res.data
    assert b"/login/admin" in res.data


def test_login_user_page_renders_with_signup(client, seeded_db):
    """Verify /login/user renders customer sign in with email, password, and sign up link."""
    res = client.get("/login/user")
    assert res.status_code == 200
    assert b"Welcome back" in res.data
    assert b"Sign in to manage your LoanPulse account" in res.data
    assert b'name="email"' in res.data
    assert b'name="password"' in res.data
    assert b"/signup" in res.data
    assert b"Sign up" in res.data


def test_login_admin_page_renders_without_signup(client, seeded_db):
    """Verify /login/admin renders administration portal and DOES NOT contain any sign up link."""
    res = client.get("/login/admin")
    assert res.status_code == 200
    assert b"Administration Login" in res.data
    assert b"Secure access for authorized Loan Officers and Loan Managers" in res.data
    assert b'name="email"' in res.data
    assert b'name="password"' in res.data
    # Strict requirement: Administration page MUST NOT contain public sign up link
    assert b"/signup" not in res.data
    assert b"Sign up" not in res.data


def test_login_user_success_customer(client, seeded_db):
    """Verify Customer can log in via /login/user and is routed to customer dashboard."""
    res = client.post(
        "/login/user",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert "/customer/dashboard" in res.location
    client.post("/logout")


def test_login_admin_success_officer(client, seeded_db):
    """Verify Loan Officer can log in via /login/admin and is routed to officer queue."""
    res = client.post(
        "/login/admin",
        data={"email": "officer01@example.test", "password": "demo123"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert "/officer/queue" in res.location
    client.post("/logout")


def test_login_admin_success_manager(client, seeded_db):
    """Verify Loan Manager can log in via /login/admin and is routed to manager queue."""
    res = client.post(
        "/login/admin",
        data={"email": "manager01@example.test", "password": "demo123"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert "/manager/queue" in res.location
    client.post("/logout")


def test_login_user_rejects_staff_credentials(client, seeded_db):
    """Verify entering staff credentials on /login/user is rejected with standardized error message (preventing role enumeration)."""
    # Officer credentials on User login
    res_off = client.post(
        "/login/user",
        data={"email": "officer01@example.test", "password": "demo123"},
    )
    assert res_off.status_code == 401
    assert b"Invalid email or password." in res_off.data

    # Manager credentials on User login
    res_mgr = client.post(
        "/login/user",
        data={"email": "manager01@example.test", "password": "demo123"},
    )
    assert res_mgr.status_code == 401
    assert b"Invalid email or password." in res_mgr.data


def test_login_admin_rejects_customer_credentials(client, seeded_db):
    """Verify entering customer credentials on /login/admin is rejected with standardized error message (preventing role enumeration)."""
    res = client.post(
        "/login/admin",
        data={"email": "borrower01@example.test", "password": "demo123"},
    )
    assert res.status_code == 401
    assert b"Invalid email or password." in res.data


def test_login_direct_post_backward_compatibility(client, seeded_db):
    """Verify direct POST /login works transparently across all roles for test suite compatibility."""
    # Customer
    r1 = client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=False)
    assert r1.status_code == 302
    assert "/customer/dashboard" in r1.location
    client.post("/logout")

    # Officer
    r2 = client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=False)
    assert r2.status_code == 302
    assert "/officer/queue" in r2.location
    client.post("/logout")

    # Manager
    r3 = client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=False)
    assert r3.status_code == 302
    assert "/manager/queue" in r3.location
    client.post("/logout")


def test_navbar_no_demo_tabs_visible(client, seeded_db):
    """Verify navbar contains NO visible demo tabs, demo launchers, or demo chips in any state."""
    # Logged out
    res_out = client.get("/")
    assert res_out.status_code == 200
    assert b"demo-tabs" not in res_out.data
    assert b"Demo Launch" not in res_out.data
    assert b"Customer &#8599;" not in res_out.data
    assert b"Customer \xe2\x86\x97" not in res_out.data

    # Logged in
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_in = client.get("/customer/dashboard")
    assert res_in.status_code == 200
    assert b"demo-tabs" not in res_in.data
    assert b"Demo Tabs" not in res_in.data
    client.post("/logout")

