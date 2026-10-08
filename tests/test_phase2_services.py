"""Tests for Phase 2: Validation service and deterministic rule assessment service.

Implements test cases:
- TC-05 (Rule-eligible assessment)
- TC-06 (Invalid assessment input rejected)
- TC-07 (Deterministic assessment with identical inputs)
- TC-16 (Missing required loan_amount rejected)
- TC-17 (Invalid field format loan_amount='abc' rejected)
- TC-22 (Multiple invalid/missing fields identified)
"""
import pytest
from src.models import AssessmentRule, LoanApplication, Assessment
from src.services.validation_service import (
    validate_loan_application,
    validate_or_raise,
    validate_assessment_inputs,
    ValidationError,
)
from src.services.assessment_service import (
    calculate_ratio,
    assess_application_data,
    assess_application,
)


# ============================================================================
# TC-05: Assess an application that satisfies configured rules (happy path)
# ============================================================================
def test_tc_05_assess_eligible_application(seeded_db):
    """TC-05: System produces configured positive assessment result for eligible inputs."""
    # Test data from docs/07_test_cases.md: income=60000, amount=200000, term=24
    rule = seeded_db.query(AssessmentRule).filter_by(rule_id=1, active=True).first()
    assert rule is not None

    data = {
        "monthly_income": 60000.0,
        "requested_amount": 200000.0,
        "term_months": 24,
    }
    result = assess_application_data(data, rule=rule, session=seeded_db)

    assert result.assessment_result == "ELIGIBLE"
    assert result.is_eligible is True
    assert result.calculated_ratio == 0.28  # 200000 / (60000 * 12) = 0.2777... -> 0.28
    assert result.rule_id == 1

    # Also test with seeded application APP-0003
    app_0003 = seeded_db.get(LoanApplication, "APP-0003")
    assert app_0003 is not None
    assessment = assess_application(app_0003, rule=rule, session=seeded_db)
    assert assessment.assessment_result == "ELIGIBLE"
    assert assessment.calculated_ratio == 0.28


# ============================================================================
# TC-06: Assess an application with invalid assessment input (invalid input)
# ============================================================================
def test_tc_06_assess_invalid_input_rejected(seeded_db):
    """TC-06: System rejects invalid income value and does not produce an assessment result."""
    rule = seeded_db.query(AssessmentRule).filter_by(rule_id=1, active=True).first()

    # Test data: Income=-5000; requested amount=200000
    invalid_data = {
        "monthly_income": -5000.0,
        "requested_amount": 200000.0,
        "term_months": 24,
    }

    # Must raise ValidationError and not produce an assessment result
    with pytest.raises(ValidationError) as exc_info:
        assess_application_data(invalid_data, rule=rule, session=seeded_db)

    assert "monthly_income" in exc_info.value.errors or "Monthly income" in str(exc_info.value)

    # Also test on a LoanApplication instance with negative income
    invalid_app = LoanApplication(
        application_id="APP-TEST-NEG",
        customer_id=1,
        applicant_name="Test Borrower",
        monthly_income=-5000.0,
        requested_amount=200000.0,
        term_months=24,
        status="PENDING_REVIEW",
    )
    with pytest.raises(ValidationError):
        assess_application(invalid_app, rule=rule, session=seeded_db)


# ============================================================================
# TC-07: Same inputs produce the same rule result (edge / determinism)
# ============================================================================
def test_tc_07_deterministic_assessment(seeded_db):
    """TC-07: Two applications with identical inputs produce identical assessment results."""
    rule = seeded_db.query(AssessmentRule).filter_by(rule_id=1, active=True).first()

    # Two distinct applications with identical assessment inputs (income=50000, amount=150000, term=24)
    # Matching seeded APP-0004 and APP-0005
    input_a = {"monthly_income": 50000.0, "requested_amount": 150000.0, "term_months": 24}
    input_b = {"monthly_income": 50000.0, "requested_amount": 150000.0, "term_months": 24}

    result_a = assess_application_data(input_a, rule=rule, session=seeded_db)
    result_b = assess_application_data(input_b, rule=rule, session=seeded_db)

    assert result_a.assessment_result == result_b.assessment_result == "ELIGIBLE"
    assert result_a.calculated_ratio == result_b.calculated_ratio == 0.25
    assert result_a.rule_id == result_b.rule_id


# ============================================================================
# TC-16: Reject an application with missing required information (invalid input)
# ============================================================================
def test_tc_16_reject_missing_loan_amount():
    """TC-16: Required field loan_amount is blank; submission rejected and field identified as missing."""
    data = {
        "applicant_name": "Test Borrower",
        "monthly_income": 50000.0,
        "loan_amount": "",  # Blank required field
        "term_months": 24,
    }

    result = validate_loan_application(data)
    assert result.is_valid is False
    assert "loan_amount" in result.errors or "requested_amount" in result.errors
    err_msg = result.errors.get("loan_amount") or result.errors.get("requested_amount")
    assert "missing" in err_msg.lower() or "required" in err_msg.lower()

    # validate_or_raise must also raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        validate_or_raise(data)
    assert "loan_amount" in exc_info.value.errors or "requested_amount" in exc_info.value.errors


# ============================================================================
# TC-17: Reject an application with an invalid field format (invalid input)
# ============================================================================
def test_tc_17_reject_invalid_loan_amount_format():
    """TC-17: Loan amount='abc'; submission rejected and field identified as invalid."""
    data = {
        "applicant_name": "Test Borrower",
        "monthly_income": 50000.0,
        "loan_amount": "abc",  # Invalid non-numeric format
        "term_months": 24,
    }

    result = validate_loan_application(data)
    assert result.is_valid is False
    assert "loan_amount" in result.errors or "requested_amount" in result.errors
    err_msg = result.errors.get("loan_amount") or result.errors.get("requested_amount")
    assert "valid" in err_msg.lower() or "numeric" in err_msg.lower()

    with pytest.raises(ValidationError):
        validate_or_raise(data)


# ============================================================================
# TC-22: Validate required fields and basic field formats (standing test)
# ============================================================================
def test_tc_22_validate_multiple_invalid_fields():
    """TC-22: Missing name, income='abc', loan amount=-1000; each invalid/missing field is identified."""
    data = {
        "applicant_name": "",       # Missing name
        "monthly_income": "abc",    # Invalid format
        "loan_amount": -1000.0,     # Invalid negative amount
        "term_months": 24,
    }

    result = validate_loan_application(data)
    assert result.is_valid is False

    # Each invalid or missing field must be identified in the error dictionary
    assert "applicant_name" in result.errors
    assert "monthly_income" in result.errors
    assert "loan_amount" in result.errors or "requested_amount" in result.errors

    # Verify meaningful error messages
    assert "required" in result.errors["applicant_name"].lower()
    assert "numeric" in result.errors["monthly_income"].lower() or "valid" in result.errors["monthly_income"].lower()
    amount_err = result.errors.get("loan_amount") or result.errors.get("requested_amount")
    assert "greater than zero" in amount_err.lower() or "positive" in amount_err.lower()


# ============================================================================
# Additional boundary condition tests
# ============================================================================
def test_assessment_boundary_conditions(seeded_db):
    """Verify exact rule threshold boundaries: min income, max ratio, min/max term."""
    rule = seeded_db.query(AssessmentRule).filter_by(rule_id=1, active=True).first()

    # 1. Exact min income boundary (30000.0) -> eligible
    res_min_inc = assess_application_data(
        {"monthly_income": 30000.0, "requested_amount": 90000.0, "term_months": 12},
        rule=rule,
        session=seeded_db,
    )
    assert res_min_inc.is_eligible is True
    assert res_min_inc.assessment_result == "ELIGIBLE"

    # Just below min income boundary (29999.0) -> not eligible
    res_below_inc = assess_application_data(
        {"monthly_income": 29999.0, "requested_amount": 90000.0, "term_months": 12},
        rule=rule,
        session=seeded_db,
    )
    assert res_below_inc.is_eligible is False
    assert res_below_inc.assessment_result == "NOT_ELIGIBLE"

    # 2. Exact max ratio boundary (0.50) -> eligible
    # Income=50000, annual=600000, amount=300000 -> ratio=0.50
    res_max_ratio = assess_application_data(
        {"monthly_income": 50000.0, "requested_amount": 300000.0, "term_months": 12},
        rule=rule,
        session=seeded_db,
    )
    assert res_max_ratio.is_eligible is True
    assert res_max_ratio.calculated_ratio == 0.50

    # Ratio slightly above boundary (amount=306000 -> ratio=0.51) -> not eligible
    res_above_ratio = assess_application_data(
        {"monthly_income": 50000.0, "requested_amount": 306000.0, "term_months": 12},
        rule=rule,
        session=seeded_db,
    )
    assert res_above_ratio.is_eligible is False
    assert res_above_ratio.calculated_ratio == 0.51
    assert res_above_ratio.assessment_result == "NOT_ELIGIBLE"


def test_assess_application_persistence(seeded_db):
    """Verify assess_application persists Assessment record when save=True."""
    app_0001 = seeded_db.get(LoanApplication, "APP-0001")
    assert app_0001 is not None

    initial_count = seeded_db.query(Assessment).count()
    assessment = assess_application(app_0001, save=True, session=seeded_db)

    assert assessment.assessment_id is not None
    assert seeded_db.query(Assessment).count() == initial_count + 1
    assert assessment.application_id == "APP-0001"
