"""Authentication and session routes for LoanPulse."""
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required

from src.models import db, User

auth_bp = Blueprint("auth", __name__)


import secrets

def role_required(*roles):
    """Decorator to enforce role-based access control and active session validity."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            wid = request.args.get("wid") or request.headers.get("X-Window-ID")

            # 1. Window-scoped session validation
            if wid:
                window_sessions = session.get("window_sessions", {})
                if wid not in window_sessions:
                    if request.is_json or request.headers.get("Accept") == "application/json":
                        return jsonify({"error": "Authentication required for this window"}), 401
                    flash("Please sign in to access this window.", "info")
                    return redirect(url_for("auth.login", wid=wid, next=request.url))

                w_info = window_sessions[wid]
                u = db.session.get(User, int(w_info["user_id"]))
                if not u or u.active_session_token != w_info.get("session_token"):
                    # Session was invalidated elsewhere (e.g. user logged in from another window or device)
                    window_sessions.pop(wid, None)
                    session["window_sessions"] = window_sessions
                    session.modified = True
                    if request.is_json or request.headers.get("Accept") == "application/json":
                        return jsonify({"error": "Session invalidated: logged in from another window or device"}), 401
                    flash("Your session has expired or you have logged in from another window or device. Please sign in again.", "warning")
                    login_endpoint = "auth.login_user_view" if w_info.get("role") == "CUSTOMER" else "auth.login_admin_view"
                    return redirect(url_for(login_endpoint, wid=wid))
            elif session.get("window_sessions"):
                # Window sessions exist, but no wid was provided: prevent new unauthenticated windows from inheriting session
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Authentication required for this window"}), 401
                flash("Please sign in to access your account in this window.", "info")
                return redirect(url_for("auth.login", next=request.url))

            # 2. General authentication check
            if not current_user.is_authenticated:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Authentication required"}), 401
                return redirect(url_for("auth.login", next=request.url))

            # 3. Single active session token validation against database
            session_token = None
            if wid:
                session_token = session.get("window_sessions", {}).get(wid, {}).get("session_token")
            elif request.args.get("demo_role") or request.headers.get("X-Demo-Role"):
                r_key = request.args.get("demo_role") or request.headers.get("X-Demo-Role")
                session_token = session.get("session_tokens", {}).get(r_key)
            if not session_token:
                session_token = session.get("active_session_token")

            if session_token and current_user.active_session_token != session_token:
                logout_user()
                session.clear()
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Session invalidated: logged in from another window or device"}), 401
                flash("Your session has expired or you have logged in from another window or device. Please sign in again.", "warning")
                login_endpoint = "auth.login_user_view" if current_user.role == "CUSTOMER" else "auth.login_admin_view"
                return redirect(url_for(login_endpoint))

            # 4. Role-based authorization
            if current_user.role not in roles:
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": "Forbidden: insufficient role permissions"}), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route("/")
def index():
    """Root landing page - always accessible and unauthenticated by default."""
    return render_template("landing.html")


@auth_bp.route("/landing")
def landing():
    """Public landing page for LoanPulse."""
    return render_template("landing.html")


@auth_bp.route("/select-role")
@auth_bp.route("/role-select")
@auth_bp.route("/get-started")
def select_role():
    """Interactive role selection screen."""
    return render_template("auth/role_select.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Public customer registration route."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))

    demo_role = request.args.get("demo_role")

    if request.method == "POST":
        raw_data = request.get_json(silent=True) or request.form.to_dict()
        full_name = (raw_data.get("full_name") or "").strip()
        email = (raw_data.get("email") or "").strip().lower()
        password = raw_data.get("password") or ""
        confirm_password = raw_data.get("confirm_password") or ""

        errors = {}

        if not full_name:
            errors["full_name"] = "Full name is required."

        if not email:
            errors["email"] = "Email address is required."
        elif "@" not in email or "." not in email.split("@")[-1] or len(email) < 5:
            errors["email"] = "A valid email address is required."
        else:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                errors["email"] = "An account with this email address already exists."

        if not password:
            errors["password"] = "Password is required."
        elif len(password) < 6:
            errors["password"] = "Password must be at least 6 characters."

        if not confirm_password:
            errors["confirm_password"] = "Please confirm your password."
        elif password and confirm_password != password:
            errors["confirm_password"] = "Passwords do not match."

        if errors:
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": "Validation failed", "errors": errors}), 400
            flash("Please correct the errors below.", "danger")
            return render_template("auth/signup.html", errors=errors, form_data=raw_data, demo_role=demo_role), 400

        # Security requirement: Public signup must ONLY create CUSTOMER accounts.
        # Ignore any role supplied in the request body.
        new_user = User(
            full_name=full_name,
            email=email,
            role="CUSTOMER",
            is_active=True,
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({
                "message": "Account created successfully. Please sign in to continue.",
                "user_id": new_user.user_id,
                "email": new_user.email,
                "role": new_user.role,
            }), 201

        flash("Account created successfully. Please sign in to continue.", "success")
        return redirect(url_for("auth.login_user_view", demo_role=demo_role))

    return render_template("auth/signup.html", errors={}, form_data={}, demo_role=demo_role)


def handle_login(portal_type: str | None = None):
    """Core login authentication handler supporting portal scoping and role validation."""
    demo_role = request.args.get("demo_role")
    wid = request.args.get("wid") or request.form.get("wid") or request.headers.get("X-Window-ID")

    if request.method == "POST":
        email = request.form.get("email") or (request.get_json(silent=True) or {}).get("email")
        password = request.form.get("password") or (request.get_json(silent=True) or {}).get("password")

        if not email or not password:
            error_msg = "Email and password are required."
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error_msg}), 400
            flash(error_msg, "danger")
            template = "auth/login_admin.html" if portal_type == "admin" else ("auth/login_user.html" if portal_type == "user" else "auth/login_select.html")
            return render_template(template, demo_role=demo_role, wid=wid, portal_type=portal_type), 400

        user = User.query.filter_by(email=email.strip().lower()).first()

        if user and user.is_active and user.check_password(password):
            # Enforce wrong-login-type credential checks without disclosing account role (LP-VULN-06)
            if (portal_type == "user" and user.role != "CUSTOMER") or (portal_type == "admin" and user.role == "CUSTOMER"):
                error_msg = "Invalid email or password."
                if request.is_json or request.headers.get("Accept") == "application/json":
                    return jsonify({"error": error_msg}), 401
                flash(error_msg, "danger")
                template = "auth/login_admin.html" if portal_type == "admin" else "auth/login_user.html"
                return render_template(template, demo_role=demo_role, wid=wid, portal_type=portal_type), 401

            # 1. Single active login session per account:
            # Generate a new session token for this user account.
            # This immediately invalidates any previously active session for this account across all devices/windows.
            new_token = secrets.token_hex(32)
            user.active_session_token = new_token
            db.session.commit()

            login_user(user)

            # Store active session token and user ID
            session["active_session_token"] = new_token
            session["_user_id"] = str(user.user_id)

            if wid:
                window_sessions = dict(session.get("window_sessions", {}))
                window_sessions[wid] = {
                    "user_id": user.user_id,
                    "session_token": new_token,
                    "role": user.role,
                }
                session["window_sessions"] = window_sessions

            # Multi-tab isolated demo session mapping
            role_key = demo_role if demo_role else user.role
            demo_sessions = dict(session.get("demo_sessions", {}))
            demo_sessions[role_key] = user.user_id
            session["demo_sessions"] = demo_sessions

            session_tokens = dict(session.get("session_tokens", {}))
            session_tokens[role_key] = new_token
            if wid:
                session_tokens[wid] = new_token
            session["session_tokens"] = session_tokens
            session.modified = True

            next_url = request.args.get("next")
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({
                    "message": "Login successful",
                    "user_id": user.user_id,
                    "email": user.email,
                    "role": user.role,
                    "wid": wid,
                }), 200

            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                # Preserve active parameters on next_url redirect
                if wid and "wid=" not in next_url:
                    sep = "&" if "?" in next_url else "?"
                    next_url = f"{next_url}{sep}wid={wid}"
                if demo_role and "demo_role=" not in next_url:
                    sep = "&" if "?" in next_url else "?"
                    next_url = f"{next_url}{sep}demo_role={demo_role}"
                return redirect(next_url)

            # Redirect directly to authoritative role dashboard
            redirect_args = {}
            if wid:
                redirect_args["wid"] = wid
            if demo_role:
                redirect_args["demo_role"] = demo_role
            elif not wid:
                redirect_args["demo_role"] = user.role

            if user.role == "CUSTOMER":
                return redirect(url_for("customer.dashboard", **redirect_args))
            elif user.role == "LOAN_OFFICER":
                return redirect(url_for("officer.queue", **redirect_args))
            elif user.role == "LOAN_MANAGER":
                return redirect(url_for("manager.queue", **redirect_args))
            return redirect(url_for("auth.index", **redirect_args))
        else:
            error_msg = "Invalid email or password."
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": error_msg}), 401
            flash(error_msg, "danger")
            template = "auth/login_admin.html" if portal_type == "admin" else ("auth/login_user.html" if portal_type == "user" else "auth/login_select.html")
            return render_template(template, demo_role=demo_role, wid=wid, portal_type=portal_type), 401

    if portal_type == "user":
        return render_template("auth/login_user.html", demo_role=demo_role, wid=wid, portal_type="user")
    elif portal_type == "admin":
        return render_template("auth/login_admin.html", demo_role=demo_role, wid=wid, portal_type="admin")
    return render_template("auth/login_select.html", demo_role=demo_role, wid=wid)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Portal entry or login handler."""
    portal_type = request.args.get("type")
    if not portal_type:
        role_param = request.args.get("role")
        if role_param == "CUSTOMER":
            portal_type = "user"
        elif role_param in ("LOAN_OFFICER", "LOAN_MANAGER"):
            portal_type = "admin"
    return handle_login(portal_type)


@auth_bp.route("/login/user", methods=["GET", "POST"])
def login_user_view():
    """Dedicated User / Customer login portal."""
    return handle_login("user")


@auth_bp.route("/login/admin", methods=["GET", "POST"])
@auth_bp.route("/login/administration", methods=["GET", "POST"])
def login_admin_view():
    """Dedicated Administration login portal for Officers and Managers."""
    return handle_login("admin")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """State-protected logout endpoint terminating user session (LP-VULN-08)."""
    wid = request.args.get("wid") or request.form.get("wid") or request.headers.get("X-Window-ID")
    demo_role = request.args.get("demo_role") or request.form.get("demo_role") or request.headers.get("X-Demo-Role")

    # 1. Window-scoped session logout
    if wid and "window_sessions" in session:
        window_sessions = dict(session.get("window_sessions", {}))
        w_info = window_sessions.pop(wid, None)
        session["window_sessions"] = window_sessions

        # Only clear database token if it still matches this window's token
        if w_info:
            try:
                user = db.session.get(User, int(w_info["user_id"]))
                if user and user.active_session_token == w_info.get("session_token"):
                    user.active_session_token = None
                    db.session.commit()
            except Exception:
                pass

        if not window_sessions:
            logout_user()
            session.pop("active_session_token", None)
        session.modified = True
        flash("You have been signed out.", "info")
        return redirect(url_for("auth.login", wid=wid))

    # 2. Demo role isolated logout
    if demo_role and "demo_sessions" in session:
        demo_sessions = dict(session.get("demo_sessions", {}))
        scoped_uid = demo_sessions.pop(demo_role, None)
        session["demo_sessions"] = demo_sessions

        session_tokens = dict(session.get("session_tokens", {}))
        demo_token = session_tokens.pop(demo_role, None)
        session["session_tokens"] = session_tokens

        if scoped_uid and demo_token:
            try:
                user = db.session.get(User, int(scoped_uid))
                if user and user.active_session_token == demo_token:
                    user.active_session_token = None
                    db.session.commit()
            except Exception:
                pass

        if demo_sessions:
            remaining_uid = next(iter(demo_sessions.values()))
            session["_user_id"] = str(remaining_uid)
        else:
            logout_user()
            session.pop("demo_sessions", None)
            session.pop("active_session_token", None)
        session.modified = True
        flash(f"Signed out of {demo_role} session.", "info")
        return redirect(url_for("auth.login", demo_role=demo_role))

    # 3. Standard global logout
    curr_token = session.get("active_session_token")
    if current_user and current_user.is_authenticated:
        try:
            if curr_token and current_user.active_session_token == curr_token:
                current_user.active_session_token = None
                db.session.commit()
        except Exception:
            pass

    logout_user()
    session.pop("active_session_token", None)
    session.pop("window_sessions", None)
    session.pop("demo_sessions", None)
    session.pop("session_tokens", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
