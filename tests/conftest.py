"""
conftest.py
Shared pytest fixtures used across all test modules.
"""

import os
import configparser
import pytest


@pytest.fixture(autouse=True)
def configure_celery_eager():
    from celeryWorker import app as celery_app

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_store_eager_result=True,
        result_backend="cache+memory://",
    )
    celery_app._backend = celery_app._get_backend()

    yield

    try:
        del celery_app._backend
    except AttributeError:
        pass
    celery_app.conf.update(task_always_eager=False)
    
    
@pytest.fixture(scope="session", autouse=True)
def _write_test_config(tmp_path_factory):
    """
    Write a minimal config.ini into the project root directory so that
    config.py can be imported during tests without a real config file.
    Uses monkeypatching at session scope via a tmp dir.
    """
    cfg_dir = tmp_path_factory.mktemp("cfg")
    cfg_path = cfg_dir / "config.ini"
    cfg_path.write_text(
        "[app]\n"
        "production = false\n\n"
        "[redis_dev]\n"
        "url = redis://localhost:6379/0\n\n"
        "[redis_prod]\n"
        "password = \n"
        "host = localhost\n"
        "port = 6379\n"
        "db = 0\n\n"
        "[celery]\n"
        "default_queue = wikifile-transfer\n"
        "result_expires = 3600\n\n"
        "[logging]\n"
        "level = DEBUG\n"
        "dir = /tmp/test_logs\n"
    )
    # Point config module to this file by patching the path before import
    import importlib, sys

    # Patch os.path so config._CONFIG_PATH resolves to our temp file
    original = os.path.join
    def patched_join(*args):
        result = original(*args)
        if result.endswith("config.ini"):
            return str(cfg_path)
        return result

    os.path.join = patched_join
    yield
    os.path.join = original


# ── Flask app fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def flask_app():
    """
    Create a Flask test app with an in-memory SQLite database.
    Patches MWOAuth and Celery so no real connections are made.
    """
    import yaml
    from unittest.mock import MagicMock, patch

    # Minimal config.yaml content so app.py does not crash on startup
    fake_yaml = {
        "ENV": "dev",
        "OAUTH_MWURI": "https://en.wikipedia.org",
        "CONSUMER_KEY": "test_consumer_key",
        "CONSUMER_SECRET": "test_consumer_secret",
        "SECRET_KEY": "test_secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }

    import builtins
    yaml_str = yaml.dump(fake_yaml)
    original_open = builtins.open

    with patch("builtins.open", side_effect=lambda path, *a, **kw:
            __import__("io").StringIO(yaml_str) if str(path).endswith("config.yaml") else original_open(path, *a, **kw)), \
        patch("flask_mwoauth.MWOAuth") as mock_mwoauth, \
        patch("celeryWorker.app") as mock_celery:

        mock_mwoauth.return_value.bp = MagicMock()
        mock_mwoauth.return_value.get_current_user = MagicMock(return_value="TestUser")

        import app as flask_module
        flask_module.app.config["TESTING"] = True
        flask_module.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        flask_module.app.config["WTF_CSRF_ENABLED"] = False

        with flask_module.app.app_context():
            flask_module.db.create_all()

        yield flask_module.app


@pytest.fixture
def client(flask_app):
    """Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def app_ctx(flask_app):
    """Push an application context for tests that need it."""
    with flask_app.app_context():
        yield


@pytest.fixture
def authed_client(client):
    """
    A test client that already has a mock OAuth session set in the cookie,
    so authenticated_session() returns a valid OAuth1 object.
    """
    with client.session_transaction() as sess:
        sess["mwoauth_access_token"] = {
            "key": "test_token_key",
            "secret": "test_token_secret",
        }
    return client
