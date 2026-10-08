"""Generate deterministic synthetic LoanPulse seed data.

All generated values are synthetic and intended for development/demo use only.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
N_USERS = 12
N_APPLICATIONS = 40
N_RULES = 3
N_ASSESSMENTS = 30
N_NOTIFICATIONS = 25
N_ROLE_PERMISSIONS = 6

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data"
FIXTURE_DIR = OUTPUT_DIR / "fixtures"

fake = Faker()
fake.seed_instance(SEED)
rng = np.random.default_rng(SEED)

STATUSES = ["DRAFT", "PENDING_REVIEW", "PENDING_MANAGER_REVIEW", "APPROVED", "REJECTED"]
STATUS_COUNTS = {
    "DRAFT": 5,
    "PENDING_REVIEW": 10,
    "PENDING_MANAGER_REVIEW": 8,
    "APPROVED": 8,
    "REJECTED": 9,
}


def money(value: float) -> float:
    return round(float(value), 2)


def make_users() -> pd.DataFrame:
    rows = []
    roles = ["CUSTOMER"] * 6 + ["LOAN_OFFICER"] * 4 + ["LOAN_MANAGER"] * 2
    for user_id, role in enumerate(roles, start=1):
        if role == "CUSTOMER":
            name = f"Test Borrower {user_id:02d}"
            email = f"borrower{user_id:02d}@example.test"
        elif role == "LOAN_OFFICER":
            officer_no = user_id - 6
            name = f"Test Officer {officer_no:02d}"
            email = f"officer{officer_no:02d}@example.test"
        else:
            manager_no = user_id - 10
            name = f"Test Manager {manager_no:02d}"
            email = f"manager{manager_no:02d}@example.test"
        # Faker is deliberately used as the synthetic name source for a hidden
        # seed value while the stored display names remain clearly synthetic.
        _ = fake.name()
        rows.append({
            "user_id": user_id,
            "full_name": name,
            "email": email,
            "role": role,
            "is_active": True,
        })
    return pd.DataFrame(rows)


def make_applications(users: pd.DataFrame) -> pd.DataFrame:
    statuses = [status for status, count in STATUS_COUNTS.items() for _ in range(count)]
    rng.shuffle(statuses)

    # Twelve months with modest synthetic peaks in Jan/Apr/Oct.
    months = np.arange(1, 13)
    weights = np.array([1.35 if m in (1, 4, 10) else 1.0 for m in months], dtype=float)
    weights /= weights.sum()

    income_ranges = [(25000, 60000, 0.60), (60001, 120000, 0.30), (120001, 300000, 0.10)]
    terms = [12, 18, 24, 36, 60]
    customer_ids = list(range(1, 7))
    rows = []

    start_date = pd.Timestamp("2025-11-01")
    for i in range(1, N_APPLICATIONS + 1):
        # Use the design's right-skewed income bands.
        band = rng.choice(len(income_ranges), p=[x[2] for x in income_ranges])
        low, high, _ = income_ranges[band]
        income = money(rng.uniform(low, high))
        amount = money(rng.uniform(50000, 400000))
        term = int(rng.choice(terms))

        # Deterministic edge/boundary records embedded in the clean demo data.
        if i == 3:  # Eligible example used by TC-05.
            income, amount, term = 60000.00, 200000.00, 24
        elif i in (4, 5):  # Identical assessment inputs for TC-07.
            income, amount, term = 50000.00, 150000.00, 24
        elif i == 6:  # Exact minimum income boundary.
            income, amount, term = 30000.00, 90000.00, 12
        elif i == 7:  # Exact maximum ratio boundary: 0.50.
            income, amount, term = 50000.00, 300000.00, 12
        elif i == 8:  # Extreme but valid numeric outlier for rule handling.
            income, amount, term = 300000.00, 5000000.00, 60

        month = int(rng.choice(months, p=weights))
        day = int(rng.integers(1, 25))
        created = start_date + pd.DateOffset(months=month - 1, days=day - 1)
        updated = created + pd.Timedelta(days=int(rng.integers(0, 20)))

        rows.append({
            "application_id": f"APP-{i:04d}",
            "customer_id": int(rng.choice(customer_ids)),
            "applicant_name": f"Test Borrower {int(rows[-1]['customer_id']) if rows else 1:02d}",
            "monthly_income": income,
            "requested_amount": amount,
            "term_months": term,
            "status": statuses[i - 1],
            "created_at": created.date().isoformat(),
            "updated_at": updated.date().isoformat(),
        })

    # Ensure named test records have their intended statuses, then rebalance
    # only the remaining records so the documented 40-row distribution is exact.
    df = pd.DataFrame(rows)
    fixed_statuses = {
        "APP-0002": "PENDING_REVIEW",
        "APP-0003": "PENDING_REVIEW",
        "APP-0010": "PENDING_MANAGER_REVIEW",
        "APP-0011": "PENDING_MANAGER_REVIEW",
        "APP-0015": "APPROVED",
        "APP-0016": "PENDING_REVIEW",
        "APP-0017": "PENDING_REVIEW",
    }
    for application_id, status in fixed_statuses.items():
        df.loc[df["application_id"] == application_id, "status"] = status

    fixed_ids = set(fixed_statuses)
    remaining = df.loc[~df["application_id"].isin(fixed_ids)].index.tolist()
    assigned = {status: 0 for status in STATUS_COUNTS}
    for status in fixed_statuses.values():
        assigned[status] += 1
    remaining_targets = {status: STATUS_COUNTS[status] - assigned[status] for status in STATUS_COUNTS}
    remaining_statuses = [status for status, count in remaining_targets.items() for _ in range(count)]
    rng.shuffle(remaining_statuses)
    for idx, status in zip(remaining, remaining_statuses):
        df.at[idx, "status"] = status

    # Derive disbursement fields only after the final lifecycle statuses are fixed.
    # All clean APPROVED demo records are represented as disbursed; the dedicated
    # edge fixture covers an approved-but-not-disbursed case.
    df["approved_amount"] = df["requested_amount"].where(df["status"] == "APPROVED", np.nan)
    df["disbursement_status"] = np.where(df["status"] == "APPROVED", "DISBURSED", "NOT_APPLICABLE")
    df["disbursement_date"] = pd.NaT
    approved_mask = df["status"] == "APPROVED"
    df.loc[approved_mask, "disbursement_date"] = pd.to_datetime(df.loc[approved_mask, "updated_at"]) + pd.to_timedelta(
        rng.integers(1, 10, size=int(approved_mask.sum())), unit="D"
    )
    df["disbursement_date"] = pd.to_datetime(df["disbursement_date"]).dt.date

    return df


def make_rules() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "rule_id": 1,
            "rule_name": "Standard Eligibility Rule",
            "min_monthly_income": 30000.00,
            "max_loan_to_income_ratio": 0.50,
            "min_term_months": 12,
            "max_term_months": 60,
            "result_if_pass": "ELIGIBLE",
            "active": True,
        },
        {
            "rule_id": 2,
            "rule_name": "Conservative Eligibility Rule",
            "min_monthly_income": 50000.00,
            "max_loan_to_income_ratio": 0.40,
            "min_term_months": 12,
            "max_term_months": 48,
            "result_if_pass": "ELIGIBLE",
            "active": True,
        },
        {
            "rule_id": 3,
            "rule_name": "Archived Demo Rule",
            "min_monthly_income": 75000.00,
            "max_loan_to_income_ratio": 0.30,
            "min_term_months": 18,
            "max_term_months": 36,
            "result_if_pass": "ELIGIBLE",
            "active": False,
        },
    ])


def assess(application: pd.Series, rule: pd.Series) -> tuple[str, float]:
    income = float(application["monthly_income"])
    amount = float(application["requested_amount"])
    term = int(application["term_months"])
    ratio = round(amount / (income * 12), 2) if income > 0 else np.nan
    eligible = (
        income >= float(rule["min_monthly_income"])
        and ratio <= float(rule["max_loan_to_income_ratio"])
        and float(rule["min_term_months"]) <= term <= float(rule["max_term_months"])
    )
    return ("ELIGIBLE" if eligible else "NOT_ELIGIBLE"), ratio


def make_assessments(applications: pd.DataFrame, rules: pd.DataFrame) -> pd.DataFrame:
    active_rule = rules.loc[rules["rule_id"] == 1].iloc[0]
    rows = []
    for assessment_id, (_, app) in enumerate(applications.iloc[:N_ASSESSMENTS].iterrows(), start=1):
        result, ratio = assess(app, active_rule)
        assessed_date = pd.Timestamp(app["updated_at"]) + pd.Timedelta(days=1)
        rows.append({
            "assessment_id": assessment_id,
            "application_id": app["application_id"],
            "rule_id": 1,
            "assessment_result": result,
            "calculated_ratio": ratio,
            "assessed_at": assessed_date.date().isoformat(),
        })
    return pd.DataFrame(rows)


def make_notifications(applications: pd.DataFrame) -> pd.DataFrame:
    rows = []
    # First row deliberately has a NULL old_status, as allowed by the design.
    for notification_id in range(1, N_NOTIFICATIONS + 1):
        app = applications.iloc[(notification_id - 1) % len(applications)]
        if notification_id == 1:
            old_status = None
            new_status = "PENDING_REVIEW"
        elif notification_id == 15:  # No-op fixture for TC-15 is kept in the data.
            old_status = "PENDING_REVIEW"
            new_status = "PENDING_REVIEW"
        else:
            old_status = "PENDING_REVIEW"
            new_status = str(app["status"])
        rows.append({
            "notification_id": notification_id,
            "application_id": app["application_id"],
            "recipient_user_id": int(app["customer_id"]),
            "old_status": old_status,
            "new_status": new_status,
            "message": f"Loan application {app['application_id']} status changed to {new_status}.",
            "created_at": app["updated_at"],
            "is_read": notification_id % 3 == 0,
        })
    return pd.DataFrame(rows)


def make_role_permissions() -> pd.DataFrame:
    return pd.DataFrame([
        ["CUSTOMER", "OWN_APPLICATION", True],
        ["CUSTOMER", "STAFF_REPORT", False],
        ["LOAN_OFFICER", "APPLICATION", True],
        ["LOAN_OFFICER", "ASSESSMENT", True],
        ["LOAN_MANAGER", "PENDING_DECISION_REPORT", True],
        ["LOAN_MANAGER", "APPLICATION", True],
    ], columns=["role", "resource", "can_view"])


def make_edge_fixtures() -> dict[str, pd.DataFrame]:
    return {
        "application_edge_cases": pd.DataFrame([
            ["APP-EDGE-NULL-INCOME", "missing_income", 1, "Test Borrower 01", None, 200000, 24, "PENDING_REVIEW", None, "NOT_APPLICABLE", None],
            ["APP-EDGE-NEG-INCOME", "negative_income", 1, "Test Borrower 01", -5000, 200000, 24, "PENDING_REVIEW", None, "NOT_APPLICABLE", None],
            ["APP-EDGE-NULL-AMOUNT", "missing_loan_amount", 2, "Test Borrower 02", 50000, None, 24, "DRAFT", None, "NOT_APPLICABLE", None],
            ["APP-EDGE-TEXT-AMOUNT", "text_loan_amount", 2, "Test Borrower 02", 50000, "abc", 24, "DRAFT", None, "NOT_APPLICABLE", None],
            ["APP-EDGE-NO-DISBURSEMENT", "approved_without_disbursement", 3, "Test Borrower 03", 60000, 200000, 24, "APPROVED", 200000, "NOT_DISBURSED", None],
        ], columns=["application_id", "case_type", "customer_id", "applicant_name", "monthly_income", "requested_amount", "term_months", "status", "approved_amount", "disbursement_status", "disbursement_date"]),
        "duplicate_identifier_attempt": pd.DataFrame([
            ["duplicate_primary_key", "APP-0001", "Attempted duplicate application ID", "Insert should be rejected by PK rule"]
        ], columns=["case_type", "application_id", "description", "expected"]),
        "unauthorized_access": pd.DataFrame([
            ["USER-CUST-01", "CUSTOMER", "STAFF_REPORT", "DENY"]
        ], columns=["user_id_label", "role", "resource", "expected_access"]),
    }


def validate(datasets: dict[str, pd.DataFrame]) -> bool:
    errors: list[str] = []

    pk_map = {
        "users": ["user_id"],
        "loan_applications": ["application_id"],
        "assessment_rules": ["rule_id"],
        "assessments": ["assessment_id"],
        "notifications": ["notification_id"],
        "role_permissions": ["role", "resource"],
    }
    for name, cols in pk_map.items():
        df = datasets[name]
        if len(df) != df[cols].drop_duplicates().shape[0]:
            errors.append(f"{name}: primary key is not unique")
        if df[cols].isna().any().any():
            errors.append(f"{name}: primary key contains null")

    fk_checks = [
        ("loan_applications", "customer_id", "users", "user_id"),
        ("assessments", "application_id", "loan_applications", "application_id"),
        ("assessments", "rule_id", "assessment_rules", "rule_id"),
        ("notifications", "application_id", "loan_applications", "application_id"),
        ("notifications", "recipient_user_id", "users", "user_id"),
    ]
    for child, child_col, parent, parent_col in fk_checks:
        child_values = set(datasets[child][child_col].dropna())
        parent_values = set(datasets[parent][parent_col].dropna())
        invalid = child_values - parent_values
        if invalid:
            errors.append(f"{child}.{child_col}: invalid foreign keys {sorted(invalid)[:5]}")

    expected_null_rates = {
        "users": {"user_id": 0.0, "full_name": 0.0, "email": 0.0, "role": 0.0, "is_active": 0.0},
        "loan_applications": {
            c: (float((datasets["loan_applications"]["status"] != "APPROVED").mean()) if c == "approved_amount" else
                float((datasets["loan_applications"]["status"] != "APPROVED").mean()) if c == "disbursement_date" else 0.0)
            for c in datasets["loan_applications"].columns
        },
        "assessment_rules": {c: 0.0 for c in datasets["assessment_rules"].columns},
        "assessments": {c: 0.0 for c in datasets["assessments"].columns},
        "notifications": {c: (1 / N_NOTIFICATIONS) if c == "old_status" else 0.0 for c in datasets["notifications"].columns},
        "role_permissions": {c: 0.0 for c in datasets["role_permissions"].columns},
    }
    for name, columns in expected_null_rates.items():
        for col, expected in columns.items():
            actual = float(datasets[name][col].isna().mean())
            if not np.isclose(actual, expected, atol=1e-12):
                errors.append(f"{name}.{col}: null rate {actual:.4f}, expected {expected:.4f}")

    apps = datasets["loan_applications"]
    approved = apps[apps["status"] == "APPROVED"]
    non_approved = apps[apps["status"] != "APPROVED"]
    if approved["approved_amount"].isna().any() or approved["disbursement_status"].isna().any() or approved["disbursement_date"].isna().any():
        errors.append("loan_applications: approved loans must have approved_amount, disbursement_status, and disbursement_date")
    if non_approved["approved_amount"].notna().any() or non_approved["disbursement_date"].notna().any():
        errors.append("loan_applications: non-approved loans must not have approved_amount or disbursement_date")

    print("\nLoanPulse dataset validation summary")
    print("=" * 44)
    for name, df in datasets.items():
        print(f"{name:22s} rows={len(df):>3}  duplicate_rows={df.duplicated().sum():>2}")
    print(f"notifications.old_status null rate: {datasets['notifications']['old_status'].isna().mean():.4f}")
    print(f"applications status counts: {datasets['loan_applications']['status'].value_counts().to_dict()}")
    print(f"assessments eligible/not: {datasets['assessments']['assessment_result'].value_counts().to_dict()}")

    if errors:
        print("\nVALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return False

    print("\nVALIDATION PASSED: primary keys, foreign keys, and intended null rates are valid.")
    return True


def write_csvs(datasets: dict[str, pd.DataFrame]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in datasets.items():
        df.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
    for name, df in make_edge_fixtures().items():
        df.to_csv(FIXTURE_DIR / f"{name}.csv", index=False)


def main() -> int:
    users = make_users()
    applications = make_applications(users)
    rules = make_rules()
    assessments = make_assessments(applications, rules)
    notifications = make_notifications(applications)
    role_permissions = make_role_permissions()

    datasets = {
        "users": users,
        "loan_applications": applications,
        "assessment_rules": rules,
        "assessments": assessments,
        "notifications": notifications,
        "role_permissions": role_permissions,
    }
    write_csvs(datasets)
    return 0 if validate(datasets) else 1


if __name__ == "__main__":
    sys.exit(main())
