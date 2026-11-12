from flask import Blueprint, request, current_app, session


from app import db
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep


workflows_bp = Blueprint("workflows", __name__)


@workflows_bp.route("/api/workflows", methods=["GET"])
def get_workflows():
    # Get the logged-in user's ID.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # Return only workflows belonging to this user.
    workflows = Workflow.query.filter_by(
        user_id=user_id
    ).order_by(
        Workflow.created_at.desc()
    ).all()

    return {
        "workflows": [
            {
                "id": workflow.id,
                "user_id": workflow.user_id,
                "name": workflow.name,
                "description": workflow.description,
                "status": workflow.status,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat()
            }
            for workflow in workflows
        ]
    }, 200



@workflows_bp.route("/api/workflows", methods=["POST"])
def create_workflow():
    # 1. Only logged-in users can create workflows.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Read and validate the request body.
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {"error": "A JSON object is required."}, 400

    name = data.get("name")
    description = data.get("description", "")
    status = data.get("status", "active")

    if not isinstance(name, str) or not name.strip():
        return {"error": "A workflow name is required."}, 400

    if len(name.strip()) > 255:
        return {
            "error": "Workflow name must be 255 characters or fewer."
        }, 400

    if not isinstance(description, str):
        return {"error": "description must be a string."}, 400

    if status not in ("active", "inactive"):
        return {"error": "status must be active or inactive."}, 400

    # 3. Check whether the request includes workflow steps.
    steps_data = data.get("steps")

    if "steps" in data:

        # The workflow builder requires exactly three steps.
        if not isinstance(steps_data, list) or len(steps_data) != 3:
            return {
                "error": "A workflow must contain exactly three steps."
            }, 400

        expected_steps = ["trigger", "condition", "action"]

        # Validate every step before starting the database transaction.
        for index, step_data in enumerate(steps_data):

            if not isinstance(step_data, dict):
                return {
                    "error": f"Step {index + 1} must be a JSON object."
                }, 400

            step_type = step_data.get("step_type")
            step_order = step_data.get("step_order")
            configuration = step_data.get("configuration")

            if step_type != expected_steps[index]:
                return {
                    "error": (
                        f"Step {index + 1} must be "
                        f"a {expected_steps[index]} step."
                    )
                }, 400

            if (
                isinstance(step_order, bool)
                or not isinstance(step_order, int)
                or step_order != index + 1
            ):
                return {
                    "error": (
                        f"{step_type} must have step_order "
                        f"{index + 1}."
                    )
                }, 400

            if not isinstance(configuration, dict):
                return {
                    "error": (
                        f"Configuration for the {step_type} "
                        "step must be a JSON object."
                    )
                }, 400

    # 4. Prepare the workflow.
    workflow = Workflow(
        user_id=user_id,
        name=name.strip(),
        description=description.strip(),
        status=status
    )

    try:
        # 5. Add the workflow to the current transaction.
        db.session.add(workflow)

        # Flush sends the INSERT to the database and obtains
        # the workflow ID without committing the transaction.
        if "steps" in data:
            db.session.flush()

            # 6. Prepare all three workflow step records.
            workflow_steps = [
                WorkflowStep(
                    workflow_id=workflow.id,
                    step_type=step_data["step_type"],
                    step_order=step_data["step_order"],
                    configuration=step_data["configuration"]
                )
                for step_data in steps_data
            ]

            # Add all steps to the same transaction.
            db.session.add_all(workflow_steps)

        # 7. Commit the workflow and steps together.
        db.session.commit()

    except Exception:
        # If anything fails, undo all database changes.
        db.session.rollback()

        current_app.logger.exception(
            "Failed to create workflow and its steps"
        )

        return {
            "error": "Could not save the workflow and its steps."
        }, 500

    # 8. Return the successfully created workflow.
    return {
        "message": "Workflow created successfully.",
        "workflow": {
            "id": workflow.id,
            "user_id": workflow.user_id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat()
        }
    }, 201

@workflows_bp.route(
    "/api/workflows/<int:workflow_id>",
    methods=["PUT"]
)
def update_workflow(workflow_id):

    # 1. Check whether the user is logged in.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Find the workflow belonging to this user.
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        user_id=user_id
    ).first()

    if workflow is None:
        return {
            "error": "Workflow not found."
        }, 404

    # 3. Read and validate the request body.
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {
            "error": "A JSON object is required."
        }, 400

    name = data.get("name")
    description = data.get("description")

    # 4. Validate the workflow name.
    if not isinstance(name, str) or not name.strip():
        return {
            "error": "A workflow name is required."
        }, 400

    if len(name.strip()) > 255:
        return {
            "error": "Workflow name must be 255 characters or fewer."
        }, 400

    # 5. Validate the description.
    if not isinstance(description, str):
        return {
            "error": "description must be a string."
        }, 400

    try:
        # 6. Update the workflow fields.
        workflow.name = name.strip()
        workflow.description = description.strip()

        # 7. Save the changes.
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to update workflow"
        )

        return {
            "error": "Could not update the workflow."
        }, 500

    # 8. Return the updated workflow.
    return {
        "message": "Workflow updated successfully.",
        "workflow": {
            "id": workflow.id,
            "user_id": workflow.user_id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status,
            "updated_at": workflow.updated_at.isoformat()
        }
    }, 200



@workflows_bp.route(
    "/api/workflows/<int:workflow_id>/status",
    methods=["PATCH"]
)
def update_workflow_status(workflow_id):

    # 1. Check authentication.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Find the workflow belonging to this user.
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        user_id=user_id
    ).first()

    if workflow is None:
        return {
            "error": "Workflow not found."
        }, 404

    # 3. Read the JSON request.
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {
            "error": "A JSON object is required."
        }, 400

    new_status = data.get("status")

    # 4. Validate the requested status.
    if not isinstance(new_status, str) or new_status not in (
        "active",
        "inactive"
    ):
        return {
            "error": "Status must be either active or inactive."
        }, 400

    try:
        # 5. Update and save the status.
        workflow.status = new_status
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to update workflow status"
        )

        return {
            "error": "Could not update workflow status."
        }, 500

    # 6. Return the updated status.
    return {
        "message": "Workflow status updated successfully.",
        "workflow_id": workflow.id,
        "status": workflow.status
    }, 200


@workflows_bp.route(
    "/api/workflows/<int:workflow_id>",
    methods=["DELETE"]
)
def delete_workflow(workflow_id):

    # 1. Check whether the user is logged in.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

    # 2. Find the workflow belonging to the logged-in user.
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        user_id=user_id
    ).first()

    # 3. Return 404 if the workflow doesn't exist
    # or belongs to another user.
    if workflow is None:
        return {
            "error": "Workflow not found."
        }, 404

    try:
        # 4. Delete the workflow.
        db.session.delete(workflow)

        # 5. Commit the deletion.
        # SQLAlchemy also deletes associated steps
        # and executions through cascade relationships.
        db.session.commit()

    except Exception:
        # 6. Undo the transaction if deletion fails.
        db.session.rollback()

        current_app.logger.exception(
            "Failed to delete workflow"
        )

        return {
            "error": "Could not delete the workflow."
        }, 500

    # 7. Confirm successful deletion.
    return {
        "message": "Workflow deleted successfully.",
        "workflow_id": workflow_id
    }, 200
