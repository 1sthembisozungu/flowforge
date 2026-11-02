import pytest

from app import create_app, db

# Import models so SQLAlchemy knows about all database tables.
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.models.workflow_execution import WorkflowExecution


@pytest.fixture
def app(): #create a separate flask app for testing
    test_app = create_app({
        "TESTING": True, # enables flask application for testing
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    })

    with test_app.app_context():
        db.create_all() # create the database table

        yield test_app #makes application available to test

        db.session.remove()
        db.drop_all() #removes test tables for testing

#makes a reusable resource available to tests
@pytest.fixture
def client(app): # allows etst to simulates HTTP requests
    return app.test_client()