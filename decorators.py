from functools import wraps

from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, logout_user


def _check_basic(role):
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.role != role:
        abort(403)
    if current_user.status != "Active":
        logout_user()
        flash("Your account is inactive.", "danger")
        return redirect(url_for("auth.login"))
    return None


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        blocked = _check_basic("Admin")
        return blocked if blocked else view(*args, **kwargs)
    return wrapper


def student_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        blocked = _check_basic("Student")
        return blocked if blocked else view(*args, **kwargs)
    return wrapper


def examiner_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        blocked = _check_basic("Examiner")
        if blocked:
            return blocked
        profile = current_user.examiner_profile
        if profile is None:
            abort(403)
        if profile.approval_status == "Pending":
            return render_template("examiner/pending.html")
        if profile.approval_status == "Rejected":
            logout_user()
            flash("Your examiner application was rejected.", "danger")
            return redirect(url_for("auth.login"))
        if profile.approval_status != "Approved":
            abort(403)
        return view(*args, **kwargs)
    return wrapper