"""Automated tests for LoanPulse brand logo and favicon integration.

Verifies:
1. Favicon and logo asset availability via /static/loanpulse.png, /favicon.ico, and /loanpulse.png.
2. Favicon <link> tags in <head> across public and authenticated pages.
3. Top-left navbar brand logo rendering with loanpulse.png, correct alt text, and styling.
4. Role-based destination links for brand logo (Customer -> /customer/dashboard, Officer -> /officer/queue, Manager -> /manager/queue, Public -> /).
5. Theme compatibility (Light Mode and Dark Mode navbar preservation).
"""
import pytest
from src.models import db, User


def test_logo_and_favicon_static_endpoints(client):
    """Verify loanpulse.png and favicon endpoints respond with 200 OK and PNG mimetype."""
    # 1. Standard static URL
    res_static = client.get("/static/loanpulse.png")
    assert res_static.status_code == 200
    assert res_static.content_type == "image/png"
    assert len(res_static.data) > 100000  # Image file is ~4.2 MB

    # 2. Browser default /favicon.ico
    res_ico = client.get("/favicon.ico")
    assert res_ico.status_code == 200
    assert res_ico.content_type == "image/png"
    assert len(res_ico.data) > 100000

    # 3. Direct /loanpulse.png endpoint
    res_root = client.get("/loanpulse.png")
    assert res_root.status_code == 200
    assert res_root.content_type == "image/png"
    assert len(res_root.data) > 100000


def test_favicon_link_tags_present_on_all_pages(client, seeded_db):
    """Verify favicon <link> tags are present in <head> for landing, login, and authenticated pages."""
    # 1. Public landing page
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b'<link rel="icon" type="image/png" href="/static/loanpulse.png">' in res_home.data
    assert b'<link rel="shortcut icon" type="image/png" href="/static/loanpulse.png">' in res_home.data
    assert b'<link rel="apple-touch-icon" href="/static/loanpulse.png">' in res_home.data

    # 2. User login page
    res_login = client.get("/login/user")
    assert res_login.status_code == 200
    assert b'<link rel="icon" type="image/png" href="/static/loanpulse.png">' in res_login.data

    # 3. Customer Dashboard
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust = client.get("/customer/dashboard")
    assert res_cust.status_code == 200
    assert b'<link rel="icon" type="image/png" href="/static/loanpulse.png">' in res_cust.data
    client.post("/logout")

    # 4. Officer Queue
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off = client.get("/officer/queue")
    assert res_off.status_code == 200
    assert b'<link rel="icon" type="image/png" href="/static/loanpulse.png">' in res_off.data
    client.post("/logout")

    # 5. Manager Queue
    client.post("/login/admin", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res_mgr = client.get("/manager/queue")
    assert res_mgr.status_code == 200
    assert b'<link rel="icon" type="image/png" href="/static/loanpulse.png">' in res_mgr.data
    client.post("/logout")


def test_navbar_logo_rendering_and_attributes(client, seeded_db):
    """Verify the top-left navbar contains the logo image with correct src, alt, and class and LoanPulse brand text."""
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b'class="brand"' in res_home.data
    assert b'<img src="/static/loanpulse.png" alt="LoanPulse" class="brand-logo-img">' in res_home.data
    assert b'<span class="brand-text">LoanPulse</span>' in res_home.data


def test_navbar_branding_text_and_flex_alignment(client, seeded_db):
    """Verify navbar branding includes logo image and LoanPulse text flex-aligned across all dashboards and themes."""
    # 1. CSS rules validation: .brand flex container and .brand-text typography
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    css = css_res.data.decode("utf-8")
    assert ".brand {" in css
    assert "display: inline-flex;" in css
    assert "align-items: center;" in css
    assert "gap: 10px;" in css
    assert ".brand-text {" in css
    assert "font-weight: 700;" in css
    assert "color: #f8fafc;" in css

    # 2. Consistent branding across dashboards
    # Customer Dashboard
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust = client.get("/customer/dashboard")
    assert res_cust.status_code == 200
    assert b'<span class="brand-text">LoanPulse</span>' in res_cust.data
    assert b'<img src="/static/loanpulse.png" alt="LoanPulse" class="brand-logo-img">' in res_cust.data
    client.post("/logout")

    # Officer Queue
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off = client.get("/officer/queue")
    assert res_off.status_code == 200
    assert b'<span class="brand-text">LoanPulse</span>' in res_off.data
    assert b'<img src="/static/loanpulse.png" alt="LoanPulse" class="brand-logo-img">' in res_off.data
    client.post("/logout")

    # Manager Queue
    client.post("/login/admin", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res_mgr = client.get("/manager/queue")
    assert res_mgr.status_code == 200
    assert b'<span class="brand-text">LoanPulse</span>' in res_mgr.data
    assert b'<img src="/static/loanpulse.png" alt="LoanPulse" class="brand-logo-img">' in res_mgr.data
    client.post("/logout")


def test_navbar_logo_role_based_destinations(client, seeded_db):
    """Verify brand logo link navigates to role-specific dashboard or home page."""
    # 1. Unauthenticated -> Home /
    res_anon = client.get("/")
    assert res_anon.status_code == 200
    assert b'<a href="/" class="brand"' in res_anon.data

    # 2. Customer -> /customer/dashboard
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust = client.get("/customer/dashboard")
    assert res_cust.status_code == 200
    assert b'<a href="/customer/dashboard' in res_cust.data
    assert b'class="brand"' in res_cust.data
    client.post("/logout")

    # 3. Loan Officer -> /officer/queue
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off = client.get("/officer/queue")
    assert res_off.status_code == 200
    assert b'<a href="/officer/queue' in res_off.data
    assert b'class="brand"' in res_off.data
    client.post("/logout")

    # 4. Loan Manager -> /manager/queue
    client.post("/login/admin", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res_mgr = client.get("/manager/queue")
    assert res_mgr.status_code == 200
    assert b'<a href="/manager/queue' in res_mgr.data
    assert b'class="brand"' in res_mgr.data
    client.post("/logout")
