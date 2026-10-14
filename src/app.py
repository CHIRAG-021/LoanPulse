"""Flask application factory for LoanPulse."""
import os
import gzip
import click
from flask import Flask, jsonify, request, session, g, has_request_context, render_template, flash, redirect, url_for, send_from_directory
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError

from src.config import config_by_name, normalize_database_url
from src.models import db, User

login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def ensure_schema_compatibility(app: Flask):
    """Ensure all declared model tables and columns exist in SQLite database on startup."""
    if app.config.get("TESTING"):
        return

    with app.app_context():
        try:
            import csv
            from pathlib import Path
            from sqlalchemy import inspect, text
            from src.models import User, LoanApplication, CustomerDocument, Assessment, LoanProduct, ApplicationAuditLog
            db.create_all()
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()

            models = [User, LoanApplication, CustomerDocument, Assessment, LoanProduct, ApplicationAuditLog]
            with db.engine.connect() as conn:
                for model in models:
                    table_name = model.__tablename__
                    if table_name in table_names:
                        existing_cols = {col['name'] for col in inspector.get_columns(table_name)}
                        for col in model.__table__.columns:
                            if col.name not in existing_cols:
                                col_type = col.type.compile(db.engine.dialect)
                                default_clause = ""
                                if col.name == "kyc_status":
                                    default_clause = " DEFAULT 'NOT_STARTED'"
                                elif col.name == "loan_purpose":
                                    default_clause = " DEFAULT 'PERSONAL'"
                                elif col.name == "existing_obligations":
                                    default_clause = " DEFAULT 0.0"
                                elif col.name == "active":
                                    default_clause = " DEFAULT 1"
                                elif col.default is not None and getattr(col.default, "is_scalar", False):
                                    val = col.default.arg
                                    if isinstance(val, str):
                                        default_clause = f" DEFAULT '{val}'"
                                    elif isinstance(val, (int, float)):
                                        default_clause = f" DEFAULT {val}"
                                sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default_clause}"
                                conn.execute(text(sql))
                conn.commit()

            # Ensure initial loan products exist in database
            if LoanProduct.query.count() == 0:
                products_file = Path(__file__).resolve().parent.parent / "data" / "loan_products.csv"
                if products_file.exists():
                    with open(products_file, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            p = LoanProduct(
                                product_id=int(r["product_id"]),
                                product_name=r["product_name"].strip(),
                                product_code=r["product_code"].strip(),
                                description=r.get("description", "").strip(),
                                min_amount=float(r["min_amount"]),
                                max_amount=float(r["max_amount"]),
                                min_term_months=int(r["min_term_months"]),
                                max_term_months=int(r["max_term_months"]),
                                annual_interest_rate=float(r["annual_interest_rate"]),
                                min_monthly_income=float(r["min_monthly_income"]),
                                max_loan_to_income_ratio=float(r["max_loan_to_income_ratio"]),
                                active=r.get("active", "True").strip().lower() in ("true", "1", "yes"),
                            )
                            db.session.add(p)
                    db.session.commit()
        except Exception:
            pass


def create_app(config_name=None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Determine configuration
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # Dynamic environment variable overrides (never override in-memory DB during testing)
    if os.getenv("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    if not app.config.get("TESTING") and os.getenv("DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(os.getenv("DATABASE_URL"))
    if "SESSION_COOKIE_SECURE" in os.environ:
        app.config["SESSION_COOKIE_SECURE"] = os.environ["SESSION_COOKIE_SECURE"].lower() in ("true", "1")
    if "BEHIND_PROXY" in os.environ:
        app.config["BEHIND_PROXY"] = os.environ["BEHIND_PROXY"].lower() in ("true", "1")

    # Configure structured production logging (Phase 9)
    import logging
    if not app.logger.handlers:
        log_handler = logging.StreamHandler()
        log_formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        log_handler.setFormatter(log_formatter)
        app.logger.addHandler(log_handler)
    app.logger.setLevel(logging.INFO if not app.debug else logging.DEBUG)

    if config_name == "production":
        secret_key = str(app.config.get("SECRET_KEY") or "")
        forbidden_defaults = {
            "change-this-for-local-development",
            "change_this_to_a_secure_production_secret_key_32_bytes",
            "dev_secret_key_12345",
            "change-me",
            "your-secret-key-here",
        }
        if not secret_key or len(secret_key) < 32 or secret_key in forbidden_defaults:
            error_msg = (
                "CRITICAL SECURITY CONFIGURATION ERROR: Production mode requires a secure, non-default SECRET_KEY "
                "environment variable with at least 32 characters. Set SECRET_KEY in your environment (e.g., generate with: "
                "python3 -c 'import secrets; print(secrets.token_hex(32))')."
            )
            app.logger.critical(error_msg)
            raise RuntimeError(error_msg)

    # Proxy handling for production reverse proxies (HTTPS termination)
    if app.config.get("BEHIND_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    ensure_schema_compatibility(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.unauthorized_handler
    def unauthorized_callback():
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Authentication required"}), 401
        flash("Please sign in to access this page.", "info")
        return redirect(url_for("auth.login", next=request.url))

    def _resolve_user(fallback_user_id=None):
        if not has_request_context():
            if fallback_user_id:
                try:
                    return db.session.get(User, int(fallback_user_id))
                except (ValueError, TypeError):
                    return None
            return None

        path = request.path

        # 1. Window-scoped session validation if wid provided:
        wid = request.args.get("wid") or request.headers.get("X-Window-ID")
        if wid and "window_sessions" in session:
            w_info = session["window_sessions"].get(wid)
            if w_info:
                try:
                    u = db.session.get(User, int(w_info["user_id"]))
                    token = w_info.get("session_token")
                    if u and u.is_active and (not token or u.active_session_token == token):
                        return u
                except (ValueError, TypeError):
                    pass
            return None

        # 2. Multi-tab isolated demo session support if demo_role provided:
        demo_role = request.args.get("demo_role") or request.headers.get("X-Demo-Role")
        if demo_role:
            demo_sessions = session.get("demo_sessions", {}) or session.get("role_sessions", {})
            scoped_uid = demo_sessions.get(demo_role)
            if scoped_uid:
                try:
                    u = db.session.get(User, int(scoped_uid))
                    token = session.get("session_tokens", {}).get(demo_role) or session.get("role_tokens", {}).get(demo_role) or session.get("active_session_token")
                    if u and u.is_active and (not token or u.active_session_token == token):
                        return u
                except (ValueError, TypeError):
                    pass
            return None

        # 3. Path-based role session isolation:
        # Ensures Customer (/customer, /applications), Officer (/officer), and Manager (/manager) tabs
        # running in the same browser NEVER conflict with each other.
        role_sessions = session.get("role_sessions", {})
        role_tokens = session.get("role_tokens", {})

        target_role = None
        if path.startswith("/customer/documents/"):
            # Shared access route: Customer, Officer, and Manager can access documents
            target_role = None
        elif path.startswith("/applications/") and "/status" in path:
            # Shared status route: Customer, Officer, and Manager can access status
            target_role = None
        elif path.startswith("/customer") or path == "/applications" or path.startswith("/applications/new"):
            target_role = "CUSTOMER"
        elif path.startswith("/officer"):
            target_role = "LOAN_OFFICER"
        elif path.startswith("/manager"):
            target_role = "LOAN_MANAGER"
        elif path.startswith("/login/user"):
            target_role = "CUSTOMER"
        elif path.startswith("/login/admin") or path.startswith("/login/administration"):
            act = session.get("active_role")
            if act in ("LOAN_OFFICER", "LOAN_MANAGER"):
                target_role = act

        if target_role:
            if target_role in role_sessions:
                try:
                    u = db.session.get(User, int(role_sessions[target_role]))
                    token = role_tokens.get(target_role)
                    if u and u.is_active and (not token or u.active_session_token == token):
                        return u
                except (ValueError, TypeError):
                    pass
                return None

            # target_role is not in role_sessions:
            # If target_role is CUSTOMER: do NOT fall back to staff roles. A new tab opening /customer
            # must not inherit staff roles or trigger 403; it must redirect to customer login.
            if target_role == "CUSTOMER":
                return None

            # If target_role is LOAN_MANAGER, but LOAN_OFFICER is authenticated:
            # Fallback to the LOAN_OFFICER user so role_required can enforce RBAC and abort(403)
            if target_role == "LOAN_MANAGER" and "LOAN_OFFICER" in role_sessions:
                try:
                    u = db.session.get(User, int(role_sessions["LOAN_OFFICER"]))
                    token = role_tokens.get("LOAN_OFFICER")
                    if u and u.is_active and (not token or u.active_session_token == token):
                        return u
                except (ValueError, TypeError):
                    pass

            # If target_role is staff (LOAN_OFFICER or LOAN_MANAGER), and CUSTOMER is authenticated:
            # Fallback to CUSTOMER so role_required can enforce RBAC and abort(403)
            if "CUSTOMER" in role_sessions:
                try:
                    u = db.session.get(User, int(role_sessions["CUSTOMER"]))
                    token = role_tokens.get("CUSTOMER")
                    if u and u.is_active and (not token or u.active_session_token == token):
                        return u
                except (ValueError, TypeError):
                    pass

            # Otherwise, unauthenticated for this role
            return None

        # 4. For non-role-specific paths (e.g. /, /notifications, /profile):
        active_role = session.get("active_role")
        if active_role and active_role in role_sessions:
            try:
                u = db.session.get(User, int(role_sessions[active_role]))
                token = role_tokens.get(active_role)
                if u and u.is_active and (not token or u.active_session_token == token):
                    return u
            except (ValueError, TypeError):
                pass

        if role_sessions:
            first_role, first_uid = next(iter(role_sessions.items()))
            try:
                u = db.session.get(User, int(first_uid))
                token = role_tokens.get(first_role)
                if u and u.is_active and (not token or u.active_session_token == token):
                    return u
            except (ValueError, TypeError):
                pass

        uid_to_check = fallback_user_id or session.get("_user_id")
        if uid_to_check:
            try:
                u = db.session.get(User, int(uid_to_check))
                token = session.get("active_session_token")
                if u and u.is_active and (not token or u.active_session_token == token):
                    return u
            except (ValueError, TypeError):
                pass

        return None

    @login_manager.user_loader
    def load_user(user_id):
        return _resolve_user(user_id)

    @login_manager.request_loader
    def load_user_from_request(req):
        return _resolve_user()

    @app.before_request
    def pre_request_tasks():
        # Ensure fresh user resolution per request when demo_role or wid may vary across concurrent requests/tabs
        if "_login_user" in g:
            g.pop("_login_user", None)

        # Content negotiation for modern image formats when accepted by browser (Image Delivery optimization)
        if request.path in ("/static/loanpulse.png", "/loanpulse.png"):
            accept = request.headers.get("Accept", "")
            if "image/webp" in accept:
                res = send_from_directory(app.static_folder, "loanpulse.webp", mimetype="image/webp")
                res.headers["Vary"] = "Accept"
                return res

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "CSRF validation failed", "message": e.description}), 400
        return render_template(
            "error.html",
            code=400,
            title="Bad Request (Security Check)",
            message="Your session security token is missing or invalid. Please refresh the page and try again.",
        ), 400

    @app.after_request
    def set_security_headers(response):
        """Set cache control and defensive HTTP security headers (LP-VULN-09) and static asset caching."""
        if request.endpoint in ("static", "favicon"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Defensive HTTP security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # Frontend-compatible Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Dynamic gzip compression for text/json/css/js when client supports it
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if (
            "gzip" in accept_encoding.lower()
            and 200 <= response.status_code < 300
            and "Content-Encoding" not in response.headers
            and (response.mimetype.startswith("text/") or response.mimetype in ("application/json", "application/javascript", "image/svg+xml"))
        ):
            response.direct_passthrough = False
            data = response.get_data()
            if len(data) > 500:
                compressed = gzip.compress(data, compresslevel=6)
                response.set_data(compressed)
                response.headers["Content-Encoding"] = "gzip"
                response.headers["Content-Length"] = str(len(compressed))
                vary = response.headers.get("Vary")
                if vary:
                    if "Accept-Encoding" not in vary:
                        response.headers["Vary"] = f"{vary}, Accept-Encoding"
                else:
                    response.headers["Vary"] = "Accept-Encoding"

        return response

    @app.url_defaults
    def propagate_request_context(endpoint, values):
        """Automatically propagate active demo_role and wid across url_for calls in test tabs only."""
        if endpoint != "static" and has_request_context():
            if endpoint in ("auth.index", "auth.landing", "auth.login", "auth.login_user_view", "auth.login_admin_view", "auth.signup", "auth.logout"):
                return
            if "demo_role" in request.args and "demo_role" not in values:
                values["demo_role"] = request.args["demo_role"]
            wid = request.args.get("wid")
            if wid and "wid" not in values:
                values["wid"] = wid

    @app.context_processor
    def inject_global_template_data():
        unread_count = 0
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            try:
                from src.models import Notification
                if current_user.role == "CUSTOMER":
                    unread_count = Notification.query.filter_by(recipient_user_id=current_user.user_id, is_read=False).count()
                else:
                    unread_count = Notification.query.filter_by(is_read=False).count()
            except Exception:
                unread_count = 0
        return {"unread_notifications_count": unread_count}

    # Register blueprints
    from src.routes import auth_bp, customer_bp, officer_bp, manager_bp, notifications_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(officer_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(notifications_bp)

    # CLI command to initialize and seed database
    @app.cli.command("init-db")
    @click.option("--seed/--no-seed", default=True, help="Seed database with CSV records")
    def init_db_command(seed):
        """Create database tables and optionally seed data."""
        from src.seed import seed_database
        db.create_all()
        if seed:
            counts = seed_database(app)
            click.echo("Database initialized and seeded successfully:")
            for table, count in counts.items():
                click.echo(f"  {table}: {count} records")
        else:
            click.echo("Database tables created.")

    # Basic system health check route
    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok", "app": "LoanPulse"})

    # Browser favicon and brand asset direct endpoints
    @app.route("/favicon.ico")
    @app.route("/loanpulse.png")
    def favicon():
        return send_from_directory(app.static_folder, "loanpulse.png", mimetype="image/png")

    # Database transaction safety: rollback on unhandled exceptions (Phase 9)
    @app.teardown_request
    def teardown_request_handler(exception=None):
        if exception is not None:
            try:
                db.session.rollback()
            except Exception:
                pass

    # Custom Error Handlers for Production Readiness (Phase 9)
    @app.errorhandler(400)
    def handle_bad_request(error):
        desc = getattr(error, "description", "The request could not be processed due to invalid parameters.")
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Bad Request", "message": desc}), 400
        return render_template("error.html", code=400, title="Bad Request", message=desc), 400

    @app.errorhandler(403)
    def handle_forbidden(error):
        desc = getattr(error, "description", "You do not have permission to access this protected resource.")
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Forbidden", "message": desc}), 403
        return render_template("error.html", code=403, title="Access Denied", message=desc), 403

    @app.errorhandler(404)
    def handle_not_found(error):
        desc = getattr(error, "description", "The requested page or record could not be found.")
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Not Found", "message": desc}), 404
        return render_template("error.html", code=404, title="Record or Page Not Found", message=desc), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        desc = getattr(error, "description", "The HTTP method is not permitted for this endpoint.")
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Method Not Allowed", "message": desc}), 405
        return render_template("error.html", code=405, title="Method Not Allowed", message=desc), 405

    @app.errorhandler(500)
    def handle_internal_server_error(error):
        try:
            db.session.rollback()
        except Exception:
            pass
        app.logger.error(f"Internal server error: {error}")
        desc = "An unexpected server error occurred. Our engineering team has been logged."
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Internal Server Error", "message": desc}), 500
        return render_template("error.html", code=500, title="Internal Server Error", message=desc), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
