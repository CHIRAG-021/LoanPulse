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


def validate_loan_application(
    data: dict[str, Any],
    require_customer_id: bool = False,
    require_product_id: bool = False,
) -> ValidationResult:
    """Validate loan application fields.
    
    Checks required presence, data types, and value domain constraints:
    - applicant_name: required, non-empty, max 100 chars
    - monthly_income: required, numeric, > 0
    - requested_amount (or loan_amount): required, numeric, > 0
    - term_months: required, integer, 12 <= term <= 60
    - customer_id: optional (or required if specified), positive integer
    - product_id: optional (or required if specified), positive integer
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
            if term_val <= 0:
                errors["term_months"] = "Loan term must be greater than zero."
            elif term_val > 360:
                errors["term_months"] = "Loan term cannot exceed 360 months."
            else:
                cleaned["term_months"] = term_val
        except (ValueError, TypeError):
            errors["term_months"] = "Loan term must be a valid integer."

    # 6. loan_purpose (Phase 6)
    allowed_purposes = {"PERSONAL", "EDUCATION", "MEDICAL", "HOME_IMPROVEMENT", "BUSINESS", "OTHER"}
    raw_purpose = data.get("loan_purpose")
    if raw_purpose is not None and str(raw_purpose).strip():
        purpose_val = str(raw_purpose).strip().upper()
        if purpose_val not in allowed_purposes:
            errors["loan_purpose"] = f"Loan purpose must be one of: {', '.join(sorted(allowed_purposes))}."
        else:
            cleaned["loan_purpose"] = purpose_val
    else:
        cleaned["loan_purpose"] = "PERSONAL"

    # 7. loan_purpose_other (Phase 6)
    raw_other = data.get("loan_purpose_other")
    if raw_other is not None and str(raw_other).strip():
        other_val = str(raw_other).strip()
        if len(other_val) > 255:
            errors["loan_purpose_other"] = "Description cannot exceed 255 characters."
        else:
            cleaned["loan_purpose_other"] = other_val
    else:
        cleaned["loan_purpose_other"] = None

    # 8. employment_type (Phase 6)
    allowed_emp_types = {"SALARIED", "SELF_EMPLOYED", "BUSINESS_OWNER", "OTHER"}
    raw_emp = data.get("employment_type")
    if raw_emp is not None and str(raw_emp).strip():
        emp_val = str(raw_emp).strip().upper()
        if emp_val not in allowed_emp_types:
            errors["employment_type"] = f"Employment type must be one of: {', '.join(sorted(allowed_emp_types))}."
        else:
            cleaned["employment_type"] = emp_val
    else:
        cleaned["employment_type"] = None

    # 9. employer_name (Phase 6)
    raw_employer = data.get("employer_name")
    if raw_employer is not None and str(raw_employer).strip():
        emp_name = str(raw_employer).strip()
        if len(emp_name) > 150:
            errors["employer_name"] = "Employer name cannot exceed 150 characters."
        else:
            cleaned["employer_name"] = emp_name
    else:
        cleaned["employer_name"] = None

    # 10. existing_obligations (Phase 6)
    raw_obligations = data.get("existing_obligations")
    if raw_obligations is not None and str(raw_obligations).strip() != "":
        try:
            ob_val = float(raw_obligations)
            if ob_val < 0:
                errors["existing_obligations"] = "Existing monthly obligations cannot be negative."
            else:
                cleaned["existing_obligations"] = round(ob_val, 2)
        except (ValueError, TypeError):
            errors["existing_obligations"] = "Existing monthly obligations must be a valid number."
    else:
        cleaned["existing_obligations"] = 0.0

    # 11. preferred_repayment_date (Phase 6)
    raw_repay_day = data.get("preferred_repayment_date")
    if raw_repay_day is not None and str(raw_repay_day).strip() != "":
        try:
            day_val = int(raw_repay_day)
            if day_val < 1 or day_val > 31:
                errors["preferred_repayment_date"] = "Preferred repayment day must be between 1 and 31."
            else:
                cleaned["preferred_repayment_date"] = day_val
        except (ValueError, TypeError):
            errors["preferred_repayment_date"] = "Preferred repayment day must be an integer between 1 and 31."
    else:
        cleaned["preferred_repayment_date"] = None

    # 12. product_id (Phase 7)
    raw_pid = data.get("product_id")
    if raw_pid is not None and str(raw_pid).strip() != "":
        try:
            pid_int = int(str(raw_pid).strip())
            if pid_int <= 0:
                errors["product_id"] = "Product ID must be a positive integer."
            else:
                cleaned["product_id"] = pid_int
        except (ValueError, TypeError):
            errors["product_id"] = "Product ID must be a valid integer."
    elif require_product_id:
        errors["product_id"] = "A valid loan product must be selected."
    else:
        cleaned["product_id"] = None

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, cleaned_data=cleaned if is_valid else {})


def validate_application_against_product(
    cleaned_data: dict[str, Any],
    product: Any,
) -> dict[str, str]:
    """Validate requested amount and tenure against a selected LoanProduct."""
    errors: dict[str, str] = {}
    if not product:
        errors["product_id"] = "Selected loan product is invalid or does not exist."
        return errors
    if not getattr(product, "active", False):
        errors["product_id"] = "Selected loan product is currently inactive."
        return errors

    amount = cleaned_data.get("requested_amount")
    if amount is not None:
        try:
            amt_val = float(amount)
            min_amt = float(product.min_amount)
            max_amt = float(product.max_amount)
            if amt_val < min_amt:
                errors["requested_amount"] = f"Requested amount is below the minimum limit of ₹{min_amt:,.2f} for {product.product_name}."
            elif amt_val > max_amt:
                errors["requested_amount"] = f"Requested amount exceeds maximum allowed limit of ₹{max_amt:,.2f} for {product.product_name}."
        except (ValueError, TypeError):
            errors["requested_amount"] = "Requested amount must be a valid numeric value."

    term = cleaned_data.get("term_months")
    if term is not None:
        try:
            term_val = int(term)
            min_term = int(product.min_term_months)
            max_term = int(product.max_term_months)
            if term_val < min_term:
                errors["term_months"] = f"Tenure is below the minimum allowed {min_term} months for {product.product_name}."
            elif term_val > max_term:
                errors["term_months"] = f"Tenure exceeds the maximum allowed {max_term} months for {product.product_name}."
        except (ValueError, TypeError):
            errors["term_months"] = "Tenure must be a valid integer."

    return errors


def validate_loan_product(data: dict[str, Any]) -> ValidationResult:
    """Validate configurable loan product fields (Phase 7)."""
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}

    # product_name
    name = data.get("product_name")
    if name is None or not str(name).strip():
        errors["product_name"] = "Product name is required."
    elif len(str(name).strip()) > 100:
        errors["product_name"] = "Product name cannot exceed 100 characters."
    else:
        cleaned["product_name"] = str(name).strip()

    # product_code
    code = data.get("product_code")
    if code is None or not str(code).strip():
        errors["product_code"] = "Product code is required."
    else:
        code_str = str(code).strip().upper()
        if len(code_str) > 50:
            errors["product_code"] = "Product code cannot exceed 50 characters."
        elif not all(c.isalnum() or c in ('_', '-') for c in code_str):
            errors["product_code"] = "Product code must contain only letters, numbers, hyphens, and underscores."
        else:
            cleaned["product_code"] = code_str

    # description
    desc = data.get("description")
    if desc is not None and str(desc).strip():
        cleaned["description"] = str(desc).strip()
    else:
        cleaned["description"] = ""

    # min_amount
    raw_min_amt = data.get("min_amount")
    min_amt = 0.0
    if raw_min_amt is None or str(raw_min_amt).strip() == "":
        errors["min_amount"] = "Minimum loan amount is required."
    else:
        try:
            min_amt = float(raw_min_amt)
            if min_amt <= 0:
                errors["min_amount"] = "Minimum loan amount must be greater than zero."
            else:
                cleaned["min_amount"] = round(min_amt, 2)
        except (ValueError, TypeError):
            errors["min_amount"] = "Minimum loan amount must be a valid number."

    # max_amount
    raw_max_amt = data.get("max_amount")
    if raw_max_amt is None or str(raw_max_amt).strip() == "":
        errors["max_amount"] = "Maximum loan amount is required."
    else:
        try:
            max_amt = float(raw_max_amt)
            if max_amt <= 0:
                errors["max_amount"] = "Maximum loan amount must be greater than zero."
            elif min_amt > 0 and max_amt < min_amt:
                errors["max_amount"] = "Maximum loan amount cannot be less than minimum loan amount."
            else:
                cleaned["max_amount"] = round(max_amt, 2)
        except (ValueError, TypeError):
            errors["max_amount"] = "Maximum loan amount must be a valid number."

    # min_term_months
    raw_min_term = data.get("min_term_months")
    min_term = 0
    if raw_min_term is None or str(raw_min_term).strip() == "":
        errors["min_term_months"] = "Minimum tenure is required."
    else:
        try:
            min_term = int(raw_min_term)
            if min_term < 1:
                errors["min_term_months"] = "Minimum tenure must be at least 1 month."
            else:
                cleaned["min_term_months"] = min_term
        except (ValueError, TypeError):
            errors["min_term_months"] = "Minimum tenure must be a valid integer."

    # max_term_months
    raw_max_term = data.get("max_term_months")
    if raw_max_term is None or str(raw_max_term).strip() == "":
        errors["max_term_months"] = "Maximum tenure is required."
    else:
        try:
            max_term = int(raw_max_term)
            if max_term < 1:
                errors["max_term_months"] = "Maximum tenure must be at least 1 month."
            elif min_term > 0 and max_term < min_term:
                errors["max_term_months"] = "Maximum tenure cannot be less than minimum tenure."
            else:
                cleaned["max_term_months"] = max_term
        except (ValueError, TypeError):
            errors["max_term_months"] = "Maximum tenure must be a valid integer."

    # annual_interest_rate
    raw_rate = data.get("annual_interest_rate")
    if raw_rate is None or str(raw_rate).strip() == "":
        errors["annual_interest_rate"] = "Annual interest rate is required."
    else:
        try:
            rate_val = float(raw_rate)
            if rate_val < 0:
                errors["annual_interest_rate"] = "Annual interest rate cannot be negative."
            elif rate_val > 100:
                errors["annual_interest_rate"] = "Annual interest rate cannot exceed 100%."
            else:
                cleaned["annual_interest_rate"] = round(rate_val, 2)
        except (ValueError, TypeError):
            errors["annual_interest_rate"] = "Annual interest rate must be a valid number."

    # min_monthly_income
    raw_inc = data.get("min_monthly_income")
    if raw_inc is None or str(raw_inc).strip() == "":
        errors["min_monthly_income"] = "Minimum monthly income is required."
    else:
        try:
            inc_val = float(raw_inc)
            if inc_val < 0:
                errors["min_monthly_income"] = "Minimum monthly income cannot be negative."
            else:
                cleaned["min_monthly_income"] = round(inc_val, 2)
        except (ValueError, TypeError):
            errors["min_monthly_income"] = "Minimum monthly income must be a valid number."

    # max_loan_to_income_ratio
    raw_ratio = data.get("max_loan_to_income_ratio")
    if raw_ratio is None or str(raw_ratio).strip() == "":
        errors["max_loan_to_income_ratio"] = "Maximum loan-to-income ratio is required."
    else:
        try:
            ratio_val = float(raw_ratio)
            if ratio_val <= 0:
                errors["max_loan_to_income_ratio"] = "Loan-to-income ratio must be greater than zero."
            elif ratio_val > 10.0:
                errors["max_loan_to_income_ratio"] = "Loan-to-income ratio cannot exceed 10.0."
            else:
                cleaned["max_loan_to_income_ratio"] = round(ratio_val, 2)
        except (ValueError, TypeError):
            errors["max_loan_to_income_ratio"] = "Maximum loan-to-income ratio must be a valid number."

    # active
    raw_active = data.get("active")
    if raw_active is not None:
        if isinstance(raw_active, bool):
            cleaned["active"] = raw_active
        else:
            cleaned["active"] = str(raw_active).strip().lower() in ("true", "1", "yes", "on")
    else:
        cleaned["active"] = True

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, cleaned_data=cleaned if is_valid else {})


def validate_customer_profile(data: dict[str, Any]) -> ValidationResult:
    """Validate customer profile fields (Phase 6)."""
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}

    # phone_number
    phone = data.get("phone_number")
    if phone is not None and str(phone).strip():
        p_val = str(phone).strip()
        if len(p_val) > 20:
            errors["phone_number"] = "Phone number cannot exceed 20 characters."
        else:
            cleaned["phone_number"] = p_val
    else:
        cleaned["phone_number"] = None

    # date_of_birth
    from datetime import datetime
    dob = data.get("date_of_birth")
    if dob is not None and str(dob).strip():
        try:
            dob_date = datetime.strptime(str(dob).strip(), "%Y-%m-%d").date()
            if dob_date >= datetime.now().date():
                errors["date_of_birth"] = "Date of birth must be in the past."
            else:
                cleaned["date_of_birth"] = dob_date
        except (ValueError, TypeError):
            errors["date_of_birth"] = "Date of birth must be in YYYY-MM-DD format."
    else:
        cleaned["date_of_birth"] = None

    # address, city, state
    for field_name, max_len in [("address", 255), ("city", 100), ("state", 100)]:
        val = data.get(field_name)
        if val is not None and str(val).strip():
            s_val = str(val).strip()
            if len(s_val) > max_len:
                errors[field_name] = f"{field_name.capitalize()} cannot exceed {max_len} characters."
            else:
                cleaned[field_name] = s_val
        else:
            cleaned[field_name] = None

    # employment_type
    allowed_emp_types = {"SALARIED", "SELF_EMPLOYED", "BUSINESS_OWNER", "OTHER"}
    emp_type = data.get("employment_type")
    if emp_type is not None and str(emp_type).strip():
        emp_type_val = str(emp_type).strip().upper()
        if emp_type_val not in allowed_emp_types:
            errors["employment_type"] = f"Employment type must be one of: {', '.join(sorted(allowed_emp_types))}."
        else:
            cleaned["employment_type"] = emp_type_val
    else:
        cleaned["employment_type"] = None

    # employer_name
    employer = data.get("employer_name")
    if employer is not None and str(employer).strip():
        e_val = str(employer).strip()
        if len(e_val) > 150:
            errors["employer_name"] = "Employer name cannot exceed 150 characters."
        else:
            cleaned["employer_name"] = e_val
    else:
        cleaned["employer_name"] = None

    # monthly_income
    income = data.get("monthly_income")
    if income is not None and str(income).strip() != "":
        try:
            inc_val = float(income)
            if inc_val < 0:
                errors["monthly_income"] = "Monthly income cannot be negative."
            else:
                cleaned["monthly_income"] = round(inc_val, 2)
        except (ValueError, TypeError):
            errors["monthly_income"] = "Monthly income must be a valid number."
    else:
        cleaned["monthly_income"] = None

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
