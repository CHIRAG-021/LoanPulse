"""Comprehensive automated test suite for Phase 7: Loan Products, Advanced Rule Engine, and EMI Calculator."""
import json
import pytest
from src.models import Assessment, LoanApplication, LoanProduct, User, db
from src.services.assessment_service import assess_application, assess_application_data, evaluate_product_rules
from src.services.financial_service import calculate_emi, validate_calculator_inputs
from src.services.validation_service import ValidationError, validate_loan_product


def login_as(client, email, password="demo123"):
    """Helper to authenticate a test user."""
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ============================================================================
# 1. Loan Products Model, Validation, and Seed Data Tests
# ============================================================================

def test_seeded_loan_products(app, seeded_db):
    """Verify standard loan products seeded correctly with valid boundaries and active status."""
    products = seeded_db.query(LoanProduct).all()
    assert len(products) >= 5

    codes = [p.product_code for p in products]
    assert "PERSONAL" in codes
    assert "EDUCATION" in codes
    assert "MEDICAL" in codes
    assert "BUSINESS" in codes
    assert "HOME_IMPROVEMENT" in codes

    pers = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()
    assert pers.product_name == "Personal Loan"
    assert pers.min_amount == 10000.0
    assert pers.max_amount == 500000.0
    assert pers.min_term_months == 12
    assert pers.max_term_months == 60
    assert pers.annual_interest_rate == 11.5
    assert pers.min_monthly_income == 25000.0
    assert pers.max_loan_to_income_ratio == 0.5
    assert pers.is_active is True


def test_loan_product_validation():
    """Verify validation_service.validate_loan_product validates data strictly."""
    # Valid product payload
    valid_data = {
        "product_code": "lp-auto",
        "product_name": "Automobile Loan",
        "description": "Vehicle financing",
        "min_amount": 50000,
        "max_amount": 1000000,
        "min_term_months": 12,
        "max_term_months": 84,
        "annual_interest_rate": 8.75,
        "min_monthly_income": 30000,
        "max_loan_to_income_ratio": 5.0,
    }
    res_valid = validate_loan_product(valid_data)
    assert res_valid.is_valid is True
    assert res_valid.cleaned_data["product_code"] == "LP-AUTO"
    assert res_valid.cleaned_data["min_amount"] == 50000.0
    assert res_valid.cleaned_data["annual_interest_rate"] == 8.75

    # Invalid: max amount < min amount
    invalid_bounds = dict(valid_data, min_amount=500000, max_amount=100000)
    res_bounds = validate_loan_product(invalid_bounds)
    assert res_bounds.is_valid is False
    assert "max_amount" in res_bounds.errors

    # Invalid: interest rate out of bounds
    invalid_rate = dict(valid_data, annual_interest_rate=-2.5)
    res_rate = validate_loan_product(invalid_rate)
    assert res_rate.is_valid is False
    assert "annual_interest_rate" in res_rate.errors

    # Invalid: negative min income
    invalid_income = dict(valid_data, min_monthly_income=-100)
    res_inc = validate_loan_product(invalid_income)
    assert res_inc.is_valid is False
    assert "min_monthly_income" in res_inc.errors


# ============================================================================
# 2. Manager Loan Product Management & RBAC Protection Tests
# ============================================================================

def test_manager_loan_products_crud_and_toggle(client, seeded_db):
    """Manager can view, create, edit, and toggle status of loan products."""
    login_as(client, "manager01@example.test")

    # 1. View catalog
    res_list = client.get("/manager/loan-products")
    assert res_list.status_code == 200
    assert b"Loan Products Management" in res_list.data
    assert b"Personal Loan" in res_list.data
    assert b"PERSONAL" in res_list.data

    # 2. Create new product
    new_product_data = {
        "product_code": "LP-SOLAR",
        "product_name": "Rooftop Solar Loan",
        "description": "Green energy solar installation finance",
        "min_amount": "50000",
        "max_amount": "800000",
        "min_term_months": "12",
        "max_term_months": "60",
        "annual_interest_rate": "7.5",
        "min_monthly_income": "30000",
        "max_loan_to_income_ratio": "4.5",
        "is_active": "y",
    }
    res_create = client.post("/manager/loan-products/new", data=new_product_data, follow_redirects=True)
    assert res_create.status_code == 200
    assert b"Rooftop Solar Loan" in res_create.data and b"created successfully" in res_create.data

    created = seeded_db.query(LoanProduct).filter_by(product_code="LP-SOLAR").first()
    assert created is not None
    assert created.annual_interest_rate == 7.5

    # 3. Duplicate code rejection
    res_dup = client.post("/manager/loan-products/new", data=new_product_data, follow_redirects=True)
    assert res_dup.status_code == 400
    assert b"already in use" in res_dup.data or b"already exists" in res_dup.data

    # 4. Edit product
    edit_data = dict(new_product_data, annual_interest_rate="6.99", description="Updated description")
    res_edit = client.post(f"/manager/loan-products/{created.product_id}/edit", data=edit_data, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"updated successfully" in res_edit.data

    seeded_db.refresh(created)
    assert created.annual_interest_rate == 6.99

    # 5. Toggle active status
    assert created.is_active is True
    res_toggle = client.post(f"/manager/loan-products/{created.product_id}/toggle-status", follow_redirects=True)
    assert res_toggle.status_code == 200
    seeded_db.refresh(created)
    assert created.is_active is False
    assert b"DEACTIVATED" in res_toggle.data or b"deactivated" in res_toggle.data.lower()


def test_loan_products_rbac_restrictions(client, seeded_db):
    """Customer and Officer cannot access manager loan product modification routes (403 Forbidden)."""
    # 1. Customer blocked
    login_as(client, "borrower01@example.test")
    assert client.get("/manager/loan-products").status_code == 403
    assert client.get("/manager/loan-products/new").status_code == 403
    assert client.post("/manager/loan-products/new", data={}).status_code == 403
    assert client.post("/manager/loan-products/1/toggle-status").status_code == 403
    client.post("/logout")

    # 2. Officer blocked from manager routes
    login_as(client, "officer01@example.test")
    assert client.get("/manager/loan-products").status_code == 403
    assert client.get("/manager/loan-products/new").status_code == 403
    assert client.post("/manager/loan-products/1/toggle-status").status_code == 403

    # Officer can access read-only products directory
    res_officer_view = client.get("/officer/loan-products")
    assert res_officer_view.status_code == 200
    assert b"Loan Product Directory" in res_officer_view.data
    client.post("/logout")


# ============================================================================
# 3. Financial Service & EMI Calculator Tests
# ============================================================================

def test_financial_service_reducing_balance_emi():
    """Verify reducing-balance EMI formula against known standard values and round-half-up precision."""
    # Standard Case: 100,000 at 12% for 12 months -> EMI = 8,884.88
    # Monthly rate = 0.01
    # EMI = 100000 * 0.01 * (1.01^12) / ((1.01^12) - 1) = 8884.87886... -> 8884.88
    result = calculate_emi(100000.0, 12.0, 12)
    assert result["monthly_emi"] == 8884.88
    assert result["total_payment"] == 106618.56
    assert result["total_interest"] == 6618.56
    assert result["interest_ratio"] == 6.62

    # Case: 500,000 at 10.5% for 36 months
    res36 = calculate_emi(500000.0, 10.5, 36)
    assert res36["monthly_emi"] > 0
    assert res36["total_payment"] == round(res36["monthly_emi"] * 36, 2)
    assert res36["total_interest"] == round(res36["total_payment"] - 500000.0, 2)

    # Edge Case: Zero interest rate (0% p.a.) -> EMI = Principal / Tenure
    res_zero = calculate_emi(120000.0, 0.0, 12)
    assert res_zero["monthly_emi"] == 10000.00
    assert res_zero["total_payment"] == 120000.00
    assert res_zero["total_interest"] == 0.00
    assert res_zero["effective_rate_pa"] == 0.0


def test_financial_service_invalid_inputs():
    """Verify financial service validation rejects negative or non-sensical inputs."""
    with pytest.raises(ValidationError):
        calculate_emi(-50000.0, 10.0, 12)

    with pytest.raises(ValidationError):
        calculate_emi(50000.0, -5.0, 12)

    with pytest.raises(ValidationError):
        calculate_emi(50000.0, 10.0, 0)


def test_emi_calculator_web_and_api_routes(client, seeded_db):
    """Verify public/customer calculator routes and JSON calculation API."""
    # Public calculator
    res_calc = client.get("/calculator")
    assert res_calc.status_code == 200
    assert b"Interactive Loan EMI Calculator" in res_calc.data
    assert b"Reducing Balance Method" in res_calc.data

    # JSON API Calculation
    api_res = client.get("/api/calculate-emi?principal=200000&rate=10.5&tenure=24")
    assert api_res.status_code == 200
    data = api_res.get_json()
    assert data["status"] == "success"
    assert data["monthly_emi"] > 0
    assert data["principal"] == 200000.0
    assert data["tenure_months"] == 24

    # Invalid query parameters return 400
    bad_api = client.get("/api/calculate-emi?principal=-5000&rate=10&tenure=12")
    assert bad_api.status_code == 400


# ============================================================================
# 4. Enhanced Application Flow with Loan Product & Historical Snapshot Tests
# ============================================================================

def test_application_with_product_and_historical_invariance(client, seeded_db):
    """Applying with a loan product snapshots terms; subsequent product edits do NOT mutate past application."""
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()
    product = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()
    initial_rate = product.annual_interest_rate  # 11.5%

    login_as(client, "borrower01@example.test")

    payload = {
        "applicant_name": "Test Borrower 01",
        "monthly_income": "60000",
        "requested_amount": "100000",
        "term_months": "24",
        "product_id": str(product.product_id),
        "employment_type": "SALARIED",
        "employer_name": "Tech Corp",
        "existing_obligations": "5000",
        "preferred_repayment_date": "5",
        "action": "submit",
    }

    res = client.post("/applications/new", data=payload, follow_redirects=True)
    assert res.status_code == 200

    new_app = seeded_db.query(LoanApplication).filter_by(customer_id=user.user_id, requested_amount=100000.0).first()
    assert new_app is not None
    assert new_app.product_id == product.product_id
    assert new_app.applied_interest_rate == initial_rate
    assert new_app.estimated_monthly_emi > 0

    original_emi = new_app.estimated_monthly_emi
    client.post("/logout")

    # Manager edits product rate to 18.0%
    login_as(client, "manager01@example.test")
    client.post(
        f"/manager/loan-products/{product.product_id}/edit",
        data={
            "product_code": product.product_code,
            "product_name": product.product_name,
            "description": product.description,
            "min_amount": str(product.min_amount),
            "max_amount": str(product.max_amount),
            "min_term_months": str(product.min_term_months),
            "max_term_months": str(product.max_term_months),
            "annual_interest_rate": "18.0",
            "min_monthly_income": str(product.min_monthly_income),
            "max_loan_to_income_ratio": str(product.max_loan_to_income_ratio),
            "is_active": "y",
        },
        follow_redirects=True,
    )
    seeded_db.refresh(product)
    assert product.annual_interest_rate == 18.0
    client.post("/logout")

    # Historical Invariance Check: Past application rate and EMI must remain unchanged!
    seeded_db.refresh(new_app)
    assert new_app.applied_interest_rate == initial_rate
    assert new_app.estimated_monthly_emi == original_emi


def test_application_product_boundaries_and_inactive_rejection(client, seeded_db):
    """Customer cannot apply with amount/tenure outside product limits or for inactive product."""
    product = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()
    login_as(client, "borrower01@example.test")

    # Amount exceeding product max
    bad_amount = {
        "applicant_name": "Test Borrower",
        "monthly_income": "60000",
        "requested_amount": "9999999",  # Max is 500000
        "term_months": "24",
        "product_id": str(product.product_id),
        "action": "submit",
    }
    res_bad_amt = client.post("/applications/new", data=bad_amount, follow_redirects=True)
    assert b"exceeds maximum allowed" in res_bad_amt.data

    # Deactivate product and verify rejection
    product.is_active = False
    seeded_db.commit()

    res_inactive = client.post("/applications/new", data=dict(bad_amount, requested_amount="100000"), follow_redirects=True)
    assert b"Selected loan product is currently inactive" in res_inactive.data


# ============================================================================
# 5. Advanced Deterministic 6-Rule Policy Engine Tests
# ============================================================================

def test_six_rule_engine_all_pass(seeded_db):
    """All 6 rules pass -> ELIGIBLE result, detailed 6-rule breakdown, empty failure reasons."""
    product = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()

    is_eligible, result, ratio, aff_ratio, emi, breakdown, failures = evaluate_product_rules(
        monthly_income=50000.0,
        requested_amount=150000.0,
        term_months=24,
        product=product,
        existing_obligations=5000.0,
        employment_type="SALARIED",
    )

    assert is_eligible is True
    assert result == "ELIGIBLE"
    assert len(breakdown) == 6
    assert len(failures) == 0

    rule_keys = [r["rule_key"] for r in breakdown]
    assert "income" in rule_keys
    assert "amount" in rule_keys
    assert "tenure" in rule_keys
    assert "lti_ratio" in rule_keys
    assert "affordability" in rule_keys
    assert "employment" in rule_keys
    assert all(r["passed"] for r in breakdown)


def test_six_rule_engine_failures(seeded_db):
    """Each individual rule failure properly triggers NOT_ELIGIBLE with specific human explanation."""
    product = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()

    # 1. Income failure (< 25000)
    _, res1, _, _, _, b1, f1 = evaluate_product_rules(
        monthly_income=20000.0, requested_amount=50000.0, term_months=24, product=product, employment_type="SALARIED"
    )
    assert res1 == "NOT_ELIGIBLE"
    assert any("does not meet the minimum requirement" in reason for reason in f1)

    # 2. Amount below minimum (< 10000)
    _, res2, _, _, _, b2, f2 = evaluate_product_rules(
        monthly_income=50000.0, requested_amount=5000.0, term_months=24, product=product, employment_type="SALARIED"
    )
    assert res2 == "NOT_ELIGIBLE"
    assert any("below the minimum permitted amount" in reason for reason in f2)

    # 3. Tenure exceeding max (> 60 months)
    _, res3, _, _, _, b3, f3 = evaluate_product_rules(
        monthly_income=50000.0, requested_amount=100000.0, term_months=84, product=product, employment_type="SALARIED"
    )
    assert res3 == "NOT_ELIGIBLE"
    assert any("exceeds the maximum allowed tenure" in reason for reason in f3)

    # 4. Loan-to-Income ratio exceeds limit (> 0.5)
    # Requested 400,000 with monthly income 30,000 -> annual income 360,000 -> ratio 1.11 > 0.5
    _, res4, _, _, _, b4, f4 = evaluate_product_rules(
        monthly_income=30000.0, requested_amount=400000.0, term_months=36, product=product, employment_type="SALARIED"
    )
    assert res4 == "NOT_ELIGIBLE"
    assert any("Loan-to-income ratio" in reason for reason in f4)

    # 5. Affordability failure (obligations + EMI > 50% monthly income)
    # Income 30,000 -> 50% cap = 15,000. Existing debt 12,000 + EMI ~9,300 = 21,300 > 15,000
    _, res5, _, _, _, b5, f5 = evaluate_product_rules(
        monthly_income=30000.0,
        requested_amount=200000.0,
        term_months=24,
        product=product,
        existing_obligations=12000.0,
        employment_type="SALARIED",
    )
    assert res5 == "NOT_ELIGIBLE"
    assert any("Affordability cap exceeded" in reason for reason in f5)

    # 6. Employment requirement failure (unemployed)
    _, res6, _, _, _, b6, f6 = evaluate_product_rules(
        monthly_income=50000.0,
        requested_amount=50000.0,
        term_months=24,
        product=product,
        employment_type="UNEMPLOYED",
    )
    assert res6 == "NOT_ELIGIBLE"
    assert any("verifiable active employment" in reason for reason in f6)


# ============================================================================
# 6. Assessment History and Legacy Backward Compatibility Tests
# ============================================================================

def test_assessment_persists_breakdown_and_preserves_history(seeded_db):
    """Assessments save json breakdown and appending multiple runs preserves history."""
    product = seeded_db.query(LoanProduct).filter_by(product_code="PERSONAL").first()
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()

    app = LoanApplication(
        application_id="APP-TEST-HIST",
        customer_id=user.user_id,
        applicant_name=user.full_name,
        monthly_income=60000.0,
        requested_amount=100000.0,
        term_months=24,
        product_id=product.product_id,
        applied_interest_rate=product.annual_interest_rate,
        status="PENDING_REVIEW",
    )
    seeded_db.add(app)
    seeded_db.commit()

    # First assessment
    ass1 = assess_application(app, save=True, session=seeded_db)
    assert ass1.assessment_id is not None
    assert ass1.assessment_result == "ELIGIBLE"
    assert ass1.rules_breakdown is not None
    assert len(ass1.rules_breakdown) == 6
    assert ass1.estimated_emi > 0

    # Second assessment run
    ass2 = assess_application(app, save=True, session=seeded_db)
    assert ass2.assessment_id != ass1.assessment_id

    # Verify both assessments are preserved in relationship
    seeded_db.refresh(app)
    assert len(app.assessments) == 2


def test_legacy_application_backward_compatibility(seeded_db):
    """Legacy application with product_id=None evaluates gracefully without errors."""
    user = seeded_db.query(User).filter_by(email="borrower01@example.test").first()

    legacy_app = LoanApplication(
        application_id="APP-LEGACY-01",
        customer_id=user.user_id,
        applicant_name=user.full_name,
        monthly_income=45000.0,
        requested_amount=100000.0,
        term_months=24,
        product_id=None,  # Legacy Phase 1-6 application
        status="PENDING_REVIEW",
    )
    seeded_db.add(legacy_app)
    seeded_db.commit()

    ass = assess_application(legacy_app, save=True, session=seeded_db)
    assert ass.assessment_result == "ELIGIBLE"
    assert ass.rules_breakdown is not None
    assert len(ass.rules_breakdown) == 6
