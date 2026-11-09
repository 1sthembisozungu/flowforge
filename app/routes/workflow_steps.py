
from flask import Blueprint, request, session

from app import db
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


workflow_steps_bp = Blueprint("workflow_steps", __name__)


@workflow_steps_bp.route(
    "/api/workflows/<int:workflow_id>/steps",
    methods=["POST"]
)
def create_workflow_step(workflow_id):
    # 1. Check whether the user is logged in.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Find the workflow.
    workflow = db.session.get(Workflow, workflow_id)

    if workflow is None or workflow.user_id != user_id:
        return {"error": "Workflow not found."}, 404

    # 3. Read and validate the request body.
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {"error": "A JSON object is required."}, 400

    step_type = data.get("step_type")
    step_order = data.get("step_order")
    configuration = data.get("configuration")

    if step_type not in ("trigger", "condition", "action"):
        return {
            "error": "step_type must be trigger, condition, or action."
        }, 400

    if (
        isinstance(step_order, bool)
        or not isinstance(step_order, int)
        or step_order < 1
    ):
        return {
            "error": "step_order must be a positive integer."
        }, 400

    if not isinstance(configuration, dict):
        return {
            "error": "configuration must be a JSON object."
        }, 400

    # 4. Prevent duplicate step positions in the workflow.
    existing_step = WorkflowStep.query.filter_by(
        workflow_id=workflow_id,
        step_order=step_order
    ).first()

    if existing_step is not None:
        return {
            "error": "This workflow already has a step at that position."
        }, 409

    # 5. Create and save the workflow step.
    step = WorkflowStep(
        workflow_id=workflow_id,
        step_type=step_type,
        step_order=step_order,
        configuration=configuration
    )

    try:
        db.session.add(step)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # 6. Return the newly created step.
    return {
        "message": "Workflow step created successfully.",
        "step": {
            "id": step.id,
            "workflow_id": step.workflow_id,
            "step_type": step.step_type,
            "step_order": step.step_order,
            "configuration": step.configuration
        }
    }, 201



@workflow_steps_bp.route(
    "/api/workflows/<int:workflow_id>/steps",
    methods=["GET"]
)
def get_workflow_steps(workflow_id):
    # 1. Check whether the user is logged in.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Verify that the workflow belongs to the user.
    workflow = db.session.get(Workflow, workflow_id)

    if workflow is None or workflow.user_id != user_id:
        return {"error": "Workflow not found."}, 404

    print("Logged-in user ID:", user_id)
    print("Requested workflow ID:", workflow_id)

    # 3. Retrieve the workflow steps in execution order.
    steps = WorkflowStep.query.filter_by(
        workflow_id=workflow_id
    ).order_by(
        WorkflowStep.step_order.asc()
    ).all()

    # 4. Return the saved steps.
    return {
        "steps": [
            {
                "id": step.id,
                "workflow_id": step.workflow_id,
                "step_type": step.step_type,
                "step_order": step.step_order,
                "configuration": step.configuration
            }
            for step in steps
        ]
    }, 200

