"""
Unit tests for the User model (model.py).
"""
from model import User


def test_new_user():
    """
    GIVEN a User model
    WHEN a new User is created with required fields
    THEN check the username, project, and language fields are defined correctly
    """
    user = User(username='Anirudh', pref_project='wikipedia', pref_language='en')

    assert user.username == 'Anirudh'
    assert user.pref_project == 'wikipedia'
    assert user.pref_language == 'en'
    assert user.user_language is None
    assert user.skip_upload_selection is None


def test_new_user_with_fixture(new_user):
    """
    GIVEN a User model
    WHEN a new User is created via the new_user fixture
    THEN check the custom fields are stored correctly
    """
    assert new_user.username == 'TestWikiUser'
    assert new_user.pref_project == 'wikipedia'
    assert new_user.pref_language == 'en'
    assert new_user.user_language == 'fr'
    assert new_user.skip_upload_selection == True


def test_user_default_values():
    """
    GIVEN a User model
    WHEN a new User is created with only the username
    THEN check that default values are applied correctly
    """
    user = User(username='DefaultUser')

    assert user.username == 'DefaultUser'
    assert user.pref_project is None
    assert user.pref_language is None
    assert user.user_language is None
    assert user.skip_upload_selection is None


def test_user_repr():
    """
    GIVEN a User model
    WHEN __repr__ is called on a User instance
    THEN check it returns the expected string representation
    """
    user = User(username='ReprTestUser')

    assert repr(user) == "<User 'ReprTestUser'>"


def test_user_all_custom_fields():
    """
    GIVEN a User model
    WHEN a new User is created with all custom fields set
    THEN check every field is stored correctly
    """
    user = User(
        username='CustomUser',
        pref_project='wiktionary',
        pref_language='de',
        user_language='ja',
        skip_upload_selection=True
    )

    assert user.username == 'CustomUser'
    assert user.pref_project == 'wiktionary'
    assert user.pref_language == 'de'
    assert user.user_language == 'ja'
    assert user.skip_upload_selection == True