from app import create_app, db
from app.models.workflow import Workflow


app = create_app()

with app.app_context():
    print("DATABASE:", db.engine.url.database)
    print("DATABASE HOST:", db.engine.url.host)

    workflows = Workflow.query.all()

    print("WORKFLOWS IN FLASK DATABASE:")

    for workflow in workflows:
        print(
            workflow.id,
            workflow.user_id,
            workflow.name
        )

print("\nREGISTERED WORKFLOW ROUTES:")

for rule in app.url_map.iter_rules():
    if "steps" in rule.rule:
        print(rule, rule.methods)

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)