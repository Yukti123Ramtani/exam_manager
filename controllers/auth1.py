import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for # type: ignore
from flask_login import current_user, login_required, login_user, logout_user # type: ignore
from werkzeug.security import check_password_hash, generate_password_hash # type: ignore

from database import db
from models import ExaminerProfile, User

auth = Blueprint("auth", __name__, url_prefix="/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_contact(number):
    return number.isdigit() and len(number) == 10


def redirect_user_by_role(user):
    """Send an authenticated user to their own dashboard."""
    if user.role == "Admin":
        return redirect(url_for("admin.dashboard"))
    if user.role == "Student":
        return redirect(url_for("student.dashboard"))
    if user.role == "Examiner":
        profile = user.examiner_profile
        if profile is None:
            logout_user()
            abort(403)
        if profile.approval_status == "Pending":
            return render_template("examiner/pending.html")
        if profile.approval_status == "Approved":
            return redirect(url_for("examiner.dashboard"))
        logout_user()
        flash("Your examiner application was rejected.", "danger")
        return redirect(url_for("auth.login"))
    logout_user()
    abort(403)


def redirect_authenticated():
    if current_user.is_authenticated:
        return redirect_user_by_role(current_user)
    return None


def get_form_data(form, is_examiner):
    data = {
        "name": form.get("name", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "password": form.get("password", ""),
        "confirm_password": form.get("confirm_password", ""),
        "contact_no": form.get("contact_no", "").strip(),
    }
    if is_examiner:
        data["qualification"] = form.get("qualification", "").strip()
        data["specialization"] = form.get("specialization", "").strip()
        data["experience"] = form.get("experience", "").strip()
    return data


def validate(data, is_examiner):
    if not data["name"]:
        return "Name is required."
    if not EMAIL_RE.match(data["email"]):
        return "Enter a valid email address."
    if len(data["password"]) < 8:
        return "Password must be at least 8 characters."
    if data["password"] != data["confirm_password"]:
        return "Passwords do not match."
    if not is_valid_contact(data["contact_no"]):
        return "Contact number must contain exactly 10 digits."
    if is_examiner:
        if not data["qualification"]:
            return "Qualification is required."
        if data["experience"] and not data["experience"].isdigit():
            return "Experience must be a whole number of years."
    if db.session.scalar(db.select(User).where(User.email == data["email"])):
        return "An account with this email already exists."
    return None


def create_user(data, role):
    user = User(
        name=data["name"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        contact_no=data["contact_no"],
        role=role,
        status="Active",
    )
    db.session.add(user)
    if role == "Examiner":
        db.session.flush()
        db.session.add(ExaminerProfile(
            user_id=user.id,
            qualification=data["qualification"],
            specialization=data.get("specialization"),
            experience=int(data["experience"]) if data.get("experience") else None,
            approval_status="Pending",
        ))
    return user


def register_user(role, template):
    """Shared registration view. Only Student / Examiner are ever passed in."""
    existing = redirect_authenticated()
    if existing:
        return existing
    if request.method == "GET":
        return render_template(template)

    is_examiner = role == "Examiner"
    data = get_form_data(request.form, is_examiner)
    error = validate(data, is_examiner)
    if error:
        flash(error, "danger")
        return render_template(template, form=data)
    try:
        create_user(data, role)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Registration failed.", "danger")
        return render_template(template, form=data)

    flash("Account created. Admin approval is required before you can log in."
          if is_examiner else "Student account created successfully.", "success")
    return redirect(url_for("auth.login"))


@auth.route("/register/student", methods=["GET", "POST"])
def register_student():
    return register_user("Student", "auth/register_student.html")


@auth.route("/register/examiner", methods=["GET", "POST"])
def register_examiner():
    return register_user("Examiner", "auth/register_examiner.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    existing = redirect_authenticated()
    if existing:
        return existing
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = db.session.scalar(db.select(User).where(User.email == email))

    if not user or not check_password_hash(user.password_hash, password):
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html")
    if user.status != "Active":
        flash("Your account is inactive.", "danger")
        return render_template("auth/login.html")

    if user.role == "Examiner":
        profile = user.examiner_profile
        if profile is None:
            flash("Your examiner profile was not found.", "danger")
            return render_template("auth/login.html")
        if profile.approval_status == "Pending":
            return render_template("examiner/pending.html")
        if profile.approval_status != "Approved":
            flash("Your examiner application was rejected.", "danger")
            return render_template("auth/login.html")

    login_user(user)
    return redirect_user_by_role(user)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))