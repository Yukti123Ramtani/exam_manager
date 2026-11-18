import os
from datetime import datetime, timezone

from flask import Flask, render_template
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

from database import db
from models import User

login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "exam_management_secret_key"),
        SQLALCHEMY_DATABASE_URI="sqlite:///exam_management.sqlite3",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from controllers.admin import admin
    from controllers.auth import auth
    from controllers.examiner import examiner
    from controllers.main import main
    from controllers.student import student

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(examiner)
    app.register_blueprint(student)

    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.now(timezone.utc).year,
            "portal_name": "examsmanager",
        }

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("404.html"), 404

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_default_admin():
    if not db.session.scalar(db.select(User).where(User.role == "Admin")):
        db.session.add(User(
            name="Exam Portal Admin",
            email="admin@examportal.com",
            password_hash=generate_password_hash("Admin@123"),
            contact_no="9876543210",
            role="Admin",
            status="Active",
        ))
        db.session.commit()
        print("Default administrator created successfully.")


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_default_admin()
    app.run(debug=True)
