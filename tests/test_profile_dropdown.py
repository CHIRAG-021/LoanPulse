"""Automated tests for top-right profile area, role labels, and dropdown menu.

Verifies:
1. Profile icon and role label rendered for all three authenticated roles:
   - Customer displays 'User'
   - Loan Officer displays 'Officer'
   - Loan Manager displays 'Manager'
2. Role is retrieved from authenticated user session.
3. Profile dropdown content:
   - 'Who are you?' section with user's name and role
   - 'Log out' link pointing to /logout
4. Logged-out users do not see the profile area.
5. Logout clears authentication and protects protected pages from unauthenticated access.
"""
import pytest
from src.models import User


def test_logged_out_user_has_no_profile_area(client, seeded_db):
    """Unauthenticated users should see the public header, not the profile dropdown."""
    res = client.get("/")
    assert res.status_code == 200
    assert b'id="profileArea"' not in res.data
    assert b'id="profileDropdownBtn"' not in res.data
    assert b"Who are you?" not in res.data


def test_customer_profile_icon_and_role_label(client, seeded_db):
    """Customer should see profile icon, 'User' role label, and dropdown details."""
    login_res = client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert login_res.status_code == 200

    dash_res = client.get("/customer/dashboard")
    assert dash_res.status_code == 200

    # Profile trigger button & icon
    assert b'id="profileArea"' in dash_res.data
    assert b'id="profileDropdownBtn"' in dash_res.data
    assert b'class="profile-icon"' in dash_res.data

    # Role label directly below icon: 'User'
    assert b'class="profile-role-label">User</span>' in dash_res.data

    # Dropdown content: 'Who are you?', user name, and 'Log out'
    assert b"Who are you?" in dash_res.data
    assert b"Test Borrower 01" in dash_res.data
    assert b"Log out" in dash_res.data
    assert b'/logout' in dash_res.data

    client.post("/logout")


def test_officer_profile_icon_and_role_label(client, seeded_db):
    """Loan Officer should see profile icon, 'Officer' role label, and dropdown details."""
    login_res = client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    assert login_res.status_code == 200

    queue_res = client.get("/officer/queue")
    assert queue_res.status_code == 200

    # Profile trigger button & icon
    assert b'id="profileArea"' in queue_res.data
    assert b'id="profileDropdownBtn"' in queue_res.data
    assert b'class="profile-icon"' in queue_res.data

    # Role label directly below icon: 'Officer'
    assert b'class="profile-role-label">Officer</span>' in queue_res.data

    # Dropdown content: 'Who are you?', user name, and 'Log out'
    assert b"Who are you?" in queue_res.data
    assert b"Test Officer 01" in queue_res.data
    assert b"Log out" in queue_res.data
    assert b'/logout' in queue_res.data

    client.post("/logout")


def test_manager_profile_icon_and_role_label(client, seeded_db):
    """Loan Manager should see profile icon, 'Manager' role label, and dropdown details."""
    login_res = client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    assert login_res.status_code == 200

    queue_res = client.get("/manager/queue")
    assert queue_res.status_code == 200

    # Profile trigger button & icon
    assert b'id="profileArea"' in queue_res.data
    assert b'id="profileDropdownBtn"' in queue_res.data
    assert b'class="profile-icon"' in queue_res.data

    # Role label directly below icon: 'Manager'
    assert b'class="profile-role-label">Manager</span>' in queue_res.data

    # Dropdown content: 'Who are you?', user name, and 'Log out'
    assert b"Who are you?" in queue_res.data
    assert b"Test Manager 01" in queue_res.data
    assert b"Log out" in queue_res.data
    assert b'/logout' in queue_res.data

    client.post("/logout")


def test_logout_redirects_and_clears_session(client, seeded_db):
    """Clicking/requesting /logout clears authentication and blocks access to protected pages."""
    # 1. Login as customer
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_auth = client.get("/customer/dashboard")
    assert res_auth.status_code == 200

    # 2. Trigger logout
    res_logout = client.post("/logout", follow_redirects=False)
    assert res_logout.status_code == 302
    assert "/login" in res_logout.headers["Location"]

    # Follow redirect to login page
    res_login_page = client.get(res_logout.headers["Location"])
    assert res_login_page.status_code == 200
    assert b"Signed out" in res_login_page.data or b"signed out" in res_login_page.data or b"Login" in res_login_page.data

    # 3. Subsequent attempt to access protected pages must be denied
    res_protected = client.get("/customer/dashboard", follow_redirects=False)
    assert res_protected.status_code in (302, 401)

    res_officer_protected = client.get("/officer/queue", follow_redirects=False)
    assert res_officer_protected.status_code in (302, 401, 403)

    res_manager_protected = client.get("/manager/queue", follow_redirects=False)
    assert res_manager_protected.status_code in (302, 401, 403)
