
from flask import Blueprint

test = Blueprint("test", __name__)



@test.route("/api/health")
def health():

    return {
        "status": "ok",
        "services": "FlowForge API"
    }

