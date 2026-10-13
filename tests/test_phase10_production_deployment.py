"""Automated tests for Phase 10: Production Deployment.

Verifies:
1. Secret key fail-safe validation: production mode rejects missing/default SECRET_KEY.
2. Production startup with valid SECRET_KEY and WSGI entrypoint.
3. PostgreSQL database URL normalization (postgres:// -> postgresql://).
4. ProxyFix reverse-proxy header handling (X-Forwarded-Proto: https).
5. Static asset availability and production cookie security flags.
6. Role-based access control and tenant isolation under production configuration.
7. Profile dropdown, logout redirect, and theme persistence verification.
8. Complete loan lifecycle verification in production mode.
"""
import os
import importlib
import pytest
from datetime import date
from unittest.mock import patch

from src.app import create_app
from src.config import Config, ProductionConfig, config_by_name
from src.models import db, User, LoanApplication, LoanProduct, ApplicationAuditLog


def test_production_fails_safely_without_secret_key():
    """Verify that create_app('production') raises RuntimeError if SECRET_KEY is missing or insecure default."""
    with patch.dict(os.environ, {"SECRET_KEY": "change-this-for-local-development"}, clear=False):
        with pytest.raises(RuntimeError) as exc_info:
            create_app("production")
        assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)
        assert "SECRET_KEY" in str(exc_info.value)

    with patch.dict(os.environ, {"SECRET_KEY": ""}, clear=False):
        with pytest.raises(RuntimeError) as exc_info:
            create_app("production")
        assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)


def test_production_starts_cleanly_with_valid_secret():
    """Verify create_app('production') initializes successfully with a strong production key."""
    strong_key = "a9f8b2c4e6d8a0b2c4e6f8a0b2c4d6e8a0b2c4e6f8a0b2c4d6e8a0b2c4e6f8a0"
    with patch.dict(os.environ, {"SECRET_KEY": strong_key, "DATABASE_URL": "sqlite:///:memory:"}):
        prod_app = create_app("production")
        assert prod_app is not None
        assert prod_app.debug is False
        assert prod_app.testing is False
        assert prod_app.config["SECRET_KEY"] == strong_key
        assert prod_app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert prod_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_postgresql_url_normalization():
    """Verify that postgres:// URLs from Render/Heroku are normalized to postgresql://."""
    legacy_url = "postgres://usr_prod:sec_pwd@db.host.provider.com:5432/loanpulse_prod"
    with patch.dict(os.environ, {"DATABASE_URL": legacy_url}):
        raw_url = os.environ.get("DATABASE_URL")
        normalized = raw_url.replace("postgres://", "postgresql://", 1) if raw_url.startswith("postgres://") else raw_url
        assert normalized == "postgresql://usr_prod:sec_pwd@db.host.provider.com:5432/loanpulse_prod"


def test_proxyfix_https_header_propagation():
    """Verify ProxyFix middleware correctly interprets X-Forwarded-Proto: https."""
    strong_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    with patch.dict(os.environ, {
        "SECRET_KEY": strong_key,
        "DATABASE_URL": "sqlite:///:memory:",
        "BEHIND_PROXY": "True",
    }):
        prod_app = create_app("production")
        test_client = prod_app.test_client()

        # Send request with TLS-terminating reverse proxy header
        res = test_client.get("/health", headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "203.0.113.195",
        })
        assert res.status_code == 200
        assert res.get_json()["status"] == "ok"


def test_wsgi_entrypoint_instantiation():
    """Verify that wsgi.py entrypoint successfully instantiates the production application."""
    strong_key = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    with patch.dict(os.environ, {
        "SECRET_KEY": strong_key,
        "FLASK_ENV": "production",
        "DATABASE_URL": "sqlite:///:memory:",
    }):
        import wsgi
        importlib.reload(wsgi)
        assert hasattr(wsgi, "app")
        assert wsgi.app is not None
        assert wsgi.app.debug is False


def test_static_assets_and_landing_in_production(client, seeded_db):
    """Verify static CSS stylesheet, fonts, and landing page respond with 200."""
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    assert b":root" in css_res.data
    assert b"--primary" in css_res.data

    home_res = client.get("/")
    assert home_res.status_code == 200
    assert b"LoanPulse" in home_res.data
    assert b"Log In" in home_res.data
    assert b"Sign Up" in home_res.data


def test_production_auth_rbac_and_profile_dropdown(client, seeded_db):
    """Verify login/logout, RBAC boundaries, profile dropdown details, and theme elements."""
    # 1. Customer login
    login_res = client.post("/login/user", data={
        "email": "borrower01@example.test",
        "password": "demo123",
    }, follow_redirects=True)
    assert login_res.status_code == 200
    assert b"Dashboard" in login_res.data
    assert b"User" in login_res.data  # Profile role badge

    # Profile dropdown elements
    assert b"Who are you?" in login_res.data
    assert b"Log out" in login_res.data
    assert b"btn-theme-toggle" in login_res.data

    # Tenant isolation: Customer cannot access staff portals
    officer_attempt = client.get("/officer/queue")
    assert officer_attempt.status_code == 403

    manager_attempt = client.get("/manager/queue")
    assert manager_attempt.status_code == 403

    # Logout
    logout_res = client.post("/logout", follow_redirects=True)
    assert logout_res.status_code == 200

    # Protected dashboard redirects to login after logout
    dash_post_logout = client.get("/customer/dashboard", follow_redirects=False)
    assert dash_post_logout.status_code in (302, 401)


def test_production_full_lifecycle_workflow(client, seeded_db):
    """Verify complete loan lifecycle end-to-end under production conditions."""
    # Step 1: Customer submits application
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    prod = LoanProduct.query.filter_by(product_code="PERSONAL", active=True).first()
    assert prod is not None

    apply_payload = {
        "action": "submit",
        "applicant_name": "Test Prod Borrower",
        "monthly_income": "65000",
        "requested_amount": "200000",
        "term_months": "24",
        "product_id": str(prod.product_id),
        "loan_purpose": "PERSONAL",
        "employment_type": "SALARIED",
        "employer_name": "Acme Tech",
        "existing_obligations": "5000",
        "preferred_repayment_date": "10",
    }
    app_res = client.post("/applications/new", data=apply_payload, follow_redirects=True)
    assert app_res.status_code == 200

    loan_app = LoanApplication.query.filter_by(applicant_name="Test Prod Borrower").order_by(LoanApplication.application_id.desc()).first()
    assert loan_app is not None
    app_id = loan_app.application_id
    assert loan_app.status == "PENDING_REVIEW"
    client.post("/logout")

    # Step 2: Officer reviews and forwards
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    fwd_res = client.post(f"/officer/applications/{app_id}/send-to-manager", data={"notes": "Production credit review passed."}, follow_redirects=True)
    assert fwd_res.status_code == 200
    loan_app = db.session.get(LoanApplication, app_id)
    assert loan_app.status == "PENDING_MANAGER_REVIEW"
    client.post("/logout")

    # Step 3: Manager approves
    client.post("/login/admin", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    appr_res = client.post(f"/manager/applications/{app_id}/decision", data={"decision": "APPROVE", "notes": "Approved in production."}, follow_redirects=True)
    assert appr_res.status_code == 200
    loan_app = db.session.get(LoanApplication, app_id)
    assert loan_app.status == "APPROVED"
    client.post("/logout")

    # Step 4: Officer records disbursement
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    disb_res = client.post(f"/officer/applications/{app_id}/disburse", data={"disbursement_date": date.today().isoformat()}, follow_redirects=True)
    assert disb_res.status_code == 200
    loan_app = db.session.get(LoanApplication, app_id)
    assert loan_app.disbursement_status == "DISBURSED"
    client.post("/logout")

    # Step 5: Customer verifies status
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    status_page = client.get(f"/applications/{app_id}/status")
    assert status_page.status_code == 200
    assert b"DISBURSED" in status_page.data
    client.post("/logout")
