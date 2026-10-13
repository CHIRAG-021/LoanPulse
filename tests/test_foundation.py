"""Foundation tests for Phase 1: environment, config, models, seeding, and auth."""
from datetime import date
from src.app import create_app
from src.config import TestingConfig, DevelopmentConfig
from src.models import (
    db,
    User,
    LoanApplication,
    AssessmentRule,
    Assessment,
    Notification,
    RolePermission,
)


def test_config():
    """Verify configuration behavior."""
    dev_cfg = DevelopmentConfig()
    test_cfg = TestingConfig()
    assert test_cfg.TESTING is True
    assert test_cfg.SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:"
    assert dev_cfg.TESTING is False


def test_app_factory_and_health(client):
    """Verify application factory and health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["app"] == "LoanPulse"


def test_database_table_creation(app):
    """Verify that all 6 relational tables are registered in metadata."""
    expected_tables = {
        "users",
        "loan_applications",
        "assessment_rules",
        "assessments",
        "notifications",
        "role_permissions",
    }
    with app.app_context():
        table_names = set(db.metadata.tables.keys())
        assert expected_tables.issubset(table_names)


def test_user_model_and_auth(db_session, app):
    """Verify User model, password hashing, and UserMixin functionality."""
    user = User(
        user_id=99,
        full_name="Test Borrower Foundation",
        email="foundation@example.test",
        role="CUSTOMER",
        is_active=True,
    )
    user.set_password("securepassword")
    db_session.add(user)
    db_session.commit()

    # Verify attributes
    assert user.get_id() == "99"
    assert user.is_active is True
    assert user.check_password("securepassword") is True
    assert user.check_password("wrongpassword") is False
    assert user.password_hash != "securepassword"  # Must not store plaintext

    # Verify user loader
    from src.app import login_manager
    loaded = login_manager._user_callback("99")
    assert loaded is not None
    assert loaded.email == "foundation@example.test"


def test_seeding_target_counts(seeded_db):
    """Verify seed_database loads exact target row counts from CSV files."""
    users_count = seeded_db.query(User).count()
    apps_count = seeded_db.query(LoanApplication).count()
    rules_count = seeded_db.query(AssessmentRule).count()
    assessments_count = seeded_db.query(Assessment).count()
    notifs_count = seeded_db.query(Notification).count()
    perms_count = seeded_db.query(RolePermission).count()

    assert users_count == 12
    assert apps_count == 40
    assert rules_count == 3
    assert assessments_count == 30
    assert notifs_count == 25
    assert perms_count == 6


def test_loan_application_disbursement_schema(seeded_db):
    """Verify disbursement fields and values match the documented schema."""
    apps = seeded_db.query(LoanApplication).all()
    assert len(apps) == 40

    valid_disbursement_statuses = {"NOT_APPLICABLE", "NOT_DISBURSED", "DISBURSED"}

    for app in apps:
        assert hasattr(app, "approved_amount")
        assert hasattr(app, "disbursement_status")
        assert hasattr(app, "disbursement_date")
        assert app.disbursement_status in valid_disbursement_statuses

        if app.status == "APPROVED":
            assert app.approved_amount is not None
            assert app.approved_amount > 0
            assert app.disbursement_status == "DISBURSED"
            assert isinstance(app.disbursement_date, date)
        else:
            assert app.approved_amount is None
            assert app.disbursement_status == "NOT_APPLICABLE"
            assert app.disbursement_date is None


def test_seeded_user_roles(seeded_db):
    """Verify seeded user roles match the three permitted roles."""
    users = seeded_db.query(User).all()
    roles = {u.role for u in users}
    assert roles == {"CUSTOMER", "LOAN_OFFICER", "LOAN_MANAGER"}

    # All seeded demo users must have demo password working
    for user in users:
        assert user.check_password("demo123") is True


def test_role_permissions_composite_key(seeded_db):
    """Verify RolePermission composite primary key functionality."""
    perm = seeded_db.get(RolePermission, ("CUSTOMER", "OWN_APPLICATION"))
    assert perm is not None
    assert perm.can_view is True

    denied_perm = seeded_db.get(RolePermission, ("CUSTOMER", "STAFF_REPORT"))
    assert denied_perm is not None
    assert denied_perm.can_view is False


def test_cli_init_db(runner):
    """Verify flask init-db CLI command creates and seeds database."""
    result = runner.invoke(args=["init-db"])
    assert result.exit_code == 0
    assert "Database initialized and seeded successfully:" in result.output
    assert "users: 12 records" in result.output
    assert "loan_applications: 40 records" in result.output
