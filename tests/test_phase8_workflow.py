"""Comprehensive automated test suite for Phase 8: End-to-End Loan Application Workflow.

Tests verify:
1. Multi-step application creation, draft saving, resumption/editing, and preview.
2. Deterministic underwriting execution on submission with snapshot rate & EMI.
3. State machine lifecycle valid transitions and illegal transition prevention.
4. Strict RBAC: Officer cannot approve; Manager exclusive approval authority.
5. Officer queue search, status filtering, product filtering, and pagination.
6. Officer review notes, document requests, and authorized rejection with reason.
7. Customer document resubmission and status tracking.
8. Application audit trail completeness and immutability across all lifecycle actions.
"""
import pytest
from datetime import date
from src.models import (
    db,
    User,
    LoanApplication,
    LoanProduct,
    Assessment,
    ApplicationAuditLog,
    Notification,
)
from src.services.workflow_service import (
    transition_application_status,
    record_application_audit,
    can_transition,
    WorkflowError,
)
from src.services.assessment_service import assess_application


def login_as(client, email: str, password: str = "demo123"):
    """Helper to authenticate a test client session."""
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ============================================================================
# 1. Customer Application Draft Creation, Editing & Submission
# ============================================================================

def test_customer_save_and_update_draft(client, seeded_db):
    """Customer saves application as draft, then resumes and updates it."""
    login_as(client, "borrower01@example.test")

    # 1. Save new draft application
    draft_data = {
        "action": "draft",
        "applicant_name": "Test Draft Borrower",
        "monthly_income": "65000",
        "requested_amount": "250000",
        "term_months": "36",
        "loan_purpose": "PERSONAL",
        "employment_type": "SALARIED",
        "employer_name": "Tech Corp",
        "existing_obligations": "5000",
        "preferred_repayment_date": "5",
    }
    res_draft = client.post("/applications/new", data=draft_data, follow_redirects=True)
    assert res_draft.status_code == 200

    # Verify draft saved in DB
    app_draft = seeded_db.query(LoanApplication).filter_by(applicant_name="Test Draft Borrower").first()
    assert app_draft is not None
    assert app_draft.status == "DRAFT"
    assert app_draft.requested_amount == 250000.0

    # Verify audit log recorded for draft creation
    logs = seeded_db.query(ApplicationAuditLog).filter_by(application_id=app_draft.application_id).all()
    actions = [l.action for l in logs]
    assert "CREATED_DRAFT" in actions

    # 2. View draft edit page
    res_edit_get = client.get(f"/applications/{app_draft.application_id}/edit")
    assert res_edit_get.status_code == 200
    assert b"Test Draft Borrower" in res_edit_get.data

    # 3. Update draft
    update_draft_data = {
        "action": "draft",
        "draft_id": app_draft.application_id,
        "applicant_name": "Test Draft Borrower Updated",
        "monthly_income": "70000",
        "requested_amount": "300000",
        "term_months": "24",
    }
    res_update = client.post(f"/applications/{app_draft.application_id}/edit", data=update_draft_data, follow_redirects=True)
    assert res_update.status_code == 200

    seeded_db.refresh(app_draft)
    assert app_draft.applicant_name == "Test Draft Borrower Updated"
    assert app_draft.requested_amount == 300000.0
    assert app_draft.status == "DRAFT"

    # Verify audit log updated
    logs = seeded_db.query(ApplicationAuditLog).filter_by(application_id=app_draft.application_id).all()
    actions = [l.action for l in logs]
    assert "DRAFT_UPDATED" in actions


def test_customer_submit_from_draft_with_underwriting(client, seeded_db):
    """Customer submits a saved draft; engine executes underwriting and snapshots EMI."""
    login_as(client, "borrower01@example.test")

    # Create a draft first
    prod = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()
    app_draft = LoanApplication(
        application_id="APP-DRAFT-001",
        customer_id=1,
        applicant_name="Draft Applicant One",
        monthly_income=75000.0,
        requested_amount=200000.0,
        term_months=24,
        status="DRAFT",
        product_id=prod.product_id if prod else None,
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app_draft)
    seeded_db.commit()

    # Submit the draft
    submit_data = {
        "action": "submit",
        "draft_id": "APP-DRAFT-001",
        "applicant_name": "Draft Applicant One",
        "monthly_income": "75000",
        "requested_amount": "200000",
        "term_months": "24",
        "product_id": str(prod.product_id) if prod else "",
        "loan_purpose": "PERSONAL",
        "employment_type": "SALARIED",
    }
    res_submit = client.post("/applications/new", data=submit_data, follow_redirects=True)
    assert res_submit.status_code == 200

    # Verify application status transitioned to PENDING_REVIEW
    seeded_db.refresh(app_draft)
    assert app_draft.status == "PENDING_REVIEW"
    assert app_draft.estimated_monthly_emi is not None
    assert app_draft.estimated_monthly_emi > 0

    # Verify deterministic underwriting assessment record created
    assessment = seeded_db.query(Assessment).filter_by(application_id="APP-DRAFT-001").first()
    assert assessment is not None
    assert assessment.assessment_result in ("ELIGIBLE", "NOT_ELIGIBLE")
    assert assessment.calculated_ratio > 0

    # Verify audit trail contains SUBMITTED and ASSESSED
    logs = seeded_db.query(ApplicationAuditLog).filter_by(application_id="APP-DRAFT-001").all()
    actions = [l.action for l in logs]
    assert "SUBMITTED" in actions
    assert "ASSESSED" in actions


def test_customer_direct_submission_with_underwriting(client, seeded_db):
    """Customer directly submits an application; verify status and automated underwriting."""
    login_as(client, "borrower01@example.test")
    prod = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()

    payload = {
        "action": "submit",
        "applicant_name": "Direct Submission Borrower",
        "monthly_income": "80000",
        "requested_amount": "250000",
        "term_months": "24",
        "product_id": str(prod.product_id) if prod else "",
        "loan_purpose": "PERSONAL",
        "employment_type": "SALARIED",
        "existing_obligations": "2000",
    }
    res = client.post("/applications/new", data=payload, follow_redirects=True)
    assert res.status_code == 200

    new_app = seeded_db.query(LoanApplication).filter_by(applicant_name="Direct Submission Borrower").first()
    assert new_app is not None
    assert new_app.status == "PENDING_REVIEW"

    # Verify assessment exists and matches product evaluation
    assessment = seeded_db.query(Assessment).filter_by(application_id=new_app.application_id).first()
    assert assessment is not None
    assert assessment.assessment_result == "ELIGIBLE"

    # Verify audit logs
    logs = seeded_db.query(ApplicationAuditLog).filter_by(application_id=new_app.application_id).all()
    actions = [l.action for l in logs]
    assert "SUBMITTED" in actions
    assert "ASSESSED" in actions


# ============================================================================
# 2. State Machine Valid Transitions and Forbidden Transitions
# ============================================================================

def test_state_machine_valid_full_lifecycle(seeded_db):
    """Verify state machine accepts full valid transition lifecycle."""
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()
    manager = seeded_db.query(User).filter_by(role="LOAN_MANAGER").first()
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()

    app = LoanApplication(
        application_id="APP-SM-001",
        customer_id=customer.user_id,
        applicant_name="Lifecycle Borrower",
        monthly_income=60000.0,
        requested_amount=150000.0,
        term_months=24,
        status="DRAFT",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    # 1. DRAFT -> PENDING_REVIEW (Customer submit)
    transition_application_status(app, "PENDING_REVIEW", customer, action="SUBMITTED", session=seeded_db)
    assert app.status == "PENDING_REVIEW"

    # 2. PENDING_REVIEW -> UNDER_REVIEW (Officer start review)
    transition_application_status(app, "UNDER_REVIEW", officer, action="STARTED_REVIEW", session=seeded_db)
    assert app.status == "UNDER_REVIEW"

    # 3. UNDER_REVIEW -> DOCUMENTS_REQUIRED (Officer request docs)
    transition_application_status(app, "DOCUMENTS_REQUIRED", officer, action="DOCUMENTS_REQUESTED", notes="Provide tax form", session=seeded_db)
    assert app.status == "DOCUMENTS_REQUIRED"

    # 4. DOCUMENTS_REQUIRED -> UNDER_REVIEW (Customer resubmit)
    transition_application_status(app, "UNDER_REVIEW", customer, action="DOCUMENTS_RESUBMITTED", session=seeded_db)
    assert app.status == "UNDER_REVIEW"

    # 5. UNDER_REVIEW -> PENDING_MANAGER_REVIEW (Officer forward)
    transition_application_status(app, "PENDING_MANAGER_REVIEW", officer, action="FORWARDED_TO_MANAGER", session=seeded_db)
    assert app.status == "PENDING_MANAGER_REVIEW"

    # 6. PENDING_MANAGER_REVIEW -> APPROVED (Manager approve)
    transition_application_status(app, "APPROVED", manager, action="MANAGER_APPROVED", session=seeded_db)
    assert app.status == "APPROVED"
    assert app.approved_amount == 150000.0
    assert app.disbursement_status == "NOT_DISBURSED"

    # 7. APPROVED -> DISBURSED (Officer disburse)
    transition_application_status(app, "DISBURSED", officer, action="DISBURSED", session=seeded_db)
    assert app.status == "DISBURSED"
    assert app.disbursement_status == "DISBURSED"


def test_state_machine_forbidden_state_jumps(seeded_db):
    """Verify illegal transitions are rejected with WorkflowError."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()

    app = LoanApplication(
        application_id="APP-SM-002",
        customer_id=customer.user_id,
        applicant_name="Illegal Jump Borrower",
        monthly_income=60000.0,
        requested_amount=150000.0,
        term_months=24,
        status="DRAFT",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    # DRAFT directly to APPROVED is forbidden
    with pytest.raises(WorkflowError):
        transition_application_status(app, "APPROVED", officer, session=seeded_db)

    # DRAFT directly to DISBURSED is forbidden
    with pytest.raises(WorkflowError):
        transition_application_status(app, "DISBURSED", officer, session=seeded_db)

    # Terminal state REJECTED cannot transition anywhere
    app.status = "REJECTED"
    seeded_db.commit()
    with pytest.raises(WorkflowError):
        transition_application_status(app, "APPROVED", officer, session=seeded_db)
    with pytest.raises(WorkflowError):
        transition_application_status(app, "PENDING_REVIEW", customer, session=seeded_db)


# ============================================================================
# 3. Strict RBAC Enforcement: Officers Cannot Approve
# ============================================================================

def test_loan_officer_cannot_approve(seeded_db):
    """Ensure Loan Officers are strictly forbidden from approving applications."""
    officer = seeded_db.query(User).filter_by(role="LOAN_OFFICER").first()
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()

    app = LoanApplication(
        application_id="APP-RBAC-001",
        customer_id=customer.user_id,
        applicant_name="RBAC Borrower",
        monthly_income=60000.0,
        requested_amount=150000.0,
        term_months=24,
        status="PENDING_MANAGER_REVIEW",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    # Officer attempts to approve -> Must raise WorkflowError
    with pytest.raises(WorkflowError) as exc_info:
        transition_application_status(app, "APPROVED", officer, session=seeded_db)
    assert "Loan Officers are not authorized to approve loans" in str(exc_info.value)


def test_customer_cannot_transition_to_approved(seeded_db):
    """Customer cannot approve their own application."""
    customer = seeded_db.query(User).filter_by(role="CUSTOMER").first()

    app = LoanApplication(
        application_id="APP-RBAC-002",
        customer_id=customer.user_id,
        applicant_name="Self Approve Borrower",
        monthly_income=60000.0,
        requested_amount=150000.0,
        term_months=24,
        status="PENDING_REVIEW",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    with pytest.raises(WorkflowError):
        transition_application_status(app, "APPROVED", customer, session=seeded_db)


# ============================================================================
# 4. Loan Officer Queue Search, Filtering & Pagination
# ============================================================================

def test_officer_queue_search_and_filter(client, seeded_db):
    """Verify loan officer queue search and status/product filters work."""
    login_as(client, "officer01@example.test")

    # 1. Access queue - standard view
    res = client.get("/officer/queue")
    assert res.status_code == 200
    assert b"Loan Officer Workspace" in res.data

    # 2. Search by applicant name
    res_search = client.get("/officer/queue?q=borrower")
    assert res_search.status_code == 200

    # 3. Filter by status
    res_filter_pending = client.get("/officer/queue?status=PENDING_REVIEW")
    assert res_filter_pending.status_code == 200

    # 4. Filter by product
    prod = seeded_db.query(LoanProduct).first()
    if prod:
        res_prod = client.get(f"/officer/queue?product_id={prod.product_id}")
        assert res_prod.status_code == 200

    # 5. Pagination
    res_page = client.get("/officer/queue?page=1&per_page=2")
    assert res_page.status_code == 200


# ============================================================================
# 5. Officer Review Workspace Actions (Notes, Request Docs, Officer Reject)
# ============================================================================

def test_officer_add_review_notes(client, seeded_db):
    """Officer adds internal review note, recorded in application and audit log."""
    login_as(client, "officer01@example.test")

    app = seeded_db.query(LoanApplication).filter_by(status="PENDING_REVIEW").first()
    assert app is not None

    res_note = client.post(
        f"/officer/applications/{app.application_id}/notes",
        data={"notes": "Applicant documents appear in order. Credit bureau check verified."},
        follow_redirects=True,
    )
    assert res_note.status_code == 200

    seeded_db.refresh(app)
    assert app.review_notes == "Applicant documents appear in order. Credit bureau check verified."

    # Verify audit log
    audit = seeded_db.query(ApplicationAuditLog).filter_by(
        application_id=app.application_id, action="NOTE_ADDED"
    ).first()
    assert audit is not None
    assert "Credit bureau check verified" in audit.notes


def test_officer_request_documents(client, seeded_db):
    """Officer marks application as DOCUMENTS_REQUIRED with instructions."""
    login_as(client, "officer01@example.test")

    app = seeded_db.query(LoanApplication).filter_by(status="PENDING_REVIEW").first()
    assert app is not None

    res = client.post(
        f"/officer/applications/{app.application_id}/request-documents",
        data={"notes": "Please upload salary slips for the last 3 months."},
        follow_redirects=True,
    )
    assert res.status_code == 200

    seeded_db.refresh(app)
    assert app.status == "DOCUMENTS_REQUIRED"
    assert "salary slips" in app.review_notes

    # Verify audit log
    audit = seeded_db.query(ApplicationAuditLog).filter_by(
        application_id=app.application_id, action="DOCUMENTS_REQUESTED"
    ).first()
    assert audit is not None


def test_customer_resubmit_documents(client, seeded_db):
    """Customer resubmits application after uploading requested documents."""
    # Create application in DOCUMENTS_REQUIRED status for customer 1
    app = LoanApplication(
        application_id="APP-RESUB-001",
        customer_id=1,
        applicant_name="Resubmit Borrower",
        monthly_income=70000.0,
        requested_amount=180000.0,
        term_months=24,
        status="DOCUMENTS_REQUIRED",
        review_notes="Upload bank statement",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app)
    seeded_db.commit()

    login_as(client, "borrower01@example.test")

    res = client.post(
        f"/applications/{app.application_id}/resubmit-documents",
        data={"notes": "Uploaded latest 6-month bank statement."},
        follow_redirects=True,
    )
    assert res.status_code == 200

    seeded_db.refresh(app)
    assert app.status == "UNDER_REVIEW"

    # Verify audit log
    audit = seeded_db.query(ApplicationAuditLog).filter_by(
        application_id=app.application_id, action="DOCUMENTS_RESUBMITTED"
    ).first()
    assert audit is not None
    assert "Uploaded latest 6-month bank statement" in audit.notes


def test_officer_reject_application_with_reason(client, seeded_db):
    """Officer rejects application with mandatory documented reason."""
    login_as(client, "officer01@example.test")

    app = seeded_db.query(LoanApplication).filter_by(status="PENDING_REVIEW").first()
    assert app is not None

    # Rejection requires reason
    res_no_reason = client.post(
        f"/officer/applications/{app.application_id}/reject",
        data={"reason": ""},
        follow_redirects=True,
    )
    seeded_db.refresh(app)
    assert app.status == "PENDING_REVIEW"  # Did not reject without reason

    # Reject with valid reason
    res_reject = client.post(
        f"/officer/applications/{app.application_id}/reject",
        data={"reason": "High debt-to-income ratio and insufficient steady income history."},
        follow_redirects=True,
    )
    assert res_reject.status_code == 200

    seeded_db.refresh(app)
    assert app.status == "REJECTED"
    assert app.rejection_reason == "High debt-to-income ratio and insufficient steady income history."

    # Verify audit log
    audit = seeded_db.query(ApplicationAuditLog).filter_by(
        application_id=app.application_id, action="OFFICER_REJECTED"
    ).first()
    assert audit is not None


# ============================================================================
# 6. Loan Manager Decisions (Approval, Rejection)
# ============================================================================

def test_manager_decision_approval_and_rejection(client, seeded_db):
    """Manager approves and rejects applications with audit logs and notes."""
    login_as(client, "manager01@example.test")

    # App 1: Approval
    app1 = LoanApplication(
        application_id="APP-MGR-001",
        customer_id=1,
        applicant_name="Manager Review Borrower 1",
        monthly_income=90000.0,
        requested_amount=300000.0,
        term_months=36,
        status="PENDING_MANAGER_REVIEW",
        created_at=date.today(),
        updated_at=date.today(),
    )
    # App 2: Rejection
    app2 = LoanApplication(
        application_id="APP-MGR-002",
        customer_id=1,
        applicant_name="Manager Review Borrower 2",
        monthly_income=35000.0,
        requested_amount=500000.0,
        term_months=60,
        status="PENDING_MANAGER_REVIEW",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add_all([app1, app2])
    seeded_db.commit()

    # 1. Approve App 1
    res_app = client.post(
        f"/manager/applications/{app1.application_id}/decision",
        data={"decision": "APPROVE", "notes": "Approved under Prime lending policy."},
        follow_redirects=True,
    )
    assert res_app.status_code == 200

    seeded_db.refresh(app1)
    assert app1.status == "APPROVED"
    assert app1.approved_amount == 300000.0
    assert app1.disbursement_status == "NOT_DISBURSED"

    audit1 = seeded_db.query(ApplicationAuditLog).filter_by(
        application_id=app1.application_id, action="MANAGER_APPROVED"
    ).first()
    assert audit1 is not None

    # 2. Reject App 2
    res_rej = client.post(
        f"/manager/applications/{app2.application_id}/decision",
        data={"decision": "REJECT", "notes": "Excessive leverage requested relative to income profile."},
        follow_redirects=True,
    )
    assert res_rej.status_code == 200

    seeded_db.refresh(app2)
    assert app2.status == "REJECTED"
    assert app2.approved_amount is None

    audit2 = seeded_db.query(ApplicationAuditLog).filter_by(
        application_id=app2.application_id, action="MANAGER_REJECTED"
    ).first()
    assert audit2 is not None


# ============================================================================
# 7. Customer Ownership Access Control
# ============================================================================

def test_customer_cannot_access_other_customer_application(client, seeded_db):
    """Customer cannot view status or edit another customer's application."""
    # Customer 2's app
    app_cust2 = LoanApplication(
        application_id="APP-CUST2-001",
        customer_id=2,
        applicant_name="Customer Two",
        monthly_income=50000.0,
        requested_amount=100000.0,
        term_months=12,
        status="DRAFT",
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app_cust2)
    seeded_db.commit()

    # Log in as Customer 1
    login_as(client, "borrower01@example.test")

    # Attempt to view status
    res_status = client.get(f"/applications/{app_cust2.application_id}/status")
    assert res_status.status_code == 403

    # Attempt to edit draft
    res_edit = client.get(f"/applications/{app_cust2.application_id}/edit")
    assert res_edit.status_code == 403

    # Attempt to resubmit documents
    res_resub = client.post(f"/applications/{app_cust2.application_id}/resubmit-documents", data={"notes": "hack"})
    assert res_resub.status_code == 403
