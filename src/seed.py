"""Database seeding module for LoanPulse.

Seeds the SQLite database using the verified synthetic CSV files in data/.
"""
import csv
import sys
from datetime import date
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import (
    db,
    User,
    LoanApplication,
    AssessmentRule,
    Assessment,
    Notification,
    RolePermission,
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def parse_date(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    return date.fromisoformat(value.strip())


def parse_float(value: str | None) -> float | None:
    if not value or not value.strip():
        return None
    return float(value.strip())


def parse_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in ("true", "1", "yes")


def seed_database(app=None, data_dir: Path | None = None) -> dict[str, int]:
    """Seed the database from CSV files.
    
    Can be run within an existing application context or by passing an app.
    Returns row counts loaded per table.
    """
    data_path = data_dir or DEFAULT_DATA_DIR

    def _seed():
        # Create all tables if they don't exist
        db.create_all()

        counts = {}

        # 1. Users
        users_file = data_path / "users.csv"
        user_rows = []
        with open(users_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                user = User(
                    user_id=int(r["user_id"]),
                    full_name=r["full_name"].strip(),
                    email=r["email"].strip(),
                    role=r["role"].strip(),
                    is_active=parse_bool(r["is_active"]),
                )
                # Set deterministic demo password for synthetic users
                user.set_password("demo123")
                user_rows.append(user)
        db.session.bulk_save_objects(user_rows)
        db.session.commit()
        counts["users"] = len(user_rows)

        # 2. Loan Applications
        apps_file = data_path / "loan_applications.csv"
        app_rows = []
        with open(apps_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                app_obj = LoanApplication(
                    application_id=r["application_id"].strip(),
                    customer_id=int(r["customer_id"]),
                    applicant_name=r["applicant_name"].strip(),
                    monthly_income=float(r["monthly_income"]),
                    requested_amount=float(r["requested_amount"]),
                    term_months=int(r["term_months"]),
                    status=r["status"].strip(),
                    approved_amount=parse_float(r.get("approved_amount")),
                    disbursement_status=r.get("disbursement_status", "NOT_APPLICABLE").strip(),
                    disbursement_date=parse_date(r.get("disbursement_date")),
                    created_at=parse_date(r["created_at"]),
                    updated_at=parse_date(r["updated_at"]),
                )
                app_rows.append(app_obj)
        db.session.bulk_save_objects(app_rows)
        db.session.commit()
        counts["loan_applications"] = len(app_rows)

        # 3. Assessment Rules
        rules_file = data_path / "assessment_rules.csv"
        rule_rows = []
        with open(rules_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rule_obj = AssessmentRule(
                    rule_id=int(r["rule_id"]),
                    rule_name=r["rule_name"].strip(),
                    min_monthly_income=float(r["min_monthly_income"]),
                    max_loan_to_income_ratio=float(r["max_loan_to_income_ratio"]),
                    min_term_months=int(r["min_term_months"]),
                    max_term_months=int(r["max_term_months"]),
                    result_if_pass=r["result_if_pass"].strip(),
                    active=parse_bool(r["active"]),
                )
                rule_rows.append(rule_obj)
        db.session.bulk_save_objects(rule_rows)
        db.session.commit()
        counts["assessment_rules"] = len(rule_rows)

        # 4. Assessments
        assessments_file = data_path / "assessments.csv"
        assessment_rows = []
        with open(assessments_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ass_obj = Assessment(
                    assessment_id=int(r["assessment_id"]),
                    application_id=r["application_id"].strip(),
                    rule_id=int(r["rule_id"]),
                    assessment_result=r["assessment_result"].strip(),
                    calculated_ratio=float(r["calculated_ratio"]),
                    assessed_at=parse_date(r["assessed_at"]),
                )
                assessment_rows.append(ass_obj)
        db.session.bulk_save_objects(assessment_rows)
        db.session.commit()
        counts["assessments"] = len(assessment_rows)

        # 5. Notifications
        notif_file = data_path / "notifications.csv"
        notif_rows = []
        with open(notif_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                notif_obj = Notification(
                    notification_id=int(r["notification_id"]),
                    application_id=r["application_id"].strip(),
                    recipient_user_id=int(r["recipient_user_id"]),
                    old_status=r.get("old_status").strip() if r.get("old_status") and r.get("old_status").strip() else None,
                    new_status=r["new_status"].strip(),
                    message=r["message"].strip(),
                    created_at=parse_date(r["created_at"]),
                    is_read=parse_bool(r["is_read"]),
                )
                notif_rows.append(notif_obj)
        db.session.bulk_save_objects(notif_rows)
        db.session.commit()
        counts["notifications"] = len(notif_rows)

        # 6. Role Permissions
        roles_file = data_path / "role_permissions.csv"
        perm_rows = []
        with open(roles_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                perm_obj = RolePermission(
                    role=r["role"].strip(),
                    resource=r["resource"].strip(),
                    can_view=parse_bool(r["can_view"]),
                )
                perm_rows.append(perm_obj)
        db.session.bulk_save_objects(perm_rows)
        db.session.commit()
        counts["role_permissions"] = len(perm_rows)

        return counts

    if app:
        with app.app_context():
            return _seed()
    else:
        return _seed()


if __name__ == "__main__":
    from src.app import create_app
    app = create_app()
    with app.app_context():
        counts = seed_database()
        print("Database seeded successfully:")
        for table, count in counts.items():
            print(f"  {table}: {count} records")
