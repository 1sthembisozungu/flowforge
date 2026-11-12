
from app import db
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.models.workflow_execution import WorkflowExecution
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


def test_deleting_workflow_also_deletes_steps_and_executions(app):
    user_id = create_test_user(app, "owner@example.com")

    with app.app_context():

        # Create a parent workflow.
        workflow = Workflow(
            user_id=user_id,
            name="Invoice Automation",
            description="Detect invoice emails"
        )

        db.session.add(workflow)
        db.session.flush()

        workflow_id = workflow.id

        # Create a child workflow step.
        step = WorkflowStep(
            workflow_id=workflow_id,
            step_type="trigger",
            step_order=1,
            configuration={
                "event": "email_received"
            }
        )

        # Create a child workflow execution.
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            input_data={
                "subject": "New invoice"
            },
            status="completed",
            result={
                "condition_matched": True,
                "action_executed": True
            }
        )

        db.session.add_all([step, execution])
        db.session.commit()

        # Confirm that the parent and child records exist.
        assert Workflow.query.count() == 1
        assert WorkflowStep.query.count() == 1
        assert WorkflowExecution.query.count() == 1

        # Delete the parent workflow.
        db.session.delete(workflow)
        db.session.commit()

        # Confirm that SQLAlchemy deleted the child records too.
        assert Workflow.query.count() == 0
        assert WorkflowStep.query.count() == 0
        assert WorkflowExecution.query.count() == 0


def test_delete_workflow(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    # Create a workflow with three steps.
    create_response = client.post(
        "/api/workflows",
        json=valid_workflow_payload()
    )

    workflow_id = create_response.json["workflow"]["id"]

    # Delete the workflow.
    response = client.delete(
        f"/api/workflows/{workflow_id}"
    )

    assert response.status_code == 200
    assert response.json["workflow_id"] == workflow_id

    # Verify the workflow and its child records are deleted.
    with app.app_context():
        assert db.session.get(Workflow, workflow_id) is None

        assert WorkflowStep.query.filter_by(
            workflow_id=workflow_id
        ).count() == 0

        assert WorkflowExecution.query.filter_by(
            workflow_id=workflow_id
        ).count() == 0


def test_delete_workflow_without_login(client):
    response = client.delete("/api/workflows/1")

    assert response.status_code == 401


def test_user_cannot_delete_another_users_workflow(client, app):
    first_user_id = create_test_user(app, "first@example.com")
    second_user_id = create_test_user(app, "second@example.com")

    # First user creates a workflow.
    login_as(client, first_user_id)

    create_response = client.post(
        "/api/workflows",
        json={"name": "Private Workflow"}
    )

    workflow_id = create_response.json["workflow"]["id"]

    # Second user attempts to delete it.
    login_as(client, second_user_id)

    response = client.delete(
        f"/api/workflows/{workflow_id}"
    )

    assert response.status_code == 404

    # Confirm the original workflow still exists.
    with app.app_context():
        assert db.session.get(Workflow, workflow_id) is not None


def test_delete_nonexistent_workflow(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    response = client.delete("/api/workflows/9999")

    assert response.status_code == 404


def test_update_workflow(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    # Create the original workflow.
    create_response = client.post(
        "/api/workflows",
        json=valid_workflow_payload()
    )

    workflow_id = create_response.json["workflow"]["id"]

    # Update the workflow.
    response = client.put(
        f"/api/workflows/{workflow_id}",
        json={
            "name": "Invoice Processing",
            "description": "Process incoming invoices."
        }
    )

    assert response.status_code == 200
    assert response.json["workflow"]["name"] == "Invoice Processing"
    assert response.json["workflow"]["description"] == (
        "Process incoming invoices."
    )

    # Confirm that the original workflow steps remain unchanged.
    with app.app_context():
        workflow = db.session.get(Workflow, workflow_id)

        assert workflow is not None
        assert workflow.name == "Invoice Processing"

        assert WorkflowStep.query.filter_by(
            workflow_id=workflow_id
        ).count() == 3


def test_update_workflow_without_login(client):
    response = client.put(
        "/api/workflows/1",
        json={
            "name": "Updated Workflow",
            "description": "Updated description"
        }
    )

    assert response.status_code == 401


def test_user_cannot_update_another_users_workflow(client, app):
    first_user_id = create_test_user(app, "first@example.com")
    second_user_id = create_test_user(app, "second@example.com")

    login_as(client, first_user_id)

    create_response = client.post(
        "/api/workflows",
        json={"name": "Private Workflow"}
    )

    workflow_id = create_response.json["workflow"]["id"]

    # Second user attempts to update the workflow.
    login_as(client, second_user_id)

    response = client.put(
        f"/api/workflows/{workflow_id}",
        json={
            "name": "Hacked Workflow",
            "description": "Unauthorized modification"
        }
    )

    assert response.status_code == 404

    # Confirm the original workflow was not modified.
    with app.app_context():
        workflow = db.session.get(Workflow, workflow_id)

        assert workflow.name == "Private Workflow"


def test_update_nonexistent_workflow(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    response = client.put(
        "/api/workflows/9999",
        json={
            "name": "Updated Workflow",
            "description": "Updated description"
        }
    )

    assert response.status_code == 404


def test_update_workflow_rejects_invalid_data(client, app):
    user_id = create_test_user(app, "owner@example.com")
    login_as(client, user_id)

    create_response = client.post(
        "/api/workflows",
        json={"name": "Original Workflow"}
    )

    workflow_id = create_response.json["workflow"]["id"]

    # Attempt to update using an empty workflow name.
    response = client.put(
        f"/api/workflows/{workflow_id}",
        json={
            "name": "   ",
            "description": "Updated description"
        }
    )

    assert response.status_code == 400

    # Confirm that the original name remains unchanged.
    with app.app_context():
        workflow = db.session.get(Workflow, workflow_id)

        assert workflow.name == "Original Workflow"



def test_activate_workflow(client, app):
    with app.app_context():
        workflow = Workflow(
            user_id=1,
            name="Inactive Workflow",
            description="Test activation",
            status="inactive"
        )
        db.session.add(workflow)
        db.session.commit()
        workflow_id = workflow.id

        with client.session_transaction() as session:
                session["user_id"] = 1

    response = client.patch(
        f"/api/workflows/{workflow_id}/status",
        json={"status": "active"}
    )

    assert response.status_code == 200
    assert response.json["status"] == "active"


def test_deactivate_workflow(client, app):
    with app.app_context():
        workflow = Workflow(
            user_id=1,
            name="Active Workflow",
            description="Test deactivation",
            status="active"
        )
        db.session.add(workflow)
        db.session.commit()
        workflow_id = workflow.id

        with client.session_transaction() as session:
                session["user_id"] = 1

    response = client.patch(
        f"/api/workflows/{workflow_id}/status",
        json={"status": "inactive"}
    )

    assert response.status_code == 200
    assert response.json["status"] == "inactive"


def test_update_workflow_status_without_login(client, app):
    with app.app_context():
        workflow = Workflow(
            user_id=1,
            name="Test Workflow",
            description="Authentication test",
            status="active"
        )
        db.session.add(workflow)
        db.session.commit()
        workflow_id = workflow.id

        # with client.session_transaction() as session:
        #         session["user_id"] = 1

    response = client.patch(
        f"/api/workflows/{workflow_id}/status",
        json={"status": "inactive"}
    )

    assert response.status_code == 401



def test_user_cannot_update_another_users_workflow_status(
    client, app
):
    with app.app_context():
        workflow = Workflow(
            user_id=1,
            name="User One Workflow",
            description="Ownership test",
            status="active"
        )
        db.session.add(workflow)
        db.session.commit()
        workflow_id = workflow.id

    with client.session_transaction() as session:
        session["user_id"] = 2

    response = client.patch(
        f"/api/workflows/{workflow_id}/status",
        json={"status": "inactive"}
    )

    assert response.status_code == 404

    with app.app_context():
        workflow = db.session.get(Workflow, workflow_id)
        assert workflow.status == "active"


def test_update_status_of_nonexistent_workflow(client):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.patch(
        "/api/workflows/9999/status",
        json={"status": "inactive"}
    )

    assert response.status_code == 404


def test_update_workflow_status_rejects_invalid_status(
    client, app
):
    with app.app_context():
        workflow = Workflow(
            user_id=1,
            name="Test Workflow",
            description="Invalid status test",
            status="active"
        )
        db.session.add(workflow)
        db.session.commit()
        workflow_id = workflow.id

    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.patch(
        f"/api/workflows/{workflow_id}/status",
        json={"status": "paused"}
    )

    assert response.status_code == 400

    with app.app_context():
        workflow = db.session.get(Workflow, workflow_id)
        assert workflow.status == "active"

