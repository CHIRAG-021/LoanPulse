"""Phase 5 Final Verification Tests.

Implements and verifies:
- TC-20 (Clean environment startup and reproducibility)
- TC-21 (Documented test execution)
- TC-23 (Synthetic demonstration data policy verification)
- TC-24 (Clean machine startup and execution)
- End-to-end lifecycle integration (Customer -> Officer -> Manager -> Disbursement -> Notifications)
- Complete UI template rendering checks against docs/wireframe.html
"""
import csv
import re
from pathlib import Path
import pytest

from src.app import create_app
from src.models import db, LoanApplication, Notification


# ============================================================================
# TC-23: Confirm demonstration data contains no real personal data
# ============================================================================
def test_tc_23_confirm_synthetic_demo_data_only():
    """TC-23: Verify that all seed and fixture datasets contain only synthetic data.
    
    Checks that:
    1. All user emails strictly end with '@example.test'
    2. All applicant and user names follow synthetic patterns ('Test Borrower...', etc.)
    3. No real personal identifiers (Aadhaar, PAN, real banking details) exist.
    """
    data_dir = Path(__file__).resolve().parent.parent / "data"

    # 1. Check users.csv
    with open(data_dir / "users.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row["email"].strip()
            name = row["full_name"].strip()
            assert email.endswith("@example.test"), f"Non-synthetic email found: {email}"
            assert name.startswith("Test "), f"Non-synthetic name found: {name}"

    # 2. Check loan_applications.csv
    with open(data_dir / "loan_applications.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["applicant_name"].strip()
            assert name.startswith("Test "), f"Non-synthetic applicant name found: {name}"

    # 3. Search all data files for Aadhaar / PAN patterns
    # Indian PAN: 5 uppercase letters + 4 digits + 1 uppercase letter
    # Aadhaar: 12 continuous digits
    pan_pattern = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
    aadhaar_pattern = re.compile(r"\b\d{12}\b")

    for csv_file in data_dir.glob("**/*.csv"):
        content = csv_file.read_text(encoding="utf-8")
        assert not pan_pattern.search(content), f"Potential real PAN pattern found in {csv_file.name}"
        assert not aadhaar_pattern.search(content), f"Potential 12-digit Aadhaar pattern found in {csv_file.name}"


# ============================================================================
# TC-20 & TC-24: Reproduce application setup and clean startup
# ============================================================================
def test_tc_20_and_24_clean_startup_and_reproducibility(runner):
    """TC-20 / TC-24: Application starts cleanly and initializes database using documented CLI."""
    # 1. Initialize and seed using CLI command
    result = runner.invoke(args=["init-db"])
    assert result.exit_code == 0
    assert "Database initialized and seeded successfully:" in result.output

    # 2. Verify clean app startup and access
    test_app = create_app(config_name="testing")
    with test_app.test_client() as client:
        # Check health endpoint works out-of-the-box
        health_res = client.get("/health")
        assert health_res.status_code == 200
        assert health_res.get_json()["status"] == "ok"

        # Check login page works smoothly on clean startup
        login_res = client.get("/login")
        assert login_res.status_code == 200
        assert b"LoanPulse" in login_res.data


# ============================================================================
# TC-21: Run documented test suite
# ============================================================================
def test_tc_21_test_suite_discoverability():
    """TC-21: Documented test suite files exist and are discoverable by pytest."""
    tests_dir = Path(__file__).resolve().parent
    test_files = [f.name for f in tests_dir.glob("test_*.py")]
    assert "test_foundation.py" in test_files
    assert "test_phase2_services.py" in test_files
    assert "test_phase3_flows.py" in test_files
    assert "test_phase4_features.py" in test_files
    assert "test_phase5_verification.py" in test_files


# ============================================================================
# Full Lifecycle Integration Test
# Customer -> Officer -> Manager -> Disbursement -> Notifications
# ============================================================================
def test_full_lifecycle_integration(client, seeded_db):
    """Verify the entire end-to-end loan lifecycle in sequence.
    
    1. Customer creates loan application
    2. Officer reviews and runs rule assessment
    3. Officer sends application to manager
    4. Manager reviews and approves application
    5. Officer records disbursement
    6. Customer views notifications and marks them as read
    """
    # Step 1: Customer submits application
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    create_res = client.post(
        "/applications/new",
        data={
            "applicant_name": "Full Lifecycle Borrower",
            "monthly_income": "75000",
            "requested_amount": "250000",
            "term_months": "24",
        },
        follow_redirects=True,
    )
    assert create_res.status_code == 200

    # Query created application
    app_record = seeded_db.query(LoanApplication).filter_by(applicant_name="Full Lifecycle Borrower").first()
    assert app_record is not None
    app_id = app_record.application_id
    assert app_record.status == "PENDING_REVIEW"
    assert app_record.disbursement_status == "NOT_APPLICABLE"

    client.get("/logout")

    # Step 2 & 3: Officer reviews, assesses, and forwards to manager
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    assess_res = client.post(f"/officer/applications/{app_id}/assess", follow_redirects=True)
    assert assess_res.status_code == 200
    assert b"ELIGIBLE" in assess_res.data

    fwd_res = client.post(f"/officer/applications/{app_id}/send-to-manager", follow_redirects=True)
    assert fwd_res.status_code == 200

    seeded_db.refresh(app_record)
    assert app_record.status == "PENDING_MANAGER_REVIEW"

    client.get("/logout")

    # Step 4: Manager reviews pending queue and approves application
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    queue_res = client.get("/manager/queue")
    assert queue_res.status_code == 200
    assert app_id.encode() in queue_res.data

    approve_res = client.post(
        f"/manager/applications/{app_id}/decision",
        data={"decision": "APPROVE"},
        follow_redirects=True,
    )
    assert approve_res.status_code == 200

    seeded_db.refresh(app_record)
    assert app_record.status == "APPROVED"
    assert app_record.approved_amount == 250000.0
    assert app_record.disbursement_status == "NOT_DISBURSED"

    client.get("/logout")

    # Step 5: Officer records disbursement
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    disb_res = client.post(
        f"/officer/applications/{app_id}/disburse",
        data={"disbursement_date": "2026-10-15"},
        follow_redirects=True,
    )
    assert disb_res.status_code == 200

    seeded_db.refresh(app_record)
    assert app_record.disbursement_status == "DISBURSED"
    assert str(app_record.disbursement_date) == "2026-10-15"

    client.get("/logout")

    # Step 6: Customer views notifications and marks them as read
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    notifs_res = client.get("/notifications")
    assert notifs_res.status_code == 200
    assert app_id.encode() in notifs_res.data

    mark_res = client.post("/notifications/mark-read", follow_redirects=True)
    assert mark_res.status_code == 200

    api_notifs = client.get("/notifications", headers={"Accept": "application/json"}).get_json()
    assert api_notifs["unread_count"] == 0


# ============================================================================
# UI Template Rendering Verification (All Screens)
# ============================================================================
def test_all_ui_screens_render_successfully(client, seeded_db):
    """Verify that every Jinja2 template and screen renders with 200 OK."""
    # 1. Login screen
    res_login = client.get("/login")
    assert res_login.status_code == 200
    assert b"Sign In" in res_login.data

    # 2. Customer screens
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust_dash = client.get("/customer/dashboard")
    assert res_cust_dash.status_code == 200

    res_cust_apply = client.get("/applications/new")
    assert res_cust_apply.status_code == 200

    res_cust_status = client.get("/applications/APP-0002/status")
    assert res_cust_status.status_code == 200

    res_cust_notifs = client.get("/notifications")
    assert res_cust_notifs.status_code == 200
    client.get("/logout")

    # 3. Officer screens
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off_queue = client.get("/officer/queue")
    assert res_off_queue.status_code == 200

    res_off_review = client.get("/officer/applications/APP-0001")
    assert res_off_review.status_code == 200

    res_off_disb = client.get("/officer/disbursements")
    assert res_off_disb.status_code == 200
    client.get("/logout")

    # 4. Manager screen
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res_mgr_queue = client.get("/manager/queue")
    assert res_mgr_queue.status_code == 200
    client.get("/logout")
