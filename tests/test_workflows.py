
from app import db
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from sqlalchemy import event


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


def valid_workflow_payload():
    """Return a workflow with all three required steps."""

    return {
        "name": "Invoice Automation",
        "description": "Detect invoice emails",
        "status": "active",
        "steps": [
            {
                "step_type": "trigger",
                "step_order": 1,
                "configuration": {
                    "event": "email_received"
                }
            },
            {
                "step_type": "condition",
                "step_order": 2,
                "configuration": {
                    "field": "subject",
                    "operator": "contains",
                    "value": "invoice"
                }
            },
            {
                "step_type": "action",
                "step_order": 3,
                "configuration": {
                    "type": "log_message",
                    "message": "Invoice email detected."
                }
            }
        ]
    }


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


def test_create_workflow_with_three_steps(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    response = client.post(
        "/api/workflows",
        json=valid_workflow_payload()
    )

    assert response.status_code == 201

    workflow_id = response.json["workflow"]["id"]

    with app.app_context():
        workflow = db.session.get(Workflow, workflow_id)

        steps = WorkflowStep.query.filter_by(
            workflow_id=workflow_id
        ).order_by(
            WorkflowStep.step_order.asc()
        ).all()

        assert workflow is not None
        assert workflow.user_id == user_id

        assert len(steps) == 3

        assert steps[0].step_type == "trigger"
        assert steps[1].step_type == "condition"
        assert steps[2].step_type == "action"

        assert [step.step_order for step in steps] == [1, 2, 3]

def test_create_workflow_rejects_invalid_steps(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    payload = valid_workflow_payload()

    # Give the condition step an invalid position.
    payload["steps"][1]["step_order"] = 5

    response = client.post(
        "/api/workflows",
        json=payload
    )

    assert response.status_code == 400

    with app.app_context():
        workflows = Workflow.query.all()

        assert len(workflows) == 0


def test_create_workflow_rolls_back_if_step_creation_fails(
    client,
    app
):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    def simulate_database_failure(mapper, connection, target):
        raise RuntimeError("Simulated step insertion failure")

    event.listen(
        WorkflowStep,
        "before_insert",
        simulate_database_failure
    )

    try:
        response = client.post(
            "/api/workflows",
            json=valid_workflow_payload()
        )
    finally:
        event.remove(
            WorkflowStep,
            "before_insert",
            simulate_database_failure
        )

    # The simulated database failure should return HTTP 500.
    assert response.status_code == 500

    with app.app_context():
        workflows = Workflow.query.all()
        steps = WorkflowStep.query.all()

        # The transaction should have rolled back everything.
        assert len(workflows) == 0
        assert len(steps) == 0
