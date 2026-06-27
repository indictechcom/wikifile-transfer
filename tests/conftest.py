import os
import pytest

# Point to a minimal test config before the app is imported
os.environ.setdefault("WIKIFILE_TEST", "1")


@pytest.fixture(scope="session")
def app():
    """Create the Flask app configured for testing."""
    # Import here so env var is set first
    from app import app as flask_app

    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_ENABLED=False,
    )

    yield flask_app


@pytest.fixture(scope="session")
def db(app):
    """Create all tables for the test session, drop them after."""
    from model import db as _db

    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture()
def client(app, db):
    """A test client for making requests."""
    return app.test_client()


@pytest.fixture()
def app_context(app):
    """Push an application context."""
    with app.app_context():
        yield
