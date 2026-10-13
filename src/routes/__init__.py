"""Routes package for LoanPulse."""
from src.routes.auth import auth_bp
from src.routes.customer import customer_bp
from src.routes.officer import officer_bp
from src.routes.manager import manager_bp
from src.routes.notifications import notifications_bp

__all__ = ["auth_bp", "customer_bp", "officer_bp", "manager_bp", "notifications_bp"]
