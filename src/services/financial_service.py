"""Financial calculation service for LoanPulse (Phase 7 EMI Calculator).

Provides deterministic reducing-balance EMI calculations using Decimal arithmetic
with round-half-up rounding to prevent floating-point discrepancies.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from src.services.validation_service import ValidationError


def validate_calculator_inputs(
    principal: Any,
    annual_interest_rate: Any,
    term_months: Any,
) -> tuple[Decimal, Decimal, int]:
    """Validate and convert raw calculator inputs into typed Decimal/int values."""
    errors: dict[str, str] = {}

    # 1. Principal
    if principal is None or (isinstance(principal, str) and not principal.strip()):
        errors["principal"] = "Principal loan amount is required."
        p_dec = Decimal("0")
    else:
        try:
            p_dec = Decimal(str(principal).strip())
            if p_dec <= Decimal("0"):
                errors["principal"] = "Principal loan amount must be greater than zero."
        except (InvalidOperation, ValueError, TypeError):
            errors["principal"] = "Principal must be a valid numeric amount."
            p_dec = Decimal("0")

    # 2. Annual interest rate
    if annual_interest_rate is None or (isinstance(annual_interest_rate, str) and not annual_interest_rate.strip()):
        errors["annual_interest_rate"] = "Annual interest rate is required."
        rate_dec = Decimal("0")
    else:
        try:
            rate_dec = Decimal(str(annual_interest_rate).strip())
            if rate_dec < Decimal("0"):
                errors["annual_interest_rate"] = "Annual interest rate cannot be negative."
            elif rate_dec > Decimal("100"):
                errors["annual_interest_rate"] = "Annual interest rate cannot exceed 100%."
        except (InvalidOperation, ValueError, TypeError):
            errors["annual_interest_rate"] = "Annual interest rate must be a valid numeric rate."
            rate_dec = Decimal("0")

    # 3. Term in months
    if term_months is None or (isinstance(term_months, str) and not str(term_months).strip()):
        errors["term_months"] = "Tenure in months is required."
        n_int = 0
    else:
        try:
            n_int = int(str(term_months).strip())
            if n_int <= 0:
                errors["term_months"] = "Tenure must be at least 1 month."
            elif n_int > 360:
                errors["term_months"] = "Tenure cannot exceed 360 months (30 years)."
        except (ValueError, TypeError):
            errors["term_months"] = "Tenure must be an integer."
            n_int = 0

    if errors:
        raise ValidationError("Invalid loan calculator parameters", errors=errors)

    return p_dec, rate_dec, n_int


def calculate_emi(
    principal: float | int | str | Decimal,
    annual_interest_rate: float | int | str | Decimal,
    term_months: int | str,
) -> dict[str, float]:
    """Calculate monthly reducing-balance EMI and repayment figures.

    Standard Reducing-Balance Formula:
      EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)
      where:
        P = principal loan amount
        r = monthly interest rate = (annual_interest_rate / 100) / 12
        n = tenure in months

    Zero-Interest Case:
      If annual_interest_rate == 0:
        EMI = P / n
    """
    P, rate_pct, n = validate_calculator_inputs(principal, annual_interest_rate, term_months)
    two_places = Decimal("0.01")

    if rate_pct == Decimal("0"):
        emi = (P / Decimal(str(n))).quantize(two_places, rounding=ROUND_HALF_UP)
        total_payable = (emi * Decimal(str(n))).quantize(two_places, rounding=ROUND_HALF_UP)
        total_interest = Decimal("0.00")
    else:
        # Monthly fractional interest rate
        r = (rate_pct / Decimal("100")) / Decimal("12")
        # Growth factor (1 + r)^n
        factor = (Decimal("1") + r) ** n
        # Standard formula
        emi_unrounded = P * r * factor / (factor - Decimal("1"))
        emi = emi_unrounded.quantize(two_places, rounding=ROUND_HALF_UP)
        total_payable = (emi * Decimal(str(n))).quantize(two_places, rounding=ROUND_HALF_UP)
        total_interest = (total_payable - P).quantize(two_places, rounding=ROUND_HALF_UP)
        if total_interest < Decimal("0.00"):
            total_interest = Decimal("0.00")

    return {
        "principal": float(P),
        "annual_interest_rate": float(rate_pct),
        "effective_rate_pa": float(rate_pct),
        "term_months": n,
        "monthly_emi": float(emi),
        "total_interest": float(total_interest),
        "total_payable": float(total_payable),
        "total_payment": float(total_payable),
        "interest_ratio": round(float(total_interest / P * 100), 2) if P > 0 else 0.0,
    }
