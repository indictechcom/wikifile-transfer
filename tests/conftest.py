import os
import pytest
from unittest.mock import patch
import yaml

_original_safe_load = yaml.safe_load

def _mock_safe_load(f):
    data = _original_safe_load(f)
    if isinstance(data, dict) and 'SQLALCHEMY_DATABASE_URI' in data:
        data['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return data

yaml_patcher = patch('yaml.safe_load', side_effect=_mock_safe_load)
yaml_patcher.start()

from model import db, User


@pytest.fixture(scope='session')
def app():
    """
    Fixture to configure the Flask app for testing and return the app instance.
    Session-scoped: created once per test session.
    """
    # Import app here to ensure env var override is active
    from app import app as flask_app

    # Set Flask configurations for testing
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False

    # Reconfigure the SQLAlchemy engine to use the in-memory SQLite DB
    # This is needed because db.init_app() at module level cached the MySQL engine
    with flask_app.app_context():
        db.engine.dispose()
        # Initialize the in-memory database
        db.create_all()

        yield flask_app

        # Teardown: clean up the database after all module tests
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture(scope='session')
def celery_config():
    return {
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://'
    }


@pytest.fixture(scope='module')
def new_user():
    """
    Fixture to create a User object for unit testing.
    Module-scoped: created once per test module.
    """
    user = User(
        username='TestWikiUser',
        pref_project='wikipedia',
        pref_language='en',
        user_language='fr',
        skip_upload_selection=True
    )
    return user


@pytest.fixture(scope='function')
def init_database(app):
    """
    Fixture to seed the in-memory test database with a sample user.
    Function-scoped: seeds a fresh user for each test and cleans up afterwards.
    """
    with app.app_context():
        user = User(
            username='TestUser',
            pref_project='wikipedia',
            pref_language='en',
            user_language='en',
            skip_upload_selection=False
        )
        db.session.add(user)
        db.session.commit()

        yield db

        # Teardown: remove the seeded data
        db.session.rollback()
        User.query.delete()
        db.session.commit()