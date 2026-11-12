
from datetime import datetime, timezone

from app import db


class WorkflowStep(db.Model):
    __tablename__ = "workflow_steps"

    id = db.Column(db.Integer, primary_key=True)

    workflow_id = db.Column(
        db.Integer,
        db.ForeignKey("workflows.id"),
        nullable=False
    )

    step_type = db.Column(db.String(20), nullable=False)

    step_order = db.Column(db.Integer, nullable=False)

    configuration = db.Column(db.JSON, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship back to the parent workflow.
    workflow = db.relationship(
        "Workflow",
        back_populates="steps"
    )
