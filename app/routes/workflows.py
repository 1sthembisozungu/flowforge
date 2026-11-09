from flask import Blueprint, request, current_app, session

from app import db
from app.models.workflow import Workflow


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
    # Only logged-in users can create workflows.
    user_id = session.get("user_id")

    if user_id is None:
        return {
            "error": "Authentication required. Please log in."
        }, 401

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

    # Assign ownership using the authenticated session.
    workflow = Workflow(
        user_id=user_id,
        name=name.strip(),
        description=description.strip(),
        status=status
    )

    try:
        db.session.add(workflow)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to create workflow")
        return {"error": "Could not save the workflow."}, 500

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
