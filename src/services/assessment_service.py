"""Deterministic rule-based assessment service for LoanPulse.

Calculates loan eligibility based on predefined criteria without AI/ML.
Follows docs/04_requirements.md (BR-03/TR-03) and docs/09_data_design.md.
"""
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.models import db, Assessment, AssessmentRule, LoanApplication
from src.services.validation_service import validate_assessment_inputs, ValidationError


@dataclass
class AssessmentResult:
    """Structured result of an eligibility assessment."""
    assessment_result: str
    calculated_ratio: float
    rule_id: int
    rule_name: str
    is_eligible: bool


def calculate_ratio(requested_amount: float, monthly_income: float) -> float:
    """Calculate loan-to-annual-income ratio rounded to two decimal places.
    
    Formula: requested_amount / (monthly_income * 12)
    Raises ValidationError if monthly_income is non-positive.
    """
    if monthly_income <= 0:
        raise ValidationError("Monthly income must be greater than zero to calculate ratio.")
    return round(requested_amount / (monthly_income * 12), 2)


def evaluate_rules(
    monthly_income: float,
    requested_amount: float,
    term_months: int,
    rule: AssessmentRule,
) -> tuple[str, float]:
    """Evaluate inputs against a specified rule configuration.
    
    Returns (assessment_result, calculated_ratio).
    """
    ratio = calculate_ratio(requested_amount, monthly_income)
    
    is_eligible = (
        monthly_income >= float(rule.min_monthly_income)
        and ratio <= float(rule.max_loan_to_income_ratio)
        and float(rule.min_term_months) <= term_months <= float(rule.max_term_months)
    )
    result = rule.result_if_pass if is_eligible else "NOT_ELIGIBLE"
    return result, ratio


def get_default_active_rule(session=None) -> AssessmentRule:
    """Fetch the active rule from the database, or return standard default."""
    s = session or db.session
    active_rule = s.query(AssessmentRule).filter_by(active=True).first()
    if active_rule:
        return active_rule
    
    # Standard documented default rule if database is empty/unseeded
    return AssessmentRule(
        rule_id=1,
        rule_name="Standard Eligibility Rule",
        min_monthly_income=30000.0,
        max_loan_to_income_ratio=0.50,
        min_term_months=12,
        max_term_months=60,
        result_if_pass="ELIGIBLE",
        active=True,
    )


def assess_application_data(
    data: dict[str, Any],
    rule: AssessmentRule | None = None,
    session=None,
) -> AssessmentResult:
    """Assess raw application data dictionary.
    
    Validates inputs before calculation. Raises ValidationError on invalid inputs.
    """
    income, amount, term = validate_assessment_inputs(
        monthly_income=data.get("monthly_income"),
        requested_amount=data.get("requested_amount", data.get("loan_amount")),
        term_months=data.get("term_months"),
    )

    active_rule = rule or get_default_active_rule(session)
    result, ratio = evaluate_rules(income, amount, term, active_rule)

    return AssessmentResult(
        assessment_result=result,
        calculated_ratio=ratio,
        rule_id=active_rule.rule_id,
        rule_name=active_rule.rule_name,
        is_eligible=(result == active_rule.result_if_pass),
    )


def assess_application(
    application: LoanApplication,
    rule: AssessmentRule | None = None,
    save: bool = False,
    session=None,
) -> Assessment:
    """Assess an existing LoanApplication model instance.
    
    Validates application fields before assessment. Raises ValidationError on invalid inputs.
    Optionally persists the Assessment record if save=True.
    """
    income, amount, term = validate_assessment_inputs(
        monthly_income=application.monthly_income,
        requested_amount=application.requested_amount,
        term_months=application.term_months,
    )

    s = session or db.session
    active_rule = rule or get_default_active_rule(s)
    result_str, ratio = evaluate_rules(income, amount, term, active_rule)

    assessment = Assessment(
        application_id=application.application_id,
        rule_id=active_rule.rule_id,
        assessment_result=result_str,
        calculated_ratio=ratio,
        assessed_at=date.today(),
    )

    if save:
        s.add(assessment)
        s.commit()

    return assessment
