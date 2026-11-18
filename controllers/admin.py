from datetime import datetime

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from decorators import admin_required
from helpers import occupied_seats, parse_dt, sync_slot
from models import (Booking, Course, Examination, ExaminerProfile,
                    ExamSlot, User)

admin = Blueprint("admin", __name__, url_prefix="/admin")

EXAM_TYPES = ("Midterm", "Final", "Quiz", "Practical", "Viva")

# admin-controlled lifecycle transitions: action -> (required, next, message)
EXAM_TRANSITIONS = {
    "open_slot_creation": ("Draft", "Slot Creation",
                           "Slot creation opened for the assigned examiner."),
    "open_booking": ("Slot Creation", "Bookings Open",
                     "Student booking opened for this examination."),
    "close_booking": ("Bookings Open", "Bookings Closed",
                      "Student booking closed for this examination."),
}


def _approved_examiners():
    return db.session.scalars(
        db.select(User)
        .join(ExaminerProfile, ExaminerProfile.user_id == User.id)
        .where(User.role == "Examiner",
               ExaminerProfile.approval_status == "Approved",
               User.status == "Active")
        .order_by(User.name.asc())
    ).all()


# ------------------------------------------------------------------ dashboard
@admin.route("/dashboard")
@admin_required
def dashboard():
    stats = {}
    for key, model, condition in (
        ("total_students", User, User.role == "Student"),
        ("total_examiners", User, User.role == "Examiner"),
        ("total_courses", Course, None),
        ("total_examinations", Examination, None),
        ("total_slots", ExamSlot, None),
        ("total_bookings", Booking, None),
    ):
        stmt = db.select(func.count(model.id))
        if condition is not None:
            stmt = stmt.where(condition)
        stats[key] = db.session.scalar(stmt) or 0

    stats["pending_examiners"] = db.session.scalar(
        db.select(func.count(ExaminerProfile.user_id))
        .where(ExaminerProfile.approval_status == "Pending")) or 0

    recent_bookings = db.session.scalars(
        db.select(Booking)
        .order_by(Booking.booked_at.desc())
        .limit(5)
    ).all()
    return render_template("admin/dashboard.html", stats=stats,
                           recent_bookings=recent_bookings)


# ------------------------------------------------------------------- courses
@admin.route("/courses")
@admin_required
def courses():
    q = request.args.get("q", "").strip()
    query = db.select(Course)
    if q:
        conditions = [Course.name.ilike(f"%{q}%"), Course.code.ilike(f"%{q}%")]
        if q.isdigit():
            conditions.append(Course.id == int(q))
        query = query.where(or_(*conditions))
    course_list = db.session.scalars(query.order_by(Course.name.asc())).all()
    return render_template("admin/courses.html", course_list=course_list, q=q)


@admin.route("/courses/add", methods=["GET", "POST"])
@admin_required
def add_course():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        description = request.form.get("description", "").strip()
        if not (name and code):
            flash("Course name and code are required.", "danger")
        elif db.session.scalar(db.select(Course).where(Course.code == code)):
            flash("A course with this code already exists.", "danger")
        else:
            try:
                db.session.add(Course(name=name, code=code,
                                      description=description or None))
                db.session.commit()
                flash("Course created successfully.", "success")
                return redirect(url_for("admin.courses"))
            except Exception:
                db.session.rollback()
                flash("Unable to create the course.", "danger")
    return render_template("admin/course_form.html", course=None)


@admin.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_course(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        flash("Course not found.", "danger")
        return redirect(url_for("admin.courses"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        if not name or not code:
            flash("Course name and code are required.", "danger")
        else:
            duplicate = db.session.scalar(
                db.select(Course).where(Course.code == code,
                                        Course.id != course.id))
            if duplicate:
                flash("Another course already uses this code.", "danger")
            else:
                try:
                    course.name = name
                    course.code = code
                    course.description = (request.form.get("description", "")
                                          .strip() or None)
                    db.session.commit()
                    flash("Course updated successfully.", "success")
                    return redirect(url_for("admin.courses"))
                except Exception:
                    db.session.rollback()
                    flash("Unable to update the course.", "danger")
    return render_template("admin/course_form.html", course=course)


@admin.route("/courses/<int:course_id>/delete", methods=["POST"])
@admin_required
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if course is None:
        flash("Course not found.", "danger")
        return redirect(url_for("admin.courses"))
    if course.examinations:
        flash("Courses with examinations cannot be deleted.", "danger")
    else:
        try:
            db.session.delete(course)
            db.session.commit()
            flash("Course deleted successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Unable to delete the course.", "danger")
    return redirect(url_for("admin.courses"))


# -------------------------------------------------------------- examinations
@admin.route("/examinations")
@admin_required
def examinations():
    q = request.args.get("q", "").strip()
    query = db.select(Examination).join(
        Course, Examination.course_id == Course.id)
    if q:
        conditions = [Examination.name.ilike(f"%{q}%"),
                      Course.name.ilike(f"%{q}%"),
                      Course.code.ilike(f"%{q}%"),
                      Examination.status.ilike(f"%{q}%")]
        if q.isdigit():
            conditions.append(Examination.id == int(q))
        query = query.where(or_(*conditions))
    exam_list = db.session.scalars(
        query.order_by(Examination.examination_date.asc())).all()
    return render_template("admin/examinations.html", exam_list=exam_list,
                           examiner_list=_approved_examiners(), q=q)


@admin.route("/examinations/add", methods=["GET", "POST"])
@admin_required
def add_examination():
    if request.method == "POST":
        data = _exam_form_data()
        error = _validate_exam(data)
        if error:
            flash(error, "danger")
        else:
            try:
                db.session.add(Examination(
                    course_id=int(data["course_id"]),
                    examiner_id=int(data["examiner_id"])
                    if data["examiner_id"] else None,
                    name=data["name"],
                    description=data["description"] or None,
                    examination_type=data["examination_type"],
                    duration=int(data["duration"]),
                    examination_date=data["examination_date"],
                ))
                db.session.commit()
                flash("Examination created successfully.", "success")
                return redirect(url_for("admin.examinations"))
            except Exception:
                db.session.rollback()
                flash("Unable to create the examination.", "danger")
    return render_template("admin/examination_form.html", exam=None,
                           course_list=_course_list(),
                           examiner_list=_approved_examiners(),
                           exam_types=EXAM_TYPES)


@admin.route("/examinations/<int:exam_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_examination(exam_id):
    exam = db.session.get(Examination, exam_id)
    if exam is None:
        flash("Examination not found.", "danger")
        return redirect(url_for("admin.examinations"))

    if request.method == "POST":
        data = _exam_form_data()
        error = _validate_exam(data)
        if error:
            flash(error, "danger")
        else:
            try:
                exam.course_id = int(data["course_id"])
                exam.examiner_id = (int(data["examiner_id"])
                                    if data["examiner_id"] else None)
                exam.name = data["name"]
                exam.description = data["description"] or None
                exam.examination_type = data["examination_type"]
                exam.duration = int(data["duration"])
                exam.examination_date = data["examination_date"]
                if exam.examiner_id:
                    for slot in exam.slots:
                        slot.examiner_id = exam.examiner_id
                db.session.commit()
                flash("Examination updated successfully.", "success")
                return redirect(url_for("admin.examinations"))
            except Exception:
                db.session.rollback()
                flash("Unable to update the examination.", "danger")
    return render_template("admin/examination_form.html", exam=exam,
                           course_list=_course_list(),
                           examiner_list=_approved_examiners(),
                           exam_types=EXAM_TYPES)


@admin.route("/examinations/<int:exam_id>/assign-examiner", methods=["POST"])
@admin_required
def assign_examiner(exam_id):
    exam = db.session.get(Examination, exam_id)
    if exam is None:
        abort(404)
    examiner_id = request.form.get("examiner_id", type=int)
    examiner = db.session.get(User, examiner_id) if examiner_id else None
    if examiner is None or examiner.role != "Examiner":
        flash("Please choose a valid examiner.", "danger")
        return redirect(url_for("admin.examinations"))
    try:
        exam.examiner_id = examiner.id
        for slot in exam.slots:
            slot.examiner_id = examiner.id
        db.session.commit()
        flash(f"{examiner.name} assigned to {exam.name}.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to assign the examiner.", "danger")
    return redirect(url_for("admin.examinations"))


@admin.route("/examinations/<int:exam_id>/status", methods=["POST"])
@admin_required
def exam_status(exam_id):
    exam = db.session.get(Examination, exam_id)
    if exam is None:
        abort(404)
    action = request.form.get("action", "")
    if action not in EXAM_TRANSITIONS:
        abort(400)
    required, next_status, message = EXAM_TRANSITIONS[action]
    if exam.status != required:
        flash(f"This action needs the examination to be in '{required}' state.",
              "warning")
        return redirect(url_for("admin.examinations"))
    if action == "open_booking" and exam.student_booking_open is None:
        exam.student_booking_open = datetime.now()
    if action == "close_booking" and exam.student_booking_close is None:
        exam.student_booking_close = datetime.now()
    exam.status = next_status
    db.session.commit()
    flash(message, "success")
    return redirect(url_for("admin.examinations"))


@admin.route("/examinations/<int:exam_id>/timeline", methods=["GET", "POST"])
@admin_required
def timeline(exam_id):
    exam = db.session.get(Examination, exam_id)
    if exam is None:
        flash("Examination not found.", "danger")
        return redirect(url_for("admin.examinations"))

    if request.method == "POST":
        fields = ("exam_start", "exam_end", "examiner_slot_open",
                  "examiner_slot_close", "student_booking_open",
                  "student_booking_close")
        try:
            for field in fields:
                setattr(exam, field, parse_dt(request.form.get(field)))
            pairs = (("examiner_slot_open", "examiner_slot_close"),
                     ("student_booking_open", "student_booking_close"),
                     ("exam_start", "exam_end"))
            for start_field, end_field in pairs:
                start, end = getattr(exam, start_field), getattr(exam, end_field)
                if start and end and start > end:
                    raise ValueError
            db.session.commit()
            flash("Examination timeline configured successfully.", "success")
            return redirect(url_for("admin.examinations"))
        except (TypeError, ValueError):
            db.session.rollback()
            flash("Invalid timeline information. Check that open times precede "
                  "close times.", "danger")
    return render_template("admin/timeline.html", examination=exam)


def _course_list():
    return db.session.scalars(db.select(Course).order_by(Course.name)).all()


def _exam_form_data():
    return {
        "course_id": request.form.get("course_id", "").strip(),
        "examiner_id": request.form.get("examiner_id", "").strip(),
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "examination_type": request.form.get("examination_type", "").strip(),
        "duration": request.form.get("duration", "").strip(),
        "examination_date": request.form.get("examination_date", "").strip(),
    }


def _validate_exam(data):
    if not data["course_id"] or not data["course_id"].isdigit():
        return "Select the course for this examination."
    if not data["name"]:
        return "Examination name is required."
    if data["examination_type"] not in EXAM_TYPES:
        return "Select a valid examination type."
    if not data["duration"].isdigit() or not (1 <= int(data["duration"]) <= 600):
        return "Duration must be between 1 and 600 minutes."
    try:
        from datetime import date as date_type
        data["examination_date"] = date_type.fromisoformat(
            data["examination_date"])
    except ValueError:
        return "Enter a valid examination date."
    return None


# ---------------------------------------------------------------- examiners
@admin.route("/examiners")
@admin_required
def examiners():
    q = request.args.get("q", "").strip()
    statement = (
        db.select(User)
        .join(ExaminerProfile, ExaminerProfile.user_id == User.id)
        .where(User.role == "Examiner")
    )
    if q:
        conditions = [User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"),
                      ExaminerProfile.approval_status.ilike(f"%{q}%")]
        if q.isdigit():
            conditions.append(User.id == int(q))
        statement = statement.where(or_(*conditions))
    examiner_list = db.session.scalars(
        statement.order_by(User.name.asc())).all()
    return render_template("admin/examiners.html",
                           examiner_list=examiner_list, q=q)


def _examiner_or_redirect(user_id, message="Examiner not found."):
    examiner = db.session.scalar(
        db.select(User).where(User.id == user_id, User.role == "Examiner"))
    if examiner is None or examiner.examiner_profile is None:
        flash(message, "danger")
        return None, redirect(url_for("admin.examiners"))
    return examiner, None


@admin.route("/examiners/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_examiner(user_id):
    examiner, redirect_response = _examiner_or_redirect(user_id)
    if redirect_response:
        return redirect_response
    examiner.examiner_profile.approval_status = "Approved"
    examiner.status = "Active"
    db.session.commit()
    flash(f"{examiner.name} approved as examiner.", "success")
    return redirect(url_for("admin.examiners"))


@admin.route("/examiners/<int:user_id>/reject", methods=["POST"])
@admin_required
def reject_examiner(user_id):
    examiner, redirect_response = _examiner_or_redirect(user_id)
    if redirect_response:
        return redirect_response
    examiner.examiner_profile.approval_status = "Rejected"
    db.session.commit()
    flash(f"{examiner.name}'s application was rejected.", "warning")
    return redirect(url_for("admin.examiners"))


@admin.route("/examiners/<int:user_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_examiner(user_id):
    examiner, redirect_response = _examiner_or_redirect(user_id)
    if redirect_response:
        return redirect_response
    examiner.status = "Inactive"
    db.session.commit()
    flash(f"{examiner.name} has been deactivated.", "warning")
    return redirect(url_for("admin.examiners"))


@admin.route("/examiners/<int:user_id>/activate", methods=["POST"])
@admin_required
def activate_examiner(user_id):
    examiner, redirect_response = _examiner_or_redirect(user_id)
    if redirect_response:
        return redirect_response
    examiner.status = "Active"
    db.session.commit()
    flash(f"{examiner.name} has been activated.", "success")
    return redirect(url_for("admin.examiners"))


# ------------------------------------------------------------------ students
@admin.route("/students")
@admin_required
def students():
    q = request.args.get("q", "").strip()
    conditions = [User.role == "Student"]
    if q:
        or_matches = [User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")]
        if q.isdigit():
            or_matches.append(User.id == int(q))
        conditions.append(or_(*or_matches))
    student_list = db.session.scalars(
        db.select(User).where(*conditions).order_by(User.name.asc())).all()
    return render_template("admin/students.html",
                           student_list=student_list, q=q)


@admin.route("/students/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_student(user_id):
    student = db.session.scalar(
        db.select(User).where(User.id == user_id, User.role == "Student"))
    if student is None:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.students"))
    student.status = "Inactive" if student.status == "Active" else "Active"
    db.session.commit()
    flash(f"{student.name} is now {student.status.lower()}.",
          "success" if student.status == "Active" else "warning")
    return redirect(url_for("admin.students"))


# -------------------------------------------------------------------- slots
@admin.route("/slots")
@admin_required
def slots():
    q = request.args.get("q", "").strip()
    query = db.select(ExamSlot).join(
        Examination, ExamSlot.examination_id == Examination.id)
    if q:
        conditions = [Examination.name.ilike(f"%{q}%")]
        if q.isdigit():
            conditions.append(ExamSlot.id == int(q))
        query = query.where(or_(*conditions))
    slot_list = db.session.scalars(
        query.order_by(ExamSlot.date.asc(), ExamSlot.start_time.asc())).all()
    return render_template("admin/slots.html", slot_list=slot_list, q=q)


# ----------------------------------------------------------------- bookings
@admin.route("/bookings")
@admin_required
def bookings():
    q = request.args.get("q", "").strip()
    query = (db.select(Booking)
             .join(User, User.id == Booking.student_id)
             .join(ExamSlot, Booking.slot_id == ExamSlot.id)
             .join(Examination, ExamSlot.examination_id == Examination.id))
    if q:
        conditions = [User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"),
                      Examination.name.ilike(f"%{q}%"),
                      Booking.status.ilike(f"%{q}%")]
        if q.isdigit():
            conditions.append(Booking.id == int(q))
        query = query.where(or_(*conditions))
    booking_list = db.session.scalars(
        query.order_by(Booking.booked_at.desc())).all()
    return render_template("admin/bookings.html",
                           booking_list=booking_list, q=q,
                           examiner_list=_approved_examiners())


@admin.route("/bookings/<int:booking_id>/reschedule", methods=["POST"])
@admin_required
def reschedule_booking(booking_id):
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("admin.bookings"))

    new_slot = db.session.get(ExamSlot,
                              request.form.get("slot_id", type=int))
    old_slot = booking.slot
    if new_slot is None:
        flash("Please select a new examination slot.", "danger")
        return redirect(url_for("admin.bookings"))
    if new_slot.id == old_slot.id:
        flash("The booking is already on this slot.", "warning")
        return redirect(url_for("admin.bookings"))
    if new_slot.examination_id != old_slot.examination_id:
        flash("The new slot must belong to the same examination.", "danger")
        return redirect(url_for("admin.bookings"))
    if (new_slot.status != "Available" or new_slot.available_seats <= 0
            or occupied_seats(new_slot.id) >= new_slot.maximum_student_capacity):
        flash("The selected slot is full or unavailable.", "danger")
        return redirect(url_for("admin.bookings"))

    try:
        booking.slot_id = new_slot.id
        sync_slot(new_slot)
        sync_slot(old_slot)
        db.session.commit()
        flash("Examination booking rescheduled successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to reschedule the booking.", "danger")
    return redirect(url_for("admin.bookings"))


@admin.route("/bookings/<int:booking_id>/change-examiner", methods=["POST"])
@admin_required
def change_examiner(booking_id):
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("admin.bookings"))

    examiner_id = request.form.get("examiner_id", type=int)
    approved = db.session.scalar(
        db.select(User)
        .join(ExaminerProfile, ExaminerProfile.user_id == User.id)
        .where(User.id == examiner_id,
               User.role == "Examiner",
               ExaminerProfile.approval_status == "Approved",
               User.status == "Active"))
    if approved is None:
        flash("Invalid or inactive examiner.", "danger")
        return redirect(url_for("admin.bookings"))

    try:
        exam = booking.slot.examination
        exam.examiner_id = approved.id
        booking.slot.examiner_id = approved.id
        db.session.commit()
        flash(f"Assigned examiner changed to {approved.name}.", "success")
    except Exception:
        db.session.rollback()
        flash("Unable to change the assigned examiner.", "danger")
    return redirect(url_for("admin.bookings"))


# ------------------------------------------------------------------ profile
@admin.route("/profile", methods=["GET", "POST"])
@admin_required
def profile():
    if request.method == "GET":
        return render_template("admin/profile.html")

    name = request.form.get("name", "").strip()
    contact = request.form.get("contact_no", "").strip()
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not name or not contact:
        flash("Name and contact number are required.", "danger")
        return render_template("admin/profile.html")
    if not (contact.isdigit() and len(contact) == 10):
        flash("Contact number must contain exactly 10 digits.", "danger")
        return render_template("admin/profile.html")

    changing_pw = any([current_pw, new_pw, confirm_pw])
    if changing_pw:
        if not check_password_hash(current_user.password_hash, current_pw):
            flash("Current password is incorrect.", "danger")
            return render_template("admin/profile.html")
        if new_pw != confirm_pw or len(new_pw) < 8:
            flash("Enter matching new passwords of at least 8 characters.",
                  "danger")
            return render_template("admin/profile.html")

    try:
        current_user.name = name
        current_user.contact_no = contact
        if changing_pw:
            current_user.password_hash = generate_password_hash(new_pw)
        db.session.commit()
        flash("Profile updated successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Profile update failed.", "danger")
    return redirect(url_for("admin.profile"))
