"""Security tests for Phase 2 fixes: LP-VULN-04 and LP-VULN-05.

Covers:
- LP-VULN-04: User-scoped notification updates and prevention of cross-tenant / staff notification wipes.
- LP-VULN-05: Server-side validation of loan product requirements, active status, amount caps, and tenure limits.
"""
from datetime import date
import pytest

from src.models import db, User, LoanApplication, LoanProduct, Notification


def login_as(client, email, password="demo123"):
    """Helper to authenticate test clients."""
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ============================================================================
# LP-VULN-04: Notification Scoping Tests
# ============================================================================

def test_staff_cannot_mark_customer_notifications_read(client, seeded_db):
    """LP-VULN-04: Staff triggering /notifications/mark-read must not clear customer unread notifications."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()

    # Create an unread notification for the customer
    cust_notif = Notification(
        application_id="APP-0001",
        recipient_user_id=customer.user_id,
        old_status="UNDER_REVIEW",
        new_status="APPROVED",
        message="Your application was approved.",
        created_at=date.today(),
        is_read=False,
    )
    seeded_db.add(cust_notif)
    seeded_db.commit()

    # Log in as loan officer and trigger mark-read
    login_as(client, officer.email)
    res = client.post("/notifications/mark-read", headers={"Accept": "application/json"})
    assert res.status_code == 200

    # Customer's notification must remain unread
    seeded_db.refresh(cust_notif)
    assert cust_notif.is_read is False


def test_user_cannot_mark_another_users_notification_read(client, seeded_db):
    """LP-VULN-04: A user cannot mark another user's notification as read by supplying its ID."""
    customers = seeded_db.query(User).filter_by(role="CUSTOMER").limit(2).all()
    assert len(customers) >= 2
    user_a, user_b = customers[0], customers[1]

    # Create unread notification for user A
    notif_a = Notification(
        application_id="APP-0001",
        recipient_user_id=user_a.user_id,
        old_status="DRAFT",
        new_status="PENDING_REVIEW",
        message="Notification for User A",
        created_at=date.today(),
        is_read=False,
    )
    seeded_db.add(notif_a)
    seeded_db.commit()

    # Log in as user B and attempt to mark user A's notification as read
    login_as(client, user_b.email)
    res = client.post(
        "/notifications/mark-read",
        json={"notification_ids": [notif_a.notification_id]},
        headers={"Accept": "application/json"},
    )
    assert res.status_code == 200

    # User A's notification must remain unread
    seeded_db.refresh(notif_a)
    assert notif_a.is_read is False


def test_customer_can_mark_own_notifications_read(client, seeded_db):
    """LP-VULN-04: Customers can mark their own notifications as read."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()

    own_notif = Notification(
        application_id="APP-0001",
        recipient_user_id=customer.user_id,
        old_status="PENDING_REVIEW",
        new_status="UNDER_REVIEW",
        message="Your application is under review.",
        created_at=date.today(),
        is_read=False,
    )
    seeded_db.add(own_notif)
    seeded_db.commit()

    login_as(client, customer.email)
    res = client.post("/notifications/mark-read", headers={"Accept": "application/json"})
    assert res.status_code == 200

    seeded_db.refresh(own_notif)
    assert own_notif.is_read is True


# ============================================================================
# LP-VULN-05: Loan Product Validation Tests
# ============================================================================

def test_application_rejected_without_product_id(client, seeded_db):
    """LP-VULN-05: Application submission without product_id must be rejected."""
    login_as(client, "borrower01@example.test")

    payload = {
        "applicant_name": "Test Borrower",
        "monthly_income": "75000",
        "requested_amount": "150000",
        "term_months": "24",
        "action": "submit",
        # product_id intentionally omitted
    }

    res = client.post("/applications/new", json=payload, headers={"Accept": "application/json"})
    assert res.status_code == 400
    data = res.get_json()
    assert "errors" in data
    assert "product_id" in data["errors"]
    assert "valid loan product must be selected" in data["errors"]["product_id"].lower()


def test_application_rejected_with_invalid_product_id(client, seeded_db):
    """LP-VULN-05: Application submission with non-existent or malformed product_id must be rejected."""
    login_as(client, "borrower01@example.test")

    # Non-existent product ID
    payload_bad_id = {
        "applicant_name": "Test Borrower",
        "monthly_income": "75000",
        "requested_amount": "150000",
        "term_months": "24",
        "product_id": "99999",
        "action": "submit",
    }
    res1 = client.post("/applications/new", json=payload_bad_id, headers={"Accept": "application/json"})
    assert res1.status_code == 400
    assert "does not exist" in res1.get_json()["errors"]["product_id"].lower()

    # Non-integer product ID
    payload_alpha = dict(payload_bad_id, product_id="invalid_code")
    res2 = client.post("/applications/new", json=payload_alpha, headers={"Accept": "application/json"})
    assert res2.status_code == 400
    assert "integer" in res2.get_json()["errors"]["product_id"].lower()


def test_application_rejected_with_inactive_product(client, seeded_db):
    """LP-VULN-05: Application submission for an inactive product must be rejected."""
    inactive_prod = LoanProduct(
        product_code="LP-INACTIVE-TEST",
        product_name="Inactive Special Loan",
        description="Disabled product",
        min_amount=10000.0,
        max_amount=200000.0,
        min_term_months=12,
        max_term_months=36,
        annual_interest_rate=12.0,
        min_monthly_income=30000.0,
        max_loan_to_income_ratio=0.5,
        active=False,
    )
    seeded_db.add(inactive_prod)
    seeded_db.commit()

    login_as(client, "borrower01@example.test")

    payload = {
        "applicant_name": "Test Borrower",
        "monthly_income": "75000",
        "requested_amount": "100000",
        "term_months": "24",
        "product_id": str(inactive_prod.product_id),
        "action": "submit",
    }

    res = client.post("/applications/new", json=payload, headers={"Accept": "application/json"})
    assert res.status_code == 400
    assert "inactive" in res.get_json()["errors"]["product_id"].lower()


def test_application_rejected_when_amount_outside_product_limits(client, seeded_db):
    """LP-VULN-05: Application amount must conform to product min and max bounds."""
    product = seeded_db.query(LoanProduct).filter_by(active=True).first()
    login_as(client, "borrower01@example.test")

    # Exceeds maximum amount
    payload_too_high = {
        "applicant_name": "Test Borrower",
        "monthly_income": "150000",
        "requested_amount": str(product.max_amount + 50000.0),
        "term_months": str(product.min_term_months),
        "product_id": str(product.product_id),
        "action": "submit",
    }
    res_high = client.post("/applications/new", json=payload_too_high, headers={"Accept": "application/json"})
    assert res_high.status_code == 400
    assert "exceeds maximum allowed limit" in res_high.get_json()["errors"]["requested_amount"].lower()

    # Below minimum amount
    payload_too_low = dict(payload_too_high, requested_amount=str(max(1.0, product.min_amount - 1000.0)))
    res_low = client.post("/applications/new", json=payload_too_low, headers={"Accept": "application/json"})
    assert res_low.status_code == 400
    assert "below the minimum limit" in res_low.get_json()["errors"]["requested_amount"].lower()


def test_application_rejected_when_tenure_outside_product_limits(client, seeded_db):
    """LP-VULN-05: Application tenure must conform to product min and max bounds."""
    product = seeded_db.query(LoanProduct).filter_by(active=True).first()
    login_as(client, "borrower01@example.test")

    # Exceeds maximum tenure
    payload_too_long = {
        "applicant_name": "Test Borrower",
        "monthly_income": "75000",
        "requested_amount": str(product.min_amount + 10000.0),
        "term_months": str(product.max_term_months + 12),
        "product_id": str(product.product_id),
        "action": "submit",
    }
    res_long = client.post("/applications/new", json=payload_too_long, headers={"Accept": "application/json"})
    assert res_long.status_code == 400
    assert "exceeds the maximum allowed" in res_long.get_json()["errors"]["term_months"].lower()

    # Below minimum tenure
    payload_too_short = dict(payload_too_long, term_months=str(max(1, product.min_term_months - 6)))
    res_short = client.post("/applications/new", json=payload_too_short, headers={"Accept": "application/json"})
    assert res_short.status_code == 400
    assert "below the minimum allowed" in res_short.get_json()["errors"]["term_months"].lower()


def test_valid_product_application_submission_succeeds(client, seeded_db):
    """LP-VULN-05: Valid product selection within limits creates application successfully."""
    product = seeded_db.query(LoanProduct).filter_by(active=True).first()
    valid_amount = (product.min_amount + product.max_amount) / 2
    valid_term = product.min_term_months

    login_as(client, "borrower01@example.test")

    payload = {
        "applicant_name": "Valid Borrower",
        "monthly_income": "80000",
        "requested_amount": str(valid_amount),
        "term_months": str(valid_term),
        "product_id": str(product.product_id),
        "employment_type": "SALARIED",
        "employer_name": "Apex Finance",
        "existing_obligations": "0",
        "preferred_repayment_date": "10",
        "action": "submit",
    }

    res = client.post("/applications/new", data=payload, follow_redirects=True)
    assert res.status_code == 200

    created = seeded_db.query(LoanApplication).filter_by(applicant_name="Valid Borrower").order_by(LoanApplication.created_at.desc()).first()
    assert created is not None
    assert created.product_id == product.product_id
    assert created.status == "PENDING_REVIEW"
