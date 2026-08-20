import pytest
from model import db, User


@pytest.fixture(autouse=True)
def db_cleanup(client):
    """
    Automatically clean up the database after each functional test.
    Ensures test isolation by removing all user records created during the test.
    """
    yield
    db.session.rollback()
    User.query.delete()
    db.session.commit()
