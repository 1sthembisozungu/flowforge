
from app import db
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.models.workflow_execution import WorkflowExecution


def create_test_workflow(app, email="owner@example.com"):
    with app.app_context():
        user = User(
            email=email,
            password_hash="test-password-hash"
        )
        db.session.add(user)
        db.session.flush()

        workflow = Workflow(
            user_id=user.id,
            name="Invoice Workflow",
            description="Detect invoice emails",
            status="active"
        )
        db.session.add(workflow)
        db.session.flush()

        steps = [
            WorkflowStep(
                workflow_id=workflow.id,
                step_type="trigger",
                step_order=1,
                configuration={"event": "email_received"}
            ),
            WorkflowStep(
                workflow_id=workflow.id,
                step_type="condition",
                step_order=2,
                configuration={
                    "field": "subject",
                    "operator": "contains",
                    "value": "invoice"
                }
            ),
            WorkflowStep(
                workflow_id=workflow.id,
                step_type="action",
                step_order=3,
                configuration={
                    "type": "log_message",
                    "message": "Invoice email detected."
                }
            )
        ]

        db.session.add_all(steps)
        db.session.commit()

        return user.id, workflow.id


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_execute_workflow_with_matching_email(client, app):
    user_id, workflow_id = create_test_workflow(app)
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "New invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "completed"
    assert response.json["result"]["condition_matched"] is True
    assert response.json["result"]["action_executed"] is True
    assert response.json["result"]["action_result"]["message"] == (
        "Invoice email detected."
    )

def test_execute_workflow_with_non_matching_email(client, app):
    user_id, workflow_id = create_test_workflow(app)
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Meeting scheduled for Monday",
            "body": "Let's discuss the project."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "completed"
    assert response.json["result"]["condition_matched"] is False
    assert response.json["result"]["action_executed"] is False


def test_execution_is_saved_in_database(client, app):
    user_id, workflow_id = create_test_workflow(app)
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "New invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200

    execution_id = response.json["execution_id"]

    with app.app_context():
        execution = db.session.get(
            WorkflowExecution,
            execution_id
        )

        assert execution is not None
        assert execution.workflow_id == workflow_id
        assert execution.status == "completed"
        assert execution.input_data["subject"] == "New invoice received"
        assert execution.result["action_executed"] is True
        assert execution.finished_at is not None


def test_get_workflow_execution_history(client, app):
    user_id, workflow_id = create_test_workflow(app)
    login_as(client, user_id)

    # Execute the workflow.
    client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process the invoice."
        }
    )

    # Retrieve execution history.
    response = client.get(
        f"/api/workflows/{workflow_id}/executions"
    )

    assert response.status_code == 200
    assert response.json["workflow_id"] == workflow_id
    assert response.json["workflow_name"] == "Invoice Workflow"
    assert response.json["count"] == 1

    execution = response.json["executions"][0]

    assert execution["status"] == "completed"
    assert execution["input_data"]["subject"] == "Invoice received"
    assert execution["result"]["action_executed"] is True
    assert execution["started_at"] is not None
    assert execution["finished_at"] is not None


def test_execute_workflow_without_login(client, app):
    _, workflow_id = create_test_workflow(app)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 401
    assert response.json["error"] == (
        "Authentication required. Please log in."
    )


def test_get_execution_history_without_login(client, app):
    _, workflow_id = create_test_workflow(app)

    response = client.get(
        f"/api/workflows/{workflow_id}/executions"
    )

    assert response.status_code == 401
    assert response.json["error"] == (
        "Authentication required. Please log in."
    )



def test_user_cannot_execute_another_users_workflow(client, app):
    _, workflow_id = create_test_workflow(
        app,
        email="first@example.com"
    )

    second_user = User(
        email="second@example.com",
        password_hash="test-password-hash"
    )

    with app.app_context():
        db.session.add(second_user)
        db.session.commit()
        second_user_id = second_user.id

    login_as(client, second_user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 404
    assert response.json["error"] == "Workflow not found."


def test_user_cannot_view_another_users_execution_history(client, app):
    _, workflow_id = create_test_workflow(
        app,
        email="first@example.com"
    )

    second_user = User(
        email="second@example.com",
        password_hash="test-password-hash"
    )

    with app.app_context():
        db.session.add(second_user)
        db.session.commit()
        second_user_id = second_user.id

    login_as(client, second_user_id)

    response = client.get(
        f"/api/workflows/{workflow_id}/executions"
    )

    assert response.status_code == 404
    assert response.json["error"] == "Workflow not found."


def test_execute_workflow_with_non_object_json(client, app):
    user_id, workflow_id = create_test_workflow(app)
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json=["invalid", "email"]
    )

    assert response.status_code == 400
    assert response.json["error"] == "A JSON object is required."


def test_execute_workflow_with_invalid_subject_type(client, app):
    user_id, workflow_id = create_test_workflow(app)
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": 123,
            "body": "Invoice received."
        }
    )

    assert response.status_code == 400
    assert response.json["error"] == (
        "subject and body must be strings."
    )


def test_execute_workflow_with_invalid_body_type(client, app):
    user_id, workflow_id = create_test_workflow(app)
    login_as(client, user_id)

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": ["invalid", "body"]
        }
    )

    assert response.status_code == 400
    assert response.json["error"] == (
        "subject and body must be strings."
    )

def test_execute_inactive_workflow(client, app):
    user_id, workflow_id = create_test_workflow(app)

    login_as(client, user_id)

    # Change the workflow status to inactive.
    with app.app_context():
        workflow = db.session.get(Workflow, workflow_id)
        workflow.status = "inactive"
        db.session.commit()

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "skipped"
    assert response.json["result"]["reason"] == "Workflow is inactive."
    assert response.json["result"]["action_executed"] is False



def test_execute_workflow_with_no_steps(client, app):
    user_id, workflow_id = create_test_workflow(app)

    login_as(client, user_id)

    # Remove all steps from the workflow.
    with app.app_context():
        WorkflowStep.query.filter_by(
            workflow_id=workflow_id
        ).delete()

        db.session.commit()

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "failed"
    assert response.json["result"]["reason"] == "Workflow has no steps."
    assert response.json["result"]["action_executed"] is False


def test_execute_workflow_with_unsupported_trigger(client, app):
    user_id, workflow_id = create_test_workflow(app)

    login_as(client, user_id)

    # Change the trigger to an unsupported event.
    with app.app_context():
        trigger = WorkflowStep.query.filter_by(
            workflow_id=workflow_id,
            step_type="trigger"
        ).first()

        trigger.configuration = {"event": "calendar_event"}
        db.session.commit()

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "skipped"
    assert response.json["result"]["reason"] == "Unsupported trigger event."
    assert response.json["result"]["action_executed"] is False


def test_execute_workflow_with_invalid_step_structure(client, app):
    user_id, workflow_id = create_test_workflow(app)

    login_as(client, user_id)

    # Remove the action step.
    with app.app_context():
        WorkflowStep.query.filter_by(
            workflow_id=workflow_id,
            step_type="action"
        ).delete()

        db.session.commit()

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "failed"
    assert response.json["result"]["reason"] == (
        "Workflow must contain a trigger, condition, and action in that order."
    )
    assert response.json["result"]["action_executed"] is False


def test_execute_workflow_with_unsupported_action(client, app):
    user_id, workflow_id = create_test_workflow(app)

    login_as(client, user_id)

    # Change the action to an unsupported type.
    with app.app_context():
        action = WorkflowStep.query.filter_by(
            workflow_id=workflow_id,
            step_type="action"
        ).first()

        action.configuration = {
            "type": "send_email",
            "message": "Sending an invoice notification."
        }

        db.session.commit()

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "failed"
    assert response.json["result"]["reason"] == "Unsupported action type."
    assert response.json["result"]["action_executed"] is False

def test_execute_workflow_with_invalid_condition_field(client, app):
    user_id, workflow_id = create_test_workflow(app)

    login_as(client, user_id)

    # Change the condition to an unsupported field.
    with app.app_context():
        condition = WorkflowStep.query.filter_by(
            workflow_id=workflow_id,
            step_type="condition"
        ).first()

        condition.configuration = {
            "field": "sender",
            "operator": "contains",
            "value": "invoice"
        }

        db.session.commit()

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "failed"
    assert response.json["result"]["reason"] == (
        "Condition field must be subject or body."
    )
    assert response.json["result"]["action_executed"] is False

def test_execute_workflow_with_unsupported_condition_operator(client, app):
    user_id, workflow_id = create_test_workflow(app)

    login_as(client, user_id)

    # Change the condition to an unsupported operator.
    with app.app_context():
        condition = WorkflowStep.query.filter_by(
            workflow_id=workflow_id,
            step_type="condition"
        ).first()

        condition.configuration = {
            "field": "subject",
            "operator": "equals",
            "value": "invoice"
        }

        db.session.commit()

    response = client.post(
        f"/api/workflows/{workflow_id}/execute",
        json={
            "subject": "Invoice received",
            "body": "Please process this invoice."
        }
    )

    assert response.status_code == 200
    assert response.json["result"]["status"] == "failed"
    assert response.json["result"]["reason"] == (
        "Unsupported condition configuration."
    )
    assert response.json["result"]["action_executed"] is False