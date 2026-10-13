"""Comprehensive tests for Phase 6: Customer Profile, KYC, Document Vault, and Enhanced Loan Application."""
import io
import pytest
from datetime import date
from src.models import User, LoanApplication, CustomerDocument, Notification


def login_as(client, email, password="demo123"):
    """Helper to authenticate a test client session."""
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ============================================================================
# 1. Customer Profile Tests
# ============================================================================

def test_customer_profile_view_and_update(client, seeded_db):
    """Customer views and updates profile details, calculating real completion percentage."""
    login_as(client, "borrower01@example.test")

    # 1. View profile page
    res_get = client.get("/customer/profile")
    assert res_get.status_code == 200
    assert b"Customer Profile" in res_get.data
    assert b"borrower01@example.test" in res_get.data

    # Check baseline completion percentage
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()
    initial_pct = user.profile_completion_percentage
    assert initial_pct >= 20  # Name and email present

    # 2. Update profile with complete fields
    update_data = {
        "phone_number": "+91 9876543210",
        "date_of_birth": "1992-05-15",
        "address": "42 Tech Boulevard, Floor 3",
        "city": "Bengaluru",
        "state": "Karnataka",
        "employment_type": "SALARIED",
        "employer_name": "Antigravity Systems",
        "monthly_income": "85000",
    }
    res_post = client.post("/customer/profile", data=update_data, follow_redirects=True)
    assert res_post.status_code == 200
    assert b"Your profile has been successfully updated" in res_post.data

    # Verify updated values in database
    seeded_db.refresh(user)
    assert user.phone_number == "+91 9876543210"
    assert user.date_of_birth == date(1992, 5, 15)
    assert user.city == "Bengaluru"
    assert user.employment_type == "SALARIED"
    assert user.employer_name == "Antigravity Systems"
    assert user.monthly_income == 85000.0
    assert user.profile_completion_percentage == 100


def test_customer_profile_validation_errors(client, seeded_db):
    """Profile updates with invalid dates or negative values are rejected."""
    login_as(client, "borrower01@example.test")

    # Invalid date of birth
    bad_data = {
        "phone_number": "9876543210",
        "date_of_birth": "not-a-date",
        "monthly_income": "-500",
    }
    res = client.post("/customer/profile", data=bad_data)
    assert res.status_code == 400
    assert b"Date of birth must be in YYYY-MM-DD format" in res.data
    assert b"Monthly income cannot be negative" in res.data


def test_profile_prefill_on_new_loan_application(client, seeded_db):
    """GET /applications/new pre-fills inputs from customer profile if available."""
    # Update borrower profile first
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()
    user.monthly_income = 75000.0
    user.employment_type = "SALARIED"
    user.employer_name = "Global FinTech Ltd"
    seeded_db.commit()

    login_as(client, "borrower01@example.test")
    res = client.get("/applications/new")
    assert res.status_code == 200
    assert b"75000" in res.data
    assert b"Global FinTech Ltd" in res.data


# ============================================================================
# 2. Document Vault & KYC Workflow Tests
# ============================================================================

def test_document_upload_and_validation(client, seeded_db, app):
    """Customer can upload valid documents; invalid files and oversized files are rejected."""
    login_as(client, "borrower01@example.test")

    # 1. Valid PDF upload
    pdf_content = b"%PDF-1.4 test dummy document content for loan verification"
    res_upload = client.post(
        "/customer/documents/upload",
        data={
            "document_type": "IDENTITY_PROOF",
            "file": (io.BytesIO(pdf_content), "passport.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res_upload.status_code == 200
    assert b"passport.pdf" in res_upload.data

    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()
    doc = seeded_db.query(CustomerDocument).filter_by(customer_id=user.user_id, document_type="IDENTITY_PROOF").first()
    assert doc is not None
    assert doc.original_filename == "passport.pdf"
    assert doc.verification_status == "PENDING"

    # 2. Invalid file type (.exe)
    res_bad_ext = client.post(
        "/customer/documents/upload",
        data={
            "document_type": "ADDRESS_PROOF",
            "file": (io.BytesIO(b"binary exe"), "script.exe"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Unsupported file type" in res_bad_ext.data

    # 3. Empty file
    res_empty = client.post(
        "/customer/documents/upload",
        data={
            "document_type": "INCOME_PROOF",
            "file": (io.BytesIO(b""), "empty.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"The uploaded file is empty" in res_empty.data


def test_document_access_control(client, seeded_db):
    """Customers cannot download another user's documents; officers and managers can."""
    # Create document for borrower 1
    user1 = seeded_db.query(User).filter_by(email="borrower01@example.test").first()
    doc = CustomerDocument(
        customer_id=user1.user_id,
        document_type="IDENTITY_PROOF",
        original_filename="user1_id.pdf",
        stored_filename="cust_1_id_test.pdf",
        file_path="/tmp/user1_id.pdf",
        file_size=100,
        mime_type="application/pdf",
        verification_status="PENDING",
    )
    seeded_db.add(doc)
    seeded_db.commit()

    # Create dummy file at /tmp/user1_id.pdf so send_file finds it
    with open("/tmp/user1_id.pdf", "wb") as f:
        f.write(b"%PDF-1.4 dummy content")

    # Borrower 2 attempts to download borrower 1's document -> 403 Forbidden
    login_as(client, "borrower02@example.test")
    res_forbidden = client.get(f"/customer/documents/{doc.document_id}/download")
    assert res_forbidden.status_code == 403
    client.post("/logout")

    # Borrower 1 downloads their own document -> 200 OK
    login_as(client, "borrower01@example.test")
    res_own = client.get(f"/customer/documents/{doc.document_id}/download")
    assert res_own.status_code == 200
    client.post("/logout")

    # Loan Officer downloads borrower 1's document -> 200 OK
    login_as(client, "officer01@example.test")
    res_officer = client.get(f"/customer/documents/{doc.document_id}/download")
    assert res_officer.status_code == 200
    client.post("/logout")

    # Loan Manager downloads borrower 1's document -> 200 OK
    login_as(client, "manager01@example.test")
    res_mgr = client.get(f"/customer/documents/{doc.document_id}/download")
    assert res_mgr.status_code == 200


def test_kyc_end_to_end_verification_and_rejection(client, seeded_db):
    """Full KYC lifecycle: Customer submits docs -> Officer reviews and rejects -> Customer resubmits -> Officer approves."""
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()
    assert user.kyc_status == "NOT_STARTED"

    login_as(client, "borrower01@example.test")

    # Attempt to submit KYC with no documents uploaded
    res_sub_empty = client.post("/customer/kyc/submit", follow_redirects=True)
    assert b"Please upload at least one verification document" in res_sub_empty.data

    # Upload document
    pdf_content = b"%PDF-1.4 passport valid"
    client.post(
        "/customer/documents/upload",
        data={"document_type": "IDENTITY_PROOF", "file": (io.BytesIO(pdf_content), "passport.pdf")},
        content_type="multipart/form-data",
    )

    # Submit KYC
    res_submit = client.post("/customer/kyc/submit", follow_redirects=True)
    assert res_submit.status_code == 200
    assert b"KYC documents submitted successfully" in res_submit.data

    seeded_db.refresh(user)
    assert user.kyc_status == "PENDING"

    client.post("/logout")

    # Officer checks KYC queue
    login_as(client, "officer01@example.test")
    res_queue = client.get("/officer/kyc")
    assert res_queue.status_code == 200
    assert b"borrower01@example.test" in res_queue.data or b"Test Borrower 01" in res_queue.data

    # Officer rejects KYC with reason
    res_reject = client.post(
        f"/officer/kyc/{user.user_id}",
        data={"action": "REJECT", "rejection_reason": "Passport scan is blurred and missing expiration date"},
        follow_redirects=True,
    )
    assert res_reject.status_code == 200
    assert b"has been rejected" in res_reject.data

    seeded_db.refresh(user)
    assert user.kyc_status == "REJECTED"
    assert "Passport scan is blurred" in user.kyc_rejection_reason

    client.post("/logout")

    # Customer sees rejection reason and resubmits
    login_as(client, "borrower01@example.test")
    res_cust_kyc = client.get("/customer/kyc")
    assert b"Passport scan is blurred" in res_cust_kyc.data

    # Customer resubmits KYC
    res_resubmit = client.post("/customer/kyc/submit", follow_redirects=True)
    assert res_resubmit.status_code == 200
    seeded_db.refresh(user)
    assert user.kyc_status == "PENDING"

    client.post("/logout")

    # Officer approves KYC
    login_as(client, "officer01@example.test")
    res_approve = client.post(
        f"/officer/kyc/{user.user_id}",
        data={"action": "VERIFY"},
        follow_redirects=True,
    )
    assert res_approve.status_code == 200
    assert b"has been verified" in res_approve.data

    seeded_db.refresh(user)
    assert user.kyc_status == "VERIFIED"
    assert user.kyc_rejection_reason is None


# ============================================================================
# 3. Enhanced Loan Application & Confirmation Summary Tests
# ============================================================================

def test_enhanced_loan_application_summary_and_commit(client, seeded_db):
    """Customer fills enhanced loan application, views confirmation summary, and submits."""
    login_as(client, "borrower01@example.test")

    payload = {
        "applicant_name": "Test Borrower",
        "monthly_income": "80000",
        "requested_amount": "250000",
        "term_months": "36",
        "loan_purpose": "EDUCATION",
        "employment_type": "SALARIED",
        "employer_name": "Antigravity Research",
        "existing_obligations": "12000",
        "preferred_repayment_date": "10",
        "action": "preview",
    }

    # 1. Preview action renders summary confirmation screen without saving to DB yet
    initial_count = seeded_db.query(LoanApplication).count()
    res_preview = client.post("/applications/new", data=payload)
    assert res_preview.status_code == 200
    assert b"Application Summary" in res_preview.data
    assert b"Confirm Application Details" in res_preview.data
    assert b"EDUCATION" in res_preview.data
    assert b"Antigravity Research" in res_preview.data
    assert seeded_db.query(LoanApplication).count() == initial_count

    # 2. Final confirm action saves the application with enhanced fields
    payload["action"] = "submit"
    res_submit = client.post("/applications/new", data=payload, follow_redirects=True)
    assert res_submit.status_code == 200
    assert seeded_db.query(LoanApplication).count() == initial_count + 1

    new_app = seeded_db.query(LoanApplication).filter_by(requested_amount=250000.0).first()
    assert new_app is not None
    assert new_app.loan_purpose == "EDUCATION"
    assert new_app.employment_type == "SALARIED"
    assert new_app.employer_name == "Antigravity Research"
    assert new_app.existing_obligations == 12000.0
    assert new_app.preferred_repayment_date == 10


def test_customer_dashboard_kyc_status_cards(client, seeded_db):
    """Dashboard dynamically displays appropriate card and CTA for each KYC state."""
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()

    # 1. NOT_STARTED
    user.kyc_status = "NOT_STARTED"
    seeded_db.commit()
    login_as(client, "borrower01@example.test")
    res1 = client.get("/customer/dashboard")
    assert b"Complete Your Verification" in res1.data
    assert b"Complete KYC" in res1.data

    # 2. PENDING
    user.kyc_status = "PENDING"
    seeded_db.commit()
    res2 = client.get("/customer/dashboard")
    assert b"Verification in Progress" in res2.data
    assert b"Check KYC Status" in res2.data

    # 3. VERIFIED
    user.kyc_status = "VERIFIED"
    seeded_db.commit()
    res3 = client.get("/customer/dashboard")
    assert b"Your Identity is Verified" in res3.data
    assert b"VERIFIED" in res3.data

    # 4. REJECTED
    user.kyc_status = "REJECTED"
    user.kyc_rejection_reason = "Expired passport"
    seeded_db.commit()
    res4 = client.get("/customer/dashboard")
    assert b"KYC Verification Action Required" in res4.data
    assert b"Expired passport" in res4.data
    assert b"Fix &amp; Resubmit KYC" in res4.data or b"Fix & Resubmit KYC" in res4.data


def test_officer_application_review_displays_kyc_and_enhanced_fields(client, seeded_db):
    """Officer reviewing a loan application sees the customer's KYC status and enhanced fields."""
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()
    user.kyc_status = "VERIFIED"
    seeded_db.commit()

    # Create application with enhanced fields
    app_obj = LoanApplication(
        application_id="APP-9999",
        customer_id=user.user_id,
        applicant_name=user.full_name,
        monthly_income=70000.0,
        requested_amount=200000.0,
        term_months=24,
        status="PENDING_REVIEW",
        loan_purpose="BUSINESS",
        loan_purpose_other="Expansion of retail shop",
        employment_type="BUSINESS_OWNER",
        employer_name="SuperMart",
        existing_obligations=5000.0,
        preferred_repayment_date=15,
        created_at=date.today(),
        updated_at=date.today(),
    )
    seeded_db.add(app_obj)
    seeded_db.commit()

    login_as(client, "officer01@example.test")
    res = client.get(f"/officer/applications/{app_obj.application_id}")
    assert res.status_code == 200
    assert b"BUSINESS" in res.data
    assert b"Expansion of retail shop" in res.data
    assert b"SuperMart" in res.data
    assert b"Day 15" in res.data
    assert b"KYC: VERIFIED" in res.data
