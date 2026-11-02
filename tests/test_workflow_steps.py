
from app import db
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


def create_user_and_workflow(app, email):
    """Create a test user and an owned workflow."""

    with app.app_context():
        user = User(
            email=email,
            password_hash="test-password-hash"
        )

        db.session.add(user)
        db.session.flush()

        workflow = Workflow(
            user_id=user.id,
            name="Test Workflow",
            description="Workflow used for testing",
            status="active"
        )

        db.session.add(workflow)
        db.session.commit()

        return user.id, workflow.id


def login_as(client, user_id):
    """Simulate a logged-in user."""

    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_create_workflow_step(client, app):
    user_id, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json={
            "step_type": "trigger",
            "step_order": 1,
            "configuration": {
                "event": "email_received"
            }
        }
    )

    assert response.status_code == 201
    assert response.json["step"]["step_type"] == "trigger"
    assert response.json["step"]["step_order"] == 1


def test_create_step_without_login(client, app):
    _, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json={
            "step_type": "trigger",
            "step_order": 1,
            "configuration": {}
        }
    )

    assert response.status_code == 401


def test_create_step_for_nonexistent_workflow(client):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.post(
        "/api/workflows/9999/steps",
        json={
            "step_type": "trigger",
            "step_order": 1,
            "configuration": {}
        }
    )

    assert response.status_code == 404


def test_user_cannot_add_step_to_another_users_workflow(
    client, app
):
    _, workflow_id = create_user_and_workflow(
        app, "first@example.com"
    )

    second_user_id, _ = create_user_and_workflow(
        app, "second@example.com"
    )

    login_as(client, second_user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json={
            "step_type": "trigger",
            "step_order": 1,
            "configuration": {}
        }
    )

    assert response.status_code == 404


def test_reject_invalid_step_type(client, app):
    user_id, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json={
            "step_type": "notification",
            "step_order": 1,
            "configuration": {}
        }
    )

    assert response.status_code == 400


def test_reject_invalid_step_order(client, app):
    user_id, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json={
            "step_type": "trigger",
            "step_order": 0,
            "configuration": {}
        }
    )

    assert response.status_code == 400


def test_reject_boolean_step_order(client, app):
    user_id, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json={
            "step_type": "trigger",
            "step_order": True,
            "configuration": {}
        }
    )

    assert response.status_code == 400


def test_reject_invalid_configuration(client, app):
    user_id, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json={
            "step_type": "trigger",
            "step_order": 1,
            "configuration": "email_received"
        }
    )

    assert response.status_code == 400


def test_reject_duplicate_step_order(client, app):
    user_id, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )
    login_as(client, user_id)

    payload = {
        "step_type": "trigger",
        "step_order": 1,
        "configuration": {
            "event": "email_received"
        }
    }

    first_response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json=payload
    )

    second_response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        json=payload
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_reject_non_json_step_request(client, app):
    user_id, workflow_id = create_user_and_workflow(
        app, "owner@example.com"
    )
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/steps",
        data="not valid json",
        content_type="application/json"
    )

    assert response.status_code == 400
