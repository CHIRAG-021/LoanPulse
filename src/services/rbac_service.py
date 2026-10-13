"""Role-based access control (RBAC) service for LoanPulse (US-09, BR-09, TR-09).

Uses the database-backed role_permissions table to verify permissions.
"""
from functools import wraps
from flask import request, jsonify, abort, redirect, url_for
from flask_login import current_user

from src.models import db, RolePermission


def has_permission(role: str, resource: str, session=None) -> bool:
    """Check if a role has view permission for a given resource."""
    s = session or db.session
    perm = s.query(RolePermission).filter_by(role=role, resource=resource).first()
    if perm is not None:
        return bool(perm.can_view)
    return False


def permission_required(resource: str):
    """Decorator to enforce RBAC based on the role_permissions database table."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Authentication required"}), 401
                return redirect(url_for("auth.login", next=request.url))

            if not has_permission(current_user.role, resource):
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": f"Forbidden: role {current_user.role} lacks permission for {resource}"}), 403
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator
