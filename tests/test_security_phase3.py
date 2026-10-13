"""Security tests for Phase 3 fixes: LP-VULN-03 and LP-VULN-10.

Covers:
- LP-VULN-03: Segregation and redaction of confidential staff review notes and internal audit metadata from customer-facing responses.
- LP-VULN-10: Repository .dockerignore configuration to prevent bundling of secrets, test databases, and local assets into Docker images.
"""
from datetime import date, datetime
from pathlib import Path
import pytest

from src.models import db, User, LoanApplication, ApplicationAuditLog


def login_as(client, email, password="demo123"):
    """Helper to authenticate test clients."""
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ============================================================================
# LP-VULN-03: Internal Review Notes & Audit Trail Exposure Tests
# ============================================================================

def test_customer_status_json_does_not_leak_internal_review_notes(client, seeded_db):
    """LP-VULN-03: Customer status JSON endpoint must not disclose internal review notes during review."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-01",
        customer_id=customer.user_id,
        applicant_name="Privacy Test Applicant",
        monthly_income=80000.0,
        requested_amount=200000.0,
        term_months=24,
        status="UNDER_REVIEW",
        review_notes="Confidential underwriting note: flagged for high credit exposure.",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    login_as(client, customer.email)
    res = client.get(f"/applications/{app.application_id}/status", headers={"Accept": "application/json"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["review_notes"] is None


def test_customer_status_json_includes_notes_when_documents_required(client, seeded_db):
    """LP-VULN-03: Customer status JSON endpoint must provide instructions when documents are required."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-02",
        customer_id=customer.user_id,
        applicant_name="Doc Request Applicant",
        monthly_income=80000.0,
        requested_amount=200000.0,
        term_months=24,
        status="DOCUMENTS_REQUIRED",
        review_notes="Please provide your latest 3 months salary slips and utility bill.",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    login_as(client, customer.email)
    res = client.get(f"/applications/{app.application_id}/status", headers={"Accept": "application/json"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["review_notes"] == "Please provide your latest 3 months salary slips and utility bill."


def test_staff_status_json_retains_review_notes(client, seeded_db):
    """LP-VULN-03: Staff accessing application status JSON should still see complete review notes."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-03",
        customer_id=customer.user_id,
        applicant_name="Staff View Applicant",
        monthly_income=80000.0,
        requested_amount=200000.0,
        term_months=24,
        status="UNDER_REVIEW",
        review_notes="Internal underwriting observation: check employer verification.",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    login_as(client, officer.email)
    res = client.get(f"/applications/{app.application_id}/status", headers={"Accept": "application/json"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["review_notes"] == "Internal underwriting observation: check employer verification."


def test_customer_status_html_does_not_leak_review_notes_on_rejection(client, seeded_db):
    """LP-VULN-03: Rejection banner must not leak internal review notes when rejection_reason is empty."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-04",
        customer_id=customer.user_id,
        applicant_name="Rejection Leak Target",
        monthly_income=40000.0,
        requested_amount=300000.0,
        term_months=36,
        status="REJECTED",
        review_notes="Suspected forged bank statement; high AML risk flag.",
        rejection_reason=None,
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    login_as(client, customer.email)
    res = client.get(f"/applications/{app.application_id}/status")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Suspected forged bank statement" not in html
    assert "high AML risk flag" not in html


def test_customer_status_html_redacts_staff_names_in_audit_log(client, seeded_db):
    """LP-VULN-03: Audit log view for customers must mask staff personal names with role labels."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-05",
        customer_id=customer.user_id,
        applicant_name="Audit Mask Applicant",
        monthly_income=70000.0,
        requested_amount=150000.0,
        term_months=12,
        status="UNDER_REVIEW",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    # Customer submission audit log
    cust_log = ApplicationAuditLog(
        application_id=app.application_id,
        actor_id=customer.user_id,
        actor_name="Jane Borrower",
        actor_role="CUSTOMER",
        from_status="NEW",
        to_status="PENDING_REVIEW",
        action="SUBMITTED",
        notes="Application submitted by borrower.",
        created_at=datetime.utcnow(),
    )
    # Staff officer transition audit log
    staff_log = ApplicationAuditLog(
        application_id=app.application_id,
        actor_id=officer.user_id,
        actor_name="Agent Sarah Officer",
        actor_role="LOAN_OFFICER",
        from_status="PENDING_REVIEW",
        to_status="UNDER_REVIEW",
        action="TRANSITION_TO_UNDER_REVIEW",
        notes="Internal check started.",
        created_at=datetime.utcnow(),
    )
    seeded_db.add_all([cust_log, staff_log])
    seeded_db.commit()

    login_as(client, customer.email)
    res = client.get(f"/applications/{app.application_id}/status")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Staff name must not be present
    assert "Agent Sarah Officer" not in html
    # Generic role label must appear for staff
    assert "Loan Officer" in html
    # Borrower's own name can be present
    assert "Jane Borrower" in html


def test_customer_status_html_excludes_internal_note_added_audit_logs(client, seeded_db):
    """LP-VULN-03: NOTE_ADDED audit log events and internal notes must not appear in customer audit view."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-06",
        customer_id=customer.user_id,
        applicant_name="Internal Note Mask Target",
        monthly_income=60000.0,
        requested_amount=100000.0,
        term_months=12,
        status="UNDER_REVIEW",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    secret_note = "Confidential: Applicant has an unverified personal loan from another lender."
    note_log = ApplicationAuditLog(
        application_id=app.application_id,
        actor_id=officer.user_id,
        actor_name="Secret Officer",
        actor_role="LOAN_OFFICER",
        from_status="UNDER_REVIEW",
        to_status="UNDER_REVIEW",
        action="NOTE_ADDED",
        notes=secret_note,
        created_at=datetime.utcnow(),
    )
    seeded_db.add(note_log)
    seeded_db.commit()

    login_as(client, customer.email)
    res = client.get(f"/applications/{app.application_id}/status")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert secret_note not in html
    assert "NOTE_ADDED" not in html


def test_customer_status_html_redacts_internal_transition_notes(client, seeded_db):
    """LP-VULN-03: Sensitive comments attached to state transitions must not leak to customers."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-07",
        customer_id=customer.user_id,
        applicant_name="Transition Note Target",
        monthly_income=70000.0,
        requested_amount=150000.0,
        term_months=12,
        status="UNDER_REVIEW",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    internal_transition_comment = "Underwriting override: DTI threshold exception requested for review."
    trans_log = ApplicationAuditLog(
        application_id=app.application_id,
        actor_id=officer.user_id,
        actor_name="Senior Underwriter",
        actor_role="LOAN_OFFICER",
        from_status="PENDING_REVIEW",
        to_status="UNDER_REVIEW",
        action="TRANSITION_TO_UNDER_REVIEW",
        notes=internal_transition_comment,
        created_at=datetime.utcnow(),
    )
    seeded_db.add(trans_log)
    seeded_db.commit()

    login_as(client, customer.email)
    res = client.get(f"/applications/{app.application_id}/status")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert internal_transition_comment not in html


def test_staff_review_retains_full_audit_trail_and_notes(client, seeded_db):
    """LP-VULN-03: Officer review page must continue to show complete audit trail and notes for staff."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()
    app = LoanApplication(
        application_id="APP-SEC-NOTE-08",
        customer_id=customer.user_id,
        applicant_name="Staff Audit Test Applicant",
        monthly_income=70000.0,
        requested_amount=150000.0,
        term_months=12,
        status="UNDER_REVIEW",
        review_notes="Underwriter observation note for staff.",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    staff_note_log = ApplicationAuditLog(
        application_id=app.application_id,
        actor_id=officer.user_id,
        actor_name="Review Officer John",
        actor_role="LOAN_OFFICER",
        from_status="UNDER_REVIEW",
        to_status="UNDER_REVIEW",
        action="NOTE_ADDED",
        notes="Internal staff note should be visible to officers.",
        created_at=datetime.utcnow(),
    )
    seeded_db.add(staff_note_log)
    seeded_db.commit()

    login_as(client, officer.email)
    res = client.get(f"/officer/applications/{app.application_id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Review Officer John" in html
    assert "Internal staff note should be visible to officers." in html


# ============================================================================
# LP-VULN-10: .dockerignore Configuration Tests
# ============================================================================

def test_dockerignore_configuration():
    """LP-VULN-10: Verify .dockerignore exists and excludes secrets, SQLite DBs, and local uploads."""
    repo_root = Path(__file__).resolve().parent.parent
    dockerignore_path = repo_root / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore must exist in repository root"

    content = dockerignore_path.read_text().splitlines()
    cleaned_lines = [line.strip() for line in content if line.strip() and not line.startswith("#")]

    required_patterns = [
        ".env*",
        "*.db",
        "*.sqlite",
        "uploads/",
        ".git",
        "__pycache__/",
    ]
    for pattern in required_patterns:
        assert any(pattern in line for line in cleaned_lines), f"Missing required pattern '{pattern}' in .dockerignore"
