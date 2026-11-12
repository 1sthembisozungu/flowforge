
from datetime import datetime, timezone

from app import db


class WorkflowExecution(db.Model): 
    #defines the database model
    __tablename__ = "workflow_executions"

    id = db.Column(db.Integer, primary_key=True)

    workflow_id = db.Column(
        db.Integer,
        db.ForeignKey("workflows.id"),
        nullable=False
    )

    input_data = db.Column(db.JSON, nullable=False)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="running"
    )

    result = db.Column(db.JSON, nullable=True)

    started_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    finished_at = db.Column(
        db.DateTime,
        nullable=True
    )

    workflow = db.relationship(
            "Workflow",
            back_populates="executions"
    )
