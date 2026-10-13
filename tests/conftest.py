"""Pytest fixtures for LoanPulse test suite."""
import pytest
from src.app import create_app
from src.models import db
from src.seed import seed_database


@pytest.fixture(scope="session")
def app():
    """Create and configure a new app instance for test session."""
    test_app = create_app(config_name="testing")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client for issuing requests."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Clean database session per test."""
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


@pytest.fixture
def seeded_db(app):
    """Database populated with synthetic CSV records."""
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        seed_database(app)
        yield db.session
        db.session.remove()
        db.drop_all()
