"""Flask application factory for LoanPulse."""
import os
import click
from flask import Flask, jsonify
from flask_login import LoginManager

from src.config import config_by_name
from src.models import db, User

login_manager = LoginManager()


def create_app(config_name=None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Determine configuration
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
