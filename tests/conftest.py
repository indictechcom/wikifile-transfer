"""
tests/conftest.py – Pytest configuration and shared fixtures.

The Flask application is imported once per test session with external
dependencies replaced by mocks so no live infrastructure is required:

  - celery.Celery  →  MagicMock  (no Redis broker needed)
  - flask_mwoauth.MWOAuth → MagicMock  (no OAuth server needed)

Individual tests can override specific mock behaviour via monkeypatching.
The test database is always an in-memory SQLite instance so MySQL is not
required either.
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Bootstrap: apply patches BEFORE the application module is imported.
#
# celeryWorker.py executes  app = Celery(...)  at import time, which would
# try to reach a Redis broker.  flask_mwoauth.MWOAuth contacts an OAuth
# server on construction.  Both are mocked out here so the test suite runs
# with zero external infrastructure.
# ---------------------------------------------------------------------------

# Build a realistic-enough MWOAuth mock so Flask doesn't reject the blueprint.
_mock_mwoauth_instance = MagicMock()
_mock_mwoauth_instance.bp.name = "mwoauth"       # Flask requires a unique blueprint name
_mock_mwoauth_instance.get_current_user.return_value = None  # unauthenticated by default

_celery_patcher = patch("celery.Celery", MagicMock())
_mwoauth_patcher = patch("flask_mwoauth.MWOAuth", return_value=_mock_mwoauth_instance)

_celery_patcher.start()
_mwoauth_patcher.start()

import app as _app_module  # noqa: E402 – must come after patches
from model import db as _db  # noqa: E402

_celery_patcher.stop()
_mwoauth_patcher.stop()


# ---------------------------------------------------------------------------
# Session-scoped fixtures (created once for the entire test run)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def flask_app():
    """
    Application configured for testing:
    - In-memory SQLite (no MySQL needed).
    - TESTING=True so Flask propagates exceptions to the test client instead
      of returning a generic 500, which makes assertion errors easier to read.
    """
    _app_module.app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with _app_module.app.app_context():
        _db.create_all()
    return _app_module.app


@pytest.fixture(scope="session")
def client(flask_app):
    """Unauthenticated test client – no OAuth session cookie present."""
    return flask_app.test_client()


# ---------------------------------------------------------------------------
# Function-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_client(flask_app):
    """
    Test client with a fake OAuth session injected.

    Use this fixture for routes that require the user to be logged in
    (upload, edit_page, preference POST, language POST).
    """
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["mwoauth_access_token"] = {
                "key":    "test_oauth_key",
                "secret": "test_oauth_secret",
            }
        yield c


@pytest.fixture
def mock_mwoauth():
    """
    Expose the MWOAuth mock instance so individual tests can set return
    values (e.g. ``mock_mwoauth.get_current_user.return_value = 'Alice'``).
    """
    return _mock_mwoauth_instance
