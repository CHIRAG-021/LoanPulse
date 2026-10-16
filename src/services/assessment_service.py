"""Deterministic rule-based assessment service for LoanPulse.

Calculates loan eligibility based on predefined criteria without AI/ML.
Follows docs/04_requirements.md (BR-03/TR-03) and Phase 7 Advanced Rule Engine requirements.
"""
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.models import db, Assessment, AssessmentRule, LoanApplication, LoanProduct
from src.services.validation_service import validate_assessment_inputs, ValidationError
from src.services.financial_service import calculate_emi


@dataclass
class AssessmentResult:
    """Structured result of an eligibility assessment."""
    assessment_result: str
    calculated_ratio: float
    rule_id: int
    rule_name: str
    is_eligible: bool
    rules_breakdown: list[dict] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    estimated_emi: float = 0.0
    affordability_ratio: float = 0.0


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
    """Evaluate inputs against a specified rule configuration (Phase 1-6 compatibility).
    
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
    try:
        active_rule = s.query(AssessmentRule).filter_by(active=True).first()
        if active_rule:
            return active_rule
    except Exception:
        pass
    
    # If no active rule exists in database, query rule 1 or persist it so FK constraints succeed
    try:
        rule = s.get(AssessmentRule, 1)
        if not rule:
            rule = AssessmentRule(
                rule_id=1,
                rule_name="Standard Eligibility Rule",
                min_monthly_income=30000.0,
                max_loan_to_income_ratio=0.50,
                min_term_months=12,
                max_term_months=60,
                result_if_pass="ELIGIBLE",
                active=True,
            )
            s.add(rule)
            s.commit()
        elif not rule.active:
            rule.active = True
            s.commit()
        return rule
    except Exception:
        try:
            s.rollback()
            return s.query(AssessmentRule).first() or s.get(AssessmentRule, 1) or AssessmentRule(
                rule_id=1,
                rule_name="Standard Eligibility Rule",
                min_monthly_income=30000.0,
                max_loan_to_income_ratio=0.50,
                min_term_months=12,
                max_term_months=60,
                result_if_pass="ELIGIBLE",
                active=True,
            )
        except Exception:
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


def evaluate_product_rules(
    monthly_income: float,
    requested_amount: float,
    term_months: int,
    product: LoanProduct,
    existing_obligations: float = 0.0,
    employment_type: str | None = None,
) -> tuple[bool, str, float, float, float, list[dict], list[str]]:
    """Evaluate an application against product criteria using 6 deterministic rules (Phase 7).
    
    Rules evaluated:
    1. Minimum Income
    2. Loan Amount
    3. Tenure
    4. Loan-to-Income Ratio
    5. Affordability (Existing Obligations + Estimated EMI)
    6. Employment Requirement
    
    Returns:
      (is_eligible, result_string, lti_ratio, affordability_ratio, estimated_emi, rules_breakdown, failure_reasons)
    """
    lti_ratio = calculate_ratio(requested_amount, monthly_income)
    
    # Calculate estimated EMI using financial service
    try:
        emi_calc = calculate_emi(requested_amount, product.annual_interest_rate, term_months)
        estimated_emi = emi_calc["monthly_emi"]
    except Exception:
        estimated_emi = round(requested_amount / term_months, 2)
    
    total_obligations = round(float(existing_obligations or 0.0) + estimated_emi, 2)
    affordability_ratio = round(total_obligations / monthly_income, 2) if monthly_income > 0 else 1.0
    affordability_limit = round(monthly_income * 0.50, 2)  # 50% max debt burden ratio
    
    breakdown: list[dict] = []
    failure_reasons: list[str] = []

    # Rule 1: Minimum Monthly Income
    r1_pass = monthly_income >= float(product.min_monthly_income)
    if not r1_pass:
        msg = f"Monthly income (₹{monthly_income:,.2f}) does not meet the minimum requirement of ₹{product.min_monthly_income:,.2f} for this loan product."
        failure_reasons.append(msg)
    else:
        msg = f"Monthly income satisfies the required threshold of ₹{product.min_monthly_income:,.2f}."
    breakdown.append({
        "rule_key": "income",
        "rule_name": "Income Requirement",
        "passed": r1_pass,
        "criterion": f"Monthly income ≥ ₹{product.min_monthly_income:,.2f}",
        "actual_value": f"₹{monthly_income:,.2f}",
        "message": msg,
    })

    # Rule 2: Loan Amount Range
    r2_pass = float(product.min_amount) <= requested_amount <= float(product.max_amount)
    if requested_amount < float(product.min_amount):
        msg = f"Requested amount (₹{requested_amount:,.2f}) is below the minimum permitted amount of ₹{product.min_amount:,.2f}."
        failure_reasons.append(msg)
    elif requested_amount > float(product.max_amount):
        msg = f"Requested amount (₹{requested_amount:,.2f}) exceeds the maximum permitted amount of ₹{product.max_amount:,.2f} for this loan product."
        failure_reasons.append(msg)
    else:
        msg = f"Requested amount is within permitted limits (₹{product.min_amount:,.2f} – ₹{product.max_amount:,.2f})."
    breakdown.append({
        "rule_key": "amount",
        "rule_name": "Loan Amount",
        "passed": r2_pass,
        "criterion": f"₹{product.min_amount:,.2f} to ₹{product.max_amount:,.2f}",
        "actual_value": f"₹{requested_amount:,.2f}",
        "message": msg,
    })

    # Rule 3: Tenure Range
    r3_pass = int(product.min_term_months) <= term_months <= int(product.max_term_months)
    if term_months < int(product.min_term_months):
        msg = f"Requested tenure of {term_months} months is below the minimum allowed tenure of {product.min_term_months} months."
        failure_reasons.append(msg)
    elif term_months > int(product.max_term_months):
        msg = f"Requested tenure of {term_months} months exceeds the maximum allowed tenure of {product.max_term_months} months."
        failure_reasons.append(msg)
    else:
        msg = f"Tenure is within permissible range ({product.min_term_months} – {product.max_term_months} months)."
    breakdown.append({
        "rule_key": "tenure",
        "rule_name": "Term Requirement",
        "passed": r3_pass,
        "criterion": f"{product.min_term_months} to {product.max_term_months} months",
        "actual_value": f"{term_months} months",
        "message": msg,
    })

    # Rule 4: Loan-to-Income Ratio
    r4_pass = lti_ratio <= float(product.max_loan_to_income_ratio)
    if not r4_pass:
        msg = f"Loan-to-income ratio ({lti_ratio:.2f}) exceeds the maximum permitted ratio of {product.max_loan_to_income_ratio:.2f}."
        failure_reasons.append(msg)
    else:
        msg = f"Loan-to-income ratio ({lti_ratio:.2f}) is within the allowable limit of {product.max_loan_to_income_ratio:.2f}."
    breakdown.append({
        "rule_key": "lti_ratio",
        "rule_name": "Loan-to-Income Ratio",
        "passed": r4_pass,
        "criterion": f"Ratio ≤ {product.max_loan_to_income_ratio:.2f} ({int(product.max_loan_to_income_ratio * 100)}% of annual income)",
        "actual_value": f"{lti_ratio:.2f} ({int(lti_ratio * 100)}% of annual income)",
        "message": msg,
    })

    # Rule 5: Existing Monthly Obligations & Affordability
    r5_pass = total_obligations <= affordability_limit
    if not r5_pass:
        msg = f"Affordability cap exceeded: Estimated monthly debt obligations (₹{total_obligations:,.2f} including ₹{estimated_emi:,.2f} EMI) exceed the permitted affordability threshold of 50% of monthly income (₹{affordability_limit:,.2f})."
        failure_reasons.append(msg)
    else:
        msg = f"Total monthly obligations (₹{total_obligations:,.2f}) are affordable within 50% of monthly income (₹{affordability_limit:,.2f})."
    breakdown.append({
        "rule_key": "affordability",
        "rule_name": "Affordability",
        "passed": r5_pass,
        "criterion": f"Total obligations ≤ 50% of monthly income (₹{affordability_limit:,.2f})",
        "actual_value": f"₹{total_obligations:,.2f} ({int(affordability_ratio * 100)}% of income)",
        "message": msg,
    })

    # Rule 6: Employment Requirement
    emp_clean = (employment_type or "").strip().upper()
    if emp_clean in ("UNEMPLOYED", "NONE"):
        r6_pass = False
        msg = "Employment requirement not met: Applicant employment status is marked as unemployed without verifiable active employment or qualifying co-signer."
        failure_reasons.append(msg)
    else:
        r6_pass = True
        label = emp_clean.replace("_", " ").title() if emp_clean else "Verified Income"
        msg = f"Employment classification ({label}) verified and compliant with policy."
    breakdown.append({
        "rule_key": "employment",
        "rule_name": "Employment Requirement",
        "passed": r6_pass,
        "criterion": "Active employment (Salaried, Self-Employed, or Business Owner)",
        "actual_value": emp_clean.replace("_", " ").title() if emp_clean else "Verified Income",
        "message": msg,
    })

    is_eligible = r1_pass and r2_pass and r3_pass and r4_pass and r5_pass and r6_pass
    result_str = "ELIGIBLE" if is_eligible else "NOT_ELIGIBLE"
    return is_eligible, result_str, lti_ratio, affordability_ratio, estimated_emi, breakdown, failure_reasons


def assess_application_data(
    data: dict[str, Any],
    rule: AssessmentRule | None = None,
    product: LoanProduct | None = None,
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

    s = session or db.session
    active_rule = rule or get_default_active_rule(s)

    # If product is provided, run 6-rule product evaluation
    if product is not None:
        is_eligible, result, ratio, aff_ratio, emi, breakdown, failures = evaluate_product_rules(
            monthly_income=income,
            requested_amount=amount,
            term_months=term,
            product=product,
            existing_obligations=float(data.get("existing_obligations") or 0.0),
            employment_type=data.get("employment_type"),
        )
        return AssessmentResult(
            assessment_result=result,
            calculated_ratio=ratio,
            rule_id=active_rule.rule_id,
            rule_name=f"{product.product_name} Underwriting Rules",
            is_eligible=is_eligible,
            rules_breakdown=breakdown,
            failure_reasons=failures,
            estimated_emi=emi,
            affordability_ratio=aff_ratio,
        )

    # Standard rule evaluation fallback for Phase 2 compatibility
    result, ratio = evaluate_rules(income, amount, term, active_rule)

    # Construct standard breakdown for transparency
    breakdown = [
        {
            "rule_key": "income",
            "rule_name": "Income Requirement",
            "passed": income >= float(active_rule.min_monthly_income),
            "criterion": f"Monthly income ≥ ₹{active_rule.min_monthly_income:,.2f}",
            "actual_value": f"₹{income:,.2f}",
            "message": "Income satisfies threshold" if income >= float(active_rule.min_monthly_income) else "Income below threshold",
        },
        {
            "rule_key": "lti_ratio",
            "rule_name": "Loan-to-Income Ratio",
            "passed": ratio <= float(active_rule.max_loan_to_income_ratio),
            "criterion": f"Ratio ≤ {active_rule.max_loan_to_income_ratio:.2f}",
            "actual_value": f"{ratio:.2f}",
            "message": "Ratio within limit" if ratio <= float(active_rule.max_loan_to_income_ratio) else "Ratio exceeds limit",
        },
        {
            "rule_key": "tenure",
            "rule_name": "Term Requirement",
            "passed": float(active_rule.min_term_months) <= term <= float(active_rule.max_term_months),
            "criterion": f"{active_rule.min_term_months} to {active_rule.max_term_months} months",
            "actual_value": f"{term} months",
            "message": "Tenure valid" if float(active_rule.min_term_months) <= term <= float(active_rule.max_term_months) else "Tenure invalid",
        },
    ]

    return AssessmentResult(
        assessment_result=result,
        calculated_ratio=ratio,
        rule_id=active_rule.rule_id,
        rule_name=active_rule.rule_name,
        is_eligible=(result == active_rule.result_if_pass),
        rules_breakdown=breakdown,
        failure_reasons=[] if result == active_rule.result_if_pass else ["Application failed one or more rule criteria."],
    )


def assess_application(
    application: LoanApplication,
    rule: AssessmentRule | None = None,
    product: LoanProduct | None = None,
    save: bool = False,
    session=None,
) -> Assessment:
    """Assess an existing LoanApplication model instance.
    
    Validates application fields before assessment. Raises ValidationError on invalid inputs.
    Optionally persists a new Assessment record if save=True (preserving assessment history).
    """
    income, amount, term = validate_assessment_inputs(
        monthly_income=application.monthly_income,
        requested_amount=application.requested_amount,
        term_months=application.term_months,
    )

    s = session or db.session
    active_rule = rule or get_default_active_rule(s)

    # Determine product to use for Phase 7 advanced evaluation
    eval_product = product or application.loan_product
    if eval_product is None and application.product_id:
        eval_product = s.get(LoanProduct, application.product_id)

    if eval_product is not None:
        is_eligible, result_str, ratio, aff_ratio, emi, breakdown, failures = evaluate_product_rules(
            monthly_income=income,
            requested_amount=amount,
            term_months=term,
            product=eval_product,
            existing_obligations=float(application.existing_obligations or 0.0),
            employment_type=application.employment_type,
        )
    else:
        # Fallback to rule evaluation for legacy/unassociated applications
        result_str, ratio = evaluate_rules(income, amount, term, active_rule)
        is_eligible = (result_str == active_rule.result_if_pass)
        emi = round(amount / term, 2)
        total_ob = float(application.existing_obligations or 0.0) + emi
        aff_ratio = round(total_ob / income, 2) if income > 0 else 1.0
        failures = [] if is_eligible else ["Application does not satisfy eligibility criteria."]
        breakdown = [
            {
                "rule_key": "income",
                "rule_name": "Income Requirement",
                "passed": income >= float(active_rule.min_monthly_income),
                "criterion": f"Monthly income ≥ ₹{active_rule.min_monthly_income:,.2f}",
                "actual_value": f"₹{income:,.2f}",
                "message": "Income satisfies threshold" if income >= float(active_rule.min_monthly_income) else f"Monthly income (₹{income:,.2f}) does not meet the minimum requirement.",
            },
            {
                "rule_key": "amount",
                "rule_name": "Loan Amount",
                "passed": amount > 0,
                "criterion": "Positive amount",
                "actual_value": f"₹{amount:,.2f}",
                "message": "Amount is valid",
            },
            {
                "rule_key": "tenure",
                "rule_name": "Term Requirement",
                "passed": float(active_rule.min_term_months) <= term <= float(active_rule.max_term_months),
                "criterion": f"{active_rule.min_term_months} to {active_rule.max_term_months} months",
                "actual_value": f"{term} months",
                "message": "Tenure within limits" if float(active_rule.min_term_months) <= term <= float(active_rule.max_term_months) else "Tenure outside limits",
            },
            {
                "rule_key": "lti_ratio",
                "rule_name": "Loan-to-Income Ratio",
                "passed": ratio <= float(active_rule.max_loan_to_income_ratio),
                "criterion": f"Ratio ≤ {active_rule.max_loan_to_income_ratio:.2f}",
                "actual_value": f"{ratio:.2f}",
                "message": "Ratio compliant" if ratio <= float(active_rule.max_loan_to_income_ratio) else f"Loan-to-income ratio ({ratio:.2f}) exceeds maximum threshold.",
            },
            {
                "rule_key": "affordability",
                "rule_name": "Affordability",
                "passed": total_ob <= income * 0.50,
                "criterion": f"Obligations ≤ 50% income (₹{income * 0.50:,.2f})",
                "actual_value": f"₹{total_ob:,.2f}",
                "message": "Affordable debt obligation" if total_ob <= income * 0.50 else "Debt obligations exceed affordability limit.",
            },
            {
                "rule_key": "employment",
                "rule_name": "Employment Requirement",
                "passed": (application.employment_type or "").upper() != "UNEMPLOYED",
                "criterion": "Active employment",
                "actual_value": application.employment_type or "Declared",
                "message": "Employment status verified",
            },
        ]

    # Create a fresh Assessment record (preserving historical assessments)
    assessment = Assessment(
        application_id=application.application_id,
        rule_id=active_rule.rule_id,
        assessment_result=result_str,
        calculated_ratio=ratio,
        assessed_at=date.today(),
        rules_breakdown_json=json.dumps(breakdown),
        failure_reasons_json=json.dumps(failures),
        estimated_emi=emi,
        affordability_ratio=aff_ratio,
    )

    if save:
        try:
            s.add(assessment)
            s.commit()
        except Exception:
            s.rollback()
            try:
                # Ensure the referenced rule exists and retry commit
                active_rule = get_default_active_rule(s)
                assessment.rule_id = active_rule.rule_id
                s.add(assessment)
                s.commit()
            except Exception as e2:
                s.rollback()
                import logging
                logging.getLogger(__name__).warning(
                    f"Unable to persist assessment record for {application.application_id}: {e2}"
                )

    return assessment
