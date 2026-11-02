
from app import db
from app.models.user import User
from app.models.workflow import Workflow


def create_test_user(app, email):
    """Create a user in the test database."""

    with app.app_context():
        user = User(
            email=email,
            password_hash="test-password-hash"
        )

        db.session.add(user)
        db.session.commit()

        return user.id


def login_as(client, user_id):
    """Simulate an authenticated user session."""

    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_create_workflow(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    response = client.post("/api/workflows", json={
        "name": "Invoice Automation",
        "description": "Detect invoice emails",
        "status": "active"
    })

    assert response.status_code == 201
    assert response.json["workflow"]["name"] == "Invoice Automation"
    assert response.json["workflow"]["user_id"] == user_id


def test_get_workflows(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    client.post("/api/workflows", json={
        "name": "Invoice Automation"
    })

    response = client.get("/api/workflows")

    assert response.status_code == 200
    assert len(response.json["workflows"]) == 1
    assert response.json["workflows"][0]["name"] == "Invoice Automation"


def test_get_workflows_without_login(client):
    response = client.get("/api/workflows")

    assert response.status_code == 401


def test_create_workflow_without_login(client):
    response = client.post("/api/workflows", json={
        "name": "Unauthorized Workflow"
    })

    assert response.status_code == 401


def test_create_workflow_without_name(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    response = client.post("/api/workflows", json={
        "description": "A workflow without a name"
    })

    assert response.status_code == 400


def test_users_cannot_see_other_users_workflows(client, app):
    first_user_id = create_test_user(app, "first@example.com")
    second_user_id = create_test_user(app, "second@example.com")

    # First user creates a workflow.
    login_as(client, first_user_id)

    client.post("/api/workflows", json={
        "name": "Private Workflow"
    })

    # Second user logs in.
    login_as(client, second_user_id)

    response = client.get("/api/workflows")

    assert response.status_code == 200
    assert len(response.json["workflows"]) == 0


def test_workflow_rejects_invalid_status(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    response = client.post("/api/workflows", json={
        "name": "Invalid Workflow",
        "status": "running"
    })

    assert response.status_code == 400
