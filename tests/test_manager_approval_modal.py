"""Automated test suite for Manager In-Page Loan Approval Confirmation Modal."""
import pytest
from src.models import db, User, LoanApplication, ApplicationAuditLog


def login_as(client, email="manager01@example.test", password="demo123"):
    """Helper to authenticate manager session."""
    return client.post("/login/admin", data={"email": email, "password": password}, follow_redirects=True)


def test_manager_review_page_renders_in_page_approval_modal(client, seeded_db):
    """Verify manager review page renders the accessible in-page approval modal instead of browser confirm."""
    login_as(client)

    # 1. Fetch an application pending manager decision
    app = seeded_db.query(LoanApplication).filter_by(status="PENDING_MANAGER_REVIEW").first()
    assert app is not None, "Seeded database should contain a PENDING_MANAGER_REVIEW application"

    res = client.get(f"/manager/applications/{app.application_id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # 2. Verify trigger button
    assert 'id="btnOpenApproveModal"' in html
    assert "Approve Loan" in html

    # 3. Verify in-page modal dialog semantics & accessibility
    assert 'id="approveConfirmModal"' in html
    assert 'class="modal-backdrop"' in html
    assert 'class="modal-dialog"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert 'aria-labelledby="approveModalTitle"' in html
    assert 'aria-describedby="approveModalDesc"' in html

    # 4. Verify modal contents per design specification
    assert "Approve This Loan?" in html
    assert "Are you sure you want to approve this loan application? Please review the application details before confirming." in html
    assert 'id="btnApproveModalCancel"' in html
    assert "Cancel" in html
    assert 'id="btnApproveModalConfirm"' in html
    assert 'id="btnApproveModalClose"' in html

    # 5. Verify the approval action no longer uses browser-native confirm()
    # There should NOT be an onsubmit="return confirm(...approve...)" or confirm for approve
    assert 'confirm(\'Are you sure you want to approve' not in html
    assert 'confirm("Are you sure you want to approve' not in html
    assert 'handleDecisionSubmit(this, \'APPROVE\')' not in html

    # 6. Verify form details
    assert 'id="managerApproveForm"' in html
    assert f'action="/manager/applications/{app.application_id}/decision"' in html
    assert 'name="decision" value="APPROVE"' in html
    assert 'name="notes"' in html
    assert 'name="csrf_token"' in html


def test_manager_approval_submission_with_decision_notes(client, seeded_db):
    """Verify submitting the approval form updates application to APPROVED with notes and audit log."""
    login_as(client)

    app = seeded_db.query(LoanApplication).filter_by(status="PENDING_MANAGER_REVIEW").first()
    assert app is not None

    approval_notes = "Approved under standard prime underwriting guidelines."
    res = client.post(
        f"/manager/applications/{app.application_id}/decision",
        data={"decision": "APPROVE", "notes": approval_notes},
        follow_redirects=True,
    )
    assert res.status_code == 200

    # Verify state in DB
    seeded_db.refresh(app)
    assert app.status == "APPROVED"
    assert app.approved_amount == app.requested_amount
    assert app.disbursement_status == "NOT_DISBURSED"

    # Verify audit log
    audit = (
        seeded_db.query(ApplicationAuditLog)
        .filter_by(application_id=app.application_id, action="MANAGER_APPROVED")
        .first()
    )
    assert audit is not None
    assert audit.notes == approval_notes


def test_manager_approval_security_and_role_authorization(client, seeded_db):
    """Verify non-managers (customer and officer) are blocked from approving applications (403 Forbidden)."""
    app = seeded_db.query(LoanApplication).filter_by(status="PENDING_MANAGER_REVIEW").first()
    assert app is not None

    # 1. Customer blocked
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust = client.post(
        f"/manager/applications/{app.application_id}/decision",
        data={"decision": "APPROVE", "notes": "Hacked approval attempt"},
    )
    assert res_cust.status_code == 403
    client.post("/logout")

    # 2. Officer blocked
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off = client.post(
        f"/manager/applications/{app.application_id}/decision",
        data={"decision": "APPROVE", "notes": "Officer cannot approve"},
    )
    assert res_off.status_code == 403
    client.post("/logout")
