
from datetime import datetime, timezone

from flask import Blueprint, current_app, request, session

from app import db
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.services.workflow_engine import execute_workflow


executions_bp = Blueprint("executions", __name__)


@executions_bp.route(
    "/api/workflows/<int:workflow_id>/execute",
    methods=["POST"]
)
def execute_workflow_route(workflow_id):
    # 1. Require an authenticated user.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Find the workflow and verify ownership.
    workflow = db.session.get(Workflow, workflow_id)

    if workflow is None or workflow.user_id != user_id:
        return {"error": "Workflow not found."}, 404

    # 3. Read and validate the simulated email.
    email = request.get_json(silent=True)

    if not isinstance(email, dict):
        return {"error": "A JSON object is required."}, 400

    subject = email.get("subject", "")
    body = email.get("body", "")

    if not isinstance(subject, str) or not isinstance(body, str):
        return {"error": "subject and body must be strings."}, 400

    # 4. Create an execution-history record before running.
    execution = WorkflowExecution(
        workflow_id=workflow.id,
        input_data={
            "subject": subject,
            "body": body
        },
        status="running"
    )

    try:
        db.session.add(execution)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Could not create workflow execution record."
        )
        return {"error": "Could not start workflow execution."}, 500

    execution_id = execution.id

    # 5. Run the workflow engine and save the outcome.
    try:
        result = execute_workflow(
            workflow,
            {
                "subject": subject,
                "body": body
            }
        )

        execution.status = result.get("status", "failed")
        execution.result = result
        execution.finished_at = datetime.now(timezone.utc)

        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception("Workflow execution failed.")

        execution = db.session.get(
            WorkflowExecution,
            execution_id
        )

        execution.status = "failed"
        execution.result = {
            "error": "An unexpected error occurred during execution."
        }
        execution.finished_at = datetime.now(timezone.utc)

        db.session.commit()

        return {
            "workflow_id": workflow.id,
            "execution_id": execution_id,
            "status": "failed",
            "error": "Workflow execution failed."
        }, 500

    # 6. Return the saved result.
    return {
        "workflow_id": workflow.id,
        "workflow_name": workflow.name,
        "execution_id": execution.id,
        "result": execution.result
    }, 200


@executions_bp.route(
    "/api/workflows/<int:workflow_id>/executions",
    methods=["GET"]
)
def get_workflow_executions(workflow_id):
    # 1. Require an authenticated user.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Find the workflow and verify ownership.
    workflow = db.session.get(Workflow, workflow_id)

    if workflow is None or workflow.user_id != user_id:
        return {"error": "Workflow not found."}, 404

    # 3. Retrieve the 50 most recent executions for this workflow.
    executions = WorkflowExecution.query.filter_by(
        workflow_id=workflow.id
    ).order_by(
        WorkflowExecution.started_at.desc()
    ).limit(50).all()

    # 4. Convert database records into JSON-friendly data.
    execution_history = []

    for execution in executions:
        execution_history.append({
            "id": execution.id,
            "workflow_id": execution.workflow_id,
            "status": execution.status,
            "input_data": execution.input_data,
            "result": execution.result,
            "started_at": (
                execution.started_at.isoformat()
                if execution.started_at else None
            ),
            "finished_at": (
                execution.finished_at.isoformat()
                if execution.finished_at else None
            )
        })

    # 5. Return the execution history.
    return {
        "workflow_id": workflow.id,
        "workflow_name": workflow.name,
        "count": len(execution_history),
        "executions": execution_history
    }, 200
