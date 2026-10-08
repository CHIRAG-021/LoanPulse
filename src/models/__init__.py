"""SQLAlchemy models for LoanPulse."""
from datetime import date
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

    loan_applications = db.relationship("LoanApplication", backref="customer", lazy=True)
    notifications = db.relationship("Notification", backref="recipient", lazy=True)

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

    assessments = db.relationship("Assessment", backref="application", lazy=True)
    notifications = db.relationship("Notification", backref="application", lazy=True)

    def __repr__(self):
        return f"<LoanApplication {self.application_id}: {self.status}>"


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
