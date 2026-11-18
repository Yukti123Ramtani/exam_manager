from flask import Blueprint, render_template
from flask_login import current_user

from controllers.auth import redirect_user_by_role

main = Blueprint("main", __name__)


@main.route("/")
def home():
    """Display the exam management platform homepage."""
    if current_user.is_authenticated:
        return redirect_user_by_role(current_user)
    return render_template("exam_management_home.html")