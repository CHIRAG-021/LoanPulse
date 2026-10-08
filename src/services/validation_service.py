"""Validation service for LoanPulse.

Validates application and assessment inputs according to business requirements
and data constraints in docs/data_dictionary.md and docs/04_requirements.md.
"""
from dataclasses import dataclass, field
from typing import Any


class ValidationError(ValueError):
    """Exception raised when application or assessment input validation fails."""

    def __init__(self, message: str, errors: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}

    def __str__(self):
        if self.errors:
            error_details = ", ".join(f"{k}: {v}" for k, v in self.errors.items())
            return f"{self.message} ({error_details})"
        return self.message


@dataclass
class ValidationResult:
    """Result of validation check."""
    is_valid: bool
    errors: dict[str, str] = field(default_factory=dict)
    cleaned_data: dict[str, Any] = field(default_factory=dict)


def validate_loan_application(data: dict[str, Any], require_customer_id: bool = False) -> ValidationResult:
    """Validate loan application fields.
    
    Checks required presence, data types, and value domain constraints:
    - applicant_name: required, non-empty, max 100 chars
    - monthly_income: required, numeric, > 0
    - requested_amount (or loan_amount): required, numeric, > 0
    - term_months: required, integer, 12 <= term <= 60
    - customer_id: optional (or required if specified), positive integer
    """
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}

    # 1. applicant_name
    name = data.get("applicant_name")
    if name is None or (isinstance(name, str) and not name.strip()):
        errors["applicant_name"] = "Applicant name is required and cannot be blank."
    elif not isinstance(name, str):
        errors["applicant_name"] = "Applicant name must be a string."
    elif len(name.strip()) > 100:
        errors["applicant_name"] = "Applicant name cannot exceed 100 characters."
    else:
        cleaned["applicant_name"] = name.strip()

    # 2. customer_id (if required or provided)
    cid = data.get("customer_id")
    if cid is not None and cid != "":
        try:
            cid_int = int(cid)
            if cid_int <= 0:
                errors["customer_id"] = "Customer ID must be a positive integer."
            else:
                cleaned["customer_id"] = cid_int
        except (ValueError, TypeError):
            errors["customer_id"] = "Customer ID must be an integer."
    elif require_customer_id:
        errors["customer_id"] = "Customer ID is required."

    # 3. monthly_income
    raw_income = data.get("monthly_income")
    if raw_income is None or (isinstance(raw_income, str) and not raw_income.strip()):
        errors["monthly_income"] = "Monthly income is required."
    else:
        try:
            income_val = float(raw_income)
            if income_val <= 0:
                errors["monthly_income"] = "Monthly income must be greater than zero."
            else:
                cleaned["monthly_income"] = round(income_val, 2)
        except (ValueError, TypeError):
            errors["monthly_income"] = "Monthly income must be a valid numeric value."

    # 4. requested_amount / loan_amount
    # Accept either 'loan_amount' or 'requested_amount'
    amount_key = "loan_amount" if "loan_amount" in data else "requested_amount"
    raw_amount = data.get("requested_amount")
    if raw_amount is None or raw_amount == "":
        raw_amount = data.get("loan_amount")

    if raw_amount is None or (isinstance(raw_amount, str) and not raw_amount.strip()):
        errors[amount_key] = "Loan amount is required and cannot be missing."
        if amount_key != "loan_amount" and "loan_amount" in data:
            errors["loan_amount"] = errors[amount_key]
        if amount_key != "requested_amount" and "requested_amount" in data:
            errors["requested_amount"] = errors[amount_key]
    else:
        try:
            amount_val = float(raw_amount)
            if amount_val <= 0:
                errors[amount_key] = "Loan amount must be greater than zero."
            else:
                cleaned["requested_amount"] = round(amount_val, 2)
                cleaned["loan_amount"] = round(amount_val, 2)
        except (ValueError, TypeError):
            errors[amount_key] = "Loan amount must be a valid numeric value."
            if amount_key == "loan_amount":
                errors["requested_amount"] = errors[amount_key]
            else:
                errors["loan_amount"] = errors[amount_key]

    # 5. term_months
    raw_term = data.get("term_months")
    if raw_term is None or (isinstance(raw_term, str) and not raw_term.strip()):
        errors["term_months"] = "Loan term in months is required."
    else:
        try:
            term_val = int(raw_term)
            if term_val < 12 or term_val > 60:
                errors["term_months"] = "Loan term must be between 12 and 60 months."
            else:
                cleaned["term_months"] = term_val
        except (ValueError, TypeError):
            errors["term_months"] = "Loan term must be a valid integer."

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, cleaned_data=cleaned if is_valid else {})


def validate_or_raise(data: dict[str, Any], require_customer_id: bool = False) -> dict[str, Any]:
    """Validate application data and return cleaned dict or raise ValidationError."""
    res = validate_loan_application(data, require_customer_id=require_customer_id)
    if not res.is_valid:
        raise ValidationError("Application validation failed", errors=res.errors)
    return res.cleaned_data


def validate_assessment_inputs(
    monthly_income: Any,
    requested_amount: Any,
    term_months: Any,
) -> tuple[float, float, int]:
    """Validate raw inputs before rule assessment.
    
    Raises ValidationError if any parameter is missing, non-numeric, or non-positive.
    """
    errors: dict[str, str] = {}

    # Monthly income
    if monthly_income is None or (isinstance(monthly_income, str) and not str(monthly_income).strip()):
        errors["monthly_income"] = "Monthly income is required for assessment."
        parsed_income = 0.0
    else:
        try:
            parsed_income = float(monthly_income)
            if parsed_income <= 0:
                errors["monthly_income"] = "Monthly income must be greater than zero."
        except (ValueError, TypeError):
            errors["monthly_income"] = "Monthly income must be a valid number."
            parsed_income = 0.0

    # Requested amount
    if requested_amount is None or (isinstance(requested_amount, str) and not str(requested_amount).strip()):
        errors["requested_amount"] = "Requested loan amount is required for assessment."
        parsed_amount = 0.0
    else:
        try:
            parsed_amount = float(requested_amount)
            if parsed_amount <= 0:
                errors["requested_amount"] = "Requested loan amount must be greater than zero."
        except (ValueError, TypeError):
            errors["requested_amount"] = "Requested loan amount must be a valid number."
            parsed_amount = 0.0

    # Term months
    if term_months is None or (isinstance(term_months, str) and not str(term_months).strip()):
        errors["term_months"] = "Loan term in months is required for assessment."
        parsed_term = 0
    else:
        try:
            parsed_term = int(term_months)
            if parsed_term <= 0:
                errors["term_months"] = "Loan term must be a positive integer."
        except (ValueError, TypeError):
            errors["term_months"] = "Loan term must be a valid integer."
            parsed_term = 0

    if errors:
        raise ValidationError("Invalid assessment inputs", errors=errors)

    return parsed_income, parsed_amount, parsed_term
