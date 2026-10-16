"""SQLAlchemy models for LoanPulse."""
from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Application user model."""
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    role = db.Column(db.String(30), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # password_hash is added exclusively as an implementation requirement for Flask-Login
    password_hash = db.Column(db.String(255), nullable=True)
    # Single active session tracking token (invalidates older sessions across windows/devices on new login)
    active_session_token = db.Column(db.String(64), nullable=True)

    # Customer profile fields (Phase 6)
    phone_number = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    employment_type = db.Column(db.String(50), nullable=True)
    employer_name = db.Column(db.String(150), nullable=True)
    monthly_income = db.Column(db.Float, nullable=True)

    # KYC verification fields (Phase 6)
    kyc_status = db.Column(db.String(30), default="NOT_STARTED", nullable=False)
    kyc_rejection_reason = db.Column(db.String(255), nullable=True)
    kyc_submitted_at = db.Column(db.Date, nullable=True)
    kyc_reviewed_at = db.Column(db.Date, nullable=True)

    loan_applications = db.relationship("LoanApplication", backref="customer", lazy=True)
    notifications = db.relationship("Notification", backref="recipient", lazy=True)
    documents = db.relationship("CustomerDocument", backref="customer", lazy=True, cascade="all, delete-orphan")

    @property
    def profile_completion_percentage(self) -> int:
        """Calculate real profile completion percentage based on core profile fields."""
        fields = [
            self.full_name,
            self.email,
            self.phone_number,
            self.date_of_birth,
            self.address,
            self.city,
            self.state,
            self.employment_type,
            self.monthly_income,
        ]
        completed = sum(1 for f in fields if f is not None and str(f).strip() != "")
        return int(round((completed / len(fields)) * 100))

    def get_id(self):
        """Return the unique user ID as a string for Flask-Login."""
        return str(self.user_id)

    def set_password(self, password: str):
        """Store hashed password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.user_id}: {self.email} ({self.role})>"


class CustomerDocument(db.Model):
    """Customer uploaded verification document (Phase 6)."""
    __tablename__ = "customer_documents"

    document_id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # IDENTITY_PROOF, ADDRESS_PROOF, INCOME_PROOF
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    verification_status = db.Column(db.String(30), default="PENDING", nullable=False)  # PENDING, VERIFIED, REJECTED
    rejection_reason = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.Date, nullable=False, default=date.today)
    reviewed_at = db.Column(db.Date, nullable=True)

    def __repr__(self):
        return f"<CustomerDocument {self.document_id}: {self.document_type} ({self.verification_status})>"


class LoanProduct(db.Model):
    """Configurable loan product catalog model (Phase 7)."""
    __tablename__ = "loan_products"

    product_id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    product_code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    min_amount = db.Column(db.Float, nullable=False)
    max_amount = db.Column(db.Float, nullable=False)
    min_term_months = db.Column(db.Integer, nullable=False)
    max_term_months = db.Column(db.Integer, nullable=False)
    annual_interest_rate = db.Column(db.Float, nullable=False)
    min_monthly_income = db.Column(db.Float, nullable=False)
    max_loan_to_income_ratio = db.Column(db.Float, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.Date, nullable=False, default=date.today)
    updated_at = db.Column(db.Date, nullable=False, default=date.today)

    applications = db.relationship("LoanApplication", backref="loan_product", lazy=True)

    @property
    def is_active(self) -> bool:
        return bool(self.active)

    @is_active.setter
    def is_active(self, val: bool):
        self.active = bool(val)

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_code": self.product_code,
            "description": self.description or "",
            "min_amount": float(self.min_amount),
            "max_amount": float(self.max_amount),
            "min_term_months": int(self.min_term_months),
            "max_term_months": int(self.max_term_months),
            "annual_interest_rate": float(self.annual_interest_rate),
            "min_monthly_income": float(self.min_monthly_income),
            "max_loan_to_income_ratio": float(self.max_loan_to_income_ratio),
            "active": bool(self.active),
        }

    def __repr__(self):
        return f"<LoanProduct {self.product_id}: {self.product_name} ({self.product_code}, active={self.active})>"


class LoanApplication(db.Model):
    """Loan application model."""
    __tablename__ = "loan_applications"

    application_id = db.Column(db.String(20), primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    applicant_name = db.Column(db.String(100), nullable=False)
    monthly_income = db.Column(db.Float, nullable=False)
    requested_amount = db.Column(db.Float, nullable=False)
    term_months = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="DRAFT", nullable=False)
    approved_amount = db.Column(db.Float, nullable=True)
    disbursement_status = db.Column(db.String(30), default="NOT_APPLICABLE", nullable=False)
    disbursement_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.Date, nullable=False, default=date.today)
    updated_at = db.Column(db.Date, nullable=False, default=date.today)

    # Enhanced loan application fields (Phase 6)
    loan_purpose = db.Column(db.String(50), default="PERSONAL", nullable=False)
    loan_purpose_other = db.Column(db.String(255), nullable=True)
    employment_type = db.Column(db.String(50), nullable=True)
    employer_name = db.Column(db.String(150), nullable=True)
    existing_obligations = db.Column(db.Float, default=0.0, nullable=False)
    preferred_repayment_date = db.Column(db.Integer, nullable=True)

    # Configurable loan products relation & financial snapshots (Phase 7)
    product_id = db.Column(db.Integer, db.ForeignKey("loan_products.product_id"), nullable=True)
    applied_interest_rate = db.Column(db.Float, nullable=True)
    estimated_monthly_emi = db.Column(db.Float, nullable=True)

    # Workflow notes and decision reasons (Phase 8)
    review_notes = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)

    assessments = db.relationship("Assessment", backref="application", lazy=True)
    notifications = db.relationship("Notification", backref="application", lazy=True)
    audit_logs = db.relationship(
        "ApplicationAuditLog",
        backref="application",
        lazy=True,
        order_by="ApplicationAuditLog.created_at.desc()",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<LoanApplication {self.application_id}: {self.status}>"


class ApplicationAuditLog(db.Model):
    """Immutable audit trail for all significant loan application events (Phase 8)."""
    __tablename__ = "application_audit_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(20), db.ForeignKey("loan_applications.application_id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    actor_name = db.Column(db.String(100), nullable=False)
    actor_role = db.Column(db.String(30), nullable=False)
    from_status = db.Column(db.String(30), nullable=True)
    to_status = db.Column(db.String(30), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    actor = db.relationship("User", foreign_keys=[actor_id], lazy=True)

    def to_dict(self) -> dict:
        return {
            "log_id": self.log_id,
            "application_id": self.application_id,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "actor_role": self.actor_role,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "action": self.action,
            "notes": self.notes or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<ApplicationAuditLog {self.log_id}: {self.application_id} {self.action} by {self.actor_name}>"


class AssessmentRule(db.Model):
    """Predefined assessment rule configuration model."""
    __tablename__ = "assessment_rules"

    rule_id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(100), nullable=False)
    min_monthly_income = db.Column(db.Float, nullable=False)
    max_loan_to_income_ratio = db.Column(db.Float, nullable=False)
    min_term_months = db.Column(db.Integer, nullable=False)
    max_term_months = db.Column(db.Integer, nullable=False)
    result_if_pass = db.Column(db.String(30), default="ELIGIBLE", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    assessments = db.relationship("Assessment", backref="rule", lazy=True)

    def __repr__(self):
        return f"<AssessmentRule {self.rule_id}: {self.rule_name} (active={self.active})>"


class Assessment(db.Model):
    """Loan assessment result record model."""
    __tablename__ = "assessments"

    assessment_id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(20), db.ForeignKey("loan_applications.application_id"), nullable=False)
    rule_id = db.Column(db.Integer, db.ForeignKey("assessment_rules.rule_id"), nullable=False)
    assessment_result = db.Column(db.String(30), nullable=False)
    calculated_ratio = db.Column(db.Float, nullable=False)
    assessed_at = db.Column(db.Date, nullable=False, default=date.today)

    # Advanced rule engine breakdown and financial metrics (Phase 7)
    rules_breakdown_json = db.Column(db.Text, nullable=True)
    failure_reasons_json = db.Column(db.Text, nullable=True)
    estimated_emi = db.Column(db.Float, nullable=True)
    affordability_ratio = db.Column(db.Float, nullable=True)

    @property
    def rules_breakdown(self) -> list[dict]:
        import json
        if self.rules_breakdown_json:
            try:
                return json.loads(self.rules_breakdown_json)
            except Exception:
                return []
        return []

    @property
    def failure_reasons(self) -> list[str]:
        import json
        if self.failure_reasons_json:
            try:
                return json.loads(self.failure_reasons_json)
            except Exception:
                return []
        return []

    def __repr__(self):
        return f"<Assessment {self.assessment_id}: {self.application_id} -> {self.assessment_result}>"


class Notification(db.Model):
    """Notification record model."""
    __tablename__ = "notifications"

    notification_id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(20), db.ForeignKey("loan_applications.application_id"), nullable=False)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.Date, nullable=False, default=date.today)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Notification {self.notification_id}: {self.recipient_user_id} ({self.new_status})>"


class RolePermission(db.Model):
    """Role-resource permission mapping model."""
    __tablename__ = "role_permissions"

    role = db.Column(db.String(30), primary_key=True)
    resource = db.Column(db.String(50), primary_key=True)
    can_view = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<RolePermission {self.role} -> {self.resource}: {self.can_view}>"


def sync_database_sequences(bind=None):
    """Synchronize PostgreSQL primary key sequences with the maximum existing ID in each table.

    Prevents duplicate key violations (psycopg.errors.UniqueViolation) when records
    have been imported or seeded with explicit primary key IDs.
    """
    from sqlalchemy import text
    engine = bind or db.engine
    if not engine or engine.dialect.name != "postgresql":
        return

    tables_and_pks = [
        ("notifications", "notification_id"),
        ("users", "user_id"),
        ("loan_products", "product_id"),
        ("assessment_rules", "rule_id"),
        ("assessments", "assessment_id"),
        ("application_audit_logs", "log_id"),
        ("customer_documents", "document_id"),
    ]

    with engine.connect() as conn:
        for table, pk in tables_and_pks:
            try:
                res = conn.execute(text(f"SELECT MAX({pk}) FROM {table}")).scalar()
                max_id = int(res) if res is not None else 0
                seq_sql = f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', '{pk}'),
                        GREATEST(:max_id, 1),
                        :is_called
                    )
                """
                conn.execute(text(seq_sql), {"max_id": max_id, "is_called": max_id > 0})
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                    res = conn.execute(text(f"SELECT MAX({pk}) FROM {table}")).scalar()
                    max_id = int(res) if res is not None else 0
                    fallback_sql = f"SELECT setval('{table}_{pk}_seq', GREATEST(:max_id, 1), :is_called)"
                    conn.execute(text(fallback_sql), {"max_id": max_id, "is_called": max_id > 0})
                    conn.commit()
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
