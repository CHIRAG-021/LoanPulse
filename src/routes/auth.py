"""Authentication and session routes for LoanPulse."""
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required

from src.models import db, User

auth_bp = Blueprint("auth", __name__)


def role_required(*roles):
    """Decorator to enforce role-based access control."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Authentication required"}), 401
                return redirect(url_for("auth.login", next=request.url))
            if current_user.role not in roles:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Forbidden: insufficient role permissions"}), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route("/")
def index():
    """Root redirect based on user authentication and role."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.role == "CUSTOMER":
        return redirect(url_for("customer.dashboard"))
    elif current_user.role == "LOAN_OFFICER":
        return redirect(url_for("officer.queue"))
    elif current_user.role == "LOAN_MANAGER":
        return redirect(url_for("manager.queue"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page and submission handler."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        email = request.form.get("email") or (request.get_json(silent=True) or {}).get("email")
        password = request.form.get("password") or (request.get_json(silent=True) or {}).get("password")

        if not email or not password:
            error_msg = "Email and password are required."
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error_msg}), 400
            flash(error_msg, "danger")
            return render_template("auth/login.html"), 400

        user = User.query.filter_by(email=email.strip().lower()).first()

        if user and user.is_active and user.check_password(password):
            login_user(user)
            next_url = request.args.get("next")
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({
                    "message": "Login successful",
                    "user_id": user.user_id,
                    "email": user.email,
                    "role": user.role,
                }), 200
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("auth.index"))
        else:
            error_msg = "Invalid email or password."
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error_msg}), 401
            flash(error_msg, "danger")
            return render_template("auth/login.html"), 401

    # Demo quick-login helpers for demonstration
    try:
        demo_users = User.query.filter(User.user_id.in_([1, 7, 11])).all()
    except Exception:
        demo_users = []
    return render_template("auth/login.html", demo_users=demo_users)


@auth_bp.route("/logout")
@login_required
def logout():
    """Logout current user and redirect to login."""
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
