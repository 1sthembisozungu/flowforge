import os # allow you to interact with computer's operating system

from flask  import Flask #create flask web application
from flask_sqlalchemy import SQLAlchemy #allows you to work with databases using Python objects instead of raw SQL.
from dotenv import load_dotenv #loads environment variables from a .env file into your system environment so you can access them with os.getenv.
#from app.routes.test import test 

db = SQLAlchemy()

def create_app(test_config=None): 
    #instead of creating the app globally, you create it inside a function so you can configure it flexibly

    load_dotenv() # loads variabled from the .env file into environment

    app = Flask(__name__) #creates flask applications instance

    # __name__ tells Flask where to look for resources (like templates and static files).

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") # set up app's secret key from the environment variable

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL"
    ) #set up db connection string from the environment variable
    
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False 
    #Disables SQLAlchemy’s event system that tracks object changes.

    if test_config is not None:
        app.config.update(test_config)

    # It’s not needed in most cases and consumes extra memory, so it’s best practice to set it to False.


    db.init_app(app) #links the db object to the flask app and it makes the database available inside the app context

    from app.models.user import User 
    from app.routes.test import test
    from app.models.workflow import Workflow
    from app.routes.workflows import workflows_bp
    from app.models.workflow_step import WorkflowStep 
    from app.routes.workflow_steps import workflow_steps_bp 
    from app.routes.executions import executions_bp
    from app.models.workflow_execution import WorkflowExecution
    from app.routes.dashboard import dashboard_bp
    from app.routes.auth import auth_bp


    app.register_blueprint(test)
    app.register_blueprint(workflows_bp)
    app.register_blueprint(workflow_steps_bp) 
    app.register_blueprint(executions_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)


    #adding a new blueprint connects the new endpoint to your application

    return app #returns the fully configured flask app instance
