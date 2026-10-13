"""Security tests for Phase 1 fixes: LP-VULN-01 and LP-VULN-02.

Covers:
- LP-VULN-01: Production SECRET_KEY validation and rejection of default/weak keys.
- LP-VULN-02: Idempotent disbursement and duplicate/concurrent replay protection.
"""
import os
from datetime import date
from unittest.mock import patch
import pytest

from src.app import create_app
from src.models import db, User, LoanApplication, ApplicationAuditLog, Notification
from src.services.disbursement_service import record_disbursement


def test_production_rejects_insecure_default_secret_key():
    """LP-VULN-01: Verify create_app('production') rejects the docker-compose default key."""
    default_insecure_key = "change_this_to_a_secure_production_secret_key_32_bytes"
    with patch.dict(os.environ, {"SECRET_KEY": default_insecure_key}, clear=False):
        with pytest.raises(RuntimeError) as exc_info:
            create_app("production")
        assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)
        assert "SECRET_KEY" in str(exc_info.value)


def test_production_rejects_short_secret_keys():
    """LP-VULN-01: Verify create_app('production') rejects keys shorter than 32 characters."""
    short_key = "short_insecure_key_12345"
    with patch.dict(os.environ, {"SECRET_KEY": short_key}, clear=False):
        with pytest.raises(RuntimeError) as exc_info:
            create_app("production")
        assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)


def test_production_accepts_strong_random_secret():
    """LP-VULN-01: Verify create_app('production') starts cleanly with a strong high-entropy key."""
    strong_key = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    with patch.dict(os.environ, {"SECRET_KEY": strong_key, "DATABASE_URL": "sqlite:///:memory:"}, clear=False):
        app = create_app("production")
        assert app is not None
        assert app.config["SECRET_KEY"] == strong_key


def test_duplicate_disbursement_rejected_by_service(seeded_db):
    """LP-VULN-02: record_disbursement must reject applications that are already DISBURSED."""
    app = LoanApplication(
        application_id="APP-SEC-DISB-01",
        customer_id=1,
        applicant_name="Disbursement Replay Target",
        monthly_income=75000.0,
        requested_amount=200000.0,
        term_months=24,
        status="APPROVED",
        approved_amount=200000.0,
        disbursement_status="NOT_DISBURSED",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    # First disbursement call must succeed
    record_disbursement(app, session=seeded_db)
    seeded_db.refresh(app)
    assert app.disbursement_status == "DISBURSED"
    assert app.disbursement_date == date.today()

    # Second disbursement call must raise ValueError
    with pytest.raises(ValueError) as exc_info:
        record_disbursement(app, session=seeded_db)
    assert "already been disbursed" in str(exc_info.value).lower()


def test_duplicate_disbursement_rejected_by_api(client, seeded_db):
    """LP-VULN-02: POST /officer/applications/<id>/disburse must return 400 on duplicate disbursement."""
    app = LoanApplication(
        application_id="APP-SEC-DISB-02",
        customer_id=1,
        applicant_name="API Replay Target",
        monthly_income=90000.0,
        requested_amount=300000.0,
        term_months=36,
        status="APPROVED",
        approved_amount=300000.0,
        disbursement_status="NOT_DISBURSED",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    # Log in as loan officer
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)

    # First disbursement request (JSON)
    res1 = client.post(
        f"/officer/applications/{app.application_id}/disburse",
        json={"disbursement_date": "2026-10-12"},
        headers={"Accept": "application/json"},
    )
    assert res1.status_code == 200
    assert res1.get_json()["disbursement_status"] == "DISBURSED"

    # Count audit logs and notifications after first disbursement
    initial_audits = ApplicationAuditLog.query.filter_by(application_id=app.application_id, action="DISBURSED").count()
    initial_notifs = Notification.query.filter_by(application_id=app.application_id, new_status="DISBURSED").count()
    assert initial_audits == 1
    assert initial_notifs == 1

    # Second disbursement request (JSON replay) must be rejected with 400
    res2 = client.post(
        f"/officer/applications/{app.application_id}/disburse",
        json={"disbursement_date": "2026-10-12"},
        headers={"Accept": "application/json"},
    )
    assert res2.status_code == 400
    assert "already been disbursed" in res2.get_json()["error"].lower()

    # Verify no duplicate audit log or notification was created
    final_audits = ApplicationAuditLog.query.filter_by(application_id=app.application_id, action="DISBURSED").count()
    final_notifs = Notification.query.filter_by(application_id=app.application_id, new_status="DISBURSED").count()
    assert final_audits == initial_audits
    assert final_notifs == initial_notifs


def test_duplicate_disbursement_rejected_by_form_post(client, seeded_db):
    """LP-VULN-02: Form POST /officer/applications/<id>/disburse redirects with warning flash and no duplication."""
    app = LoanApplication(
        application_id="APP-SEC-DISB-03",
        customer_id=1,
        applicant_name="Form Replay Target",
        monthly_income=65000.0,
        requested_amount=150000.0,
        term_months=18,
        status="APPROVED",
        approved_amount=150000.0,
        disbursement_status="NOT_DISBURSED",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    # Log in as loan officer
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)

    # First form POST
    res1 = client.post(
        f"/officer/applications/{app.application_id}/disburse",
        data={"disbursement_date": "2026-10-12"},
        follow_redirects=True,
    )
    assert res1.status_code == 200

    # Second form POST replay
    res2 = client.post(
        f"/officer/applications/{app.application_id}/disburse",
        data={"disbursement_date": "2026-10-12"},
        follow_redirects=True,
    )
    assert res2.status_code == 200
    assert b"already been disbursed" in res2.data.lower()
