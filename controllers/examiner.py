from datetime import date, datetime

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from decorators import examiner_required
from helpers import (occupied_seats, slot_creation_open, slots_locked,
                     sync_slot)
from models import Booking, EvaluationScore, Examination, ExamSlot, Rubric

examiner = Blueprint("examiner", __name__, url_prefix="/examiner")


def _my_exams():
    return db.session.scalars(
        db.select(Examination)
        .where(Examination.examiner_id == current_user.id)
        .order_by(Examination.examination_date.asc(), Examination.name.asc())
    ).all()


def _parse_time(value):
    value = (value or "").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def _validate_slot(data):
    if not data["date"]:
        return "Slot date is required."
    try:
        slot_date = date.fromisoformat(data["date"])
    except ValueError:
        return "Enter a valid slot date."
    start = _parse_time(data["start_time"])
    end = _parse_time(data["end_time"])
    if start is None or end is None:
        return "Enter valid start and end times."
    if end <= start:
        return "End time must be after the start time."
    if not data["capacity"].isdigit() or not (1 <= int(data["capacity"]) <= 500):
        return "Maximum student capacity must be between 1 and 500."
    if slot_date < date.today():
        return "Slot date cannot be in the past."
    return None


def _slot_form_data():
    return {
        "date": request.form.get("date", "").strip(),
        "start_time": request.form.get("start_time", "").strip(),
        "end_time": request.form.get("end_time", "").strip(),
        "capacity": request.form.get("maximum_student_capacity", "").strip(),
    }


# ------------------------------------------------------------------ dashboard
@examiner.route("/dashboard")
@examiner_required
def dashboard():
    exams = _my_exams()
    exam_ids = [exam.id for exam in exams]
    my_slots = db.session.scalars(
        db.select(ExamSlot)
        .where(ExamSlot.examiner_id == current_user.id)
        .order_by(ExamSlot.date.asc(), ExamSlot.start_time.asc())
    ).all()
    pending = []
    if exam_ids:
        pending = db.session.scalars(
            db.select(Booking)
            .join(ExamSlot, Booking.slot_id == ExamSlot.id)
            .where(ExamSlot.examination_id.in_(exam_ids),
                   Booking.status == "Booked")
            .order_by(Booking.booked_at.desc())
        ).all()
    return render_template("examiner/dashboard.html", exams=exams,
                           slots=my_slots, pending=pending)


# ---------------------------------------------------------- assigned exams
@examiner.route("/examinations")
@examiner_required
def examinations():
    exams = _my_exams()
    slots_by_exam = {}
    rubrics_by_exam = {}
    for exam in exams:
        slots_by_exam[exam.id] = db.session.scalars(
            db.select(ExamSlot)
            .where(ExamSlot.examination_id == exam.id)
            .order_by(ExamSlot.date.asc(), ExamSlot.start_time.asc())
        ).all()
        rubrics_by_exam[exam.id] = db.session.scalars(
            db.select(Rubric)
            .where(Rubric.examination_id == exam.id)
            .order_by(Rubric.id.asc())
        ).all()
    return render_template("examiner/examinations.html", exams=exams,
                           slots_by_exam=slots_by_exam,
                           rubrics_by_exam=rubrics_by_exam,
                           slot_creation_open=slot_creation_open,
                           slots_locked=slots_locked)


# ---------------------------------------------------------------- slot CRUD
@examiner.route("/examinations/<int:exam_id>/slots/add", methods=["GET", "POST"])
@examiner_required
def add_slot(exam_id):
    exam = db.session.get(Examination, exam_id)
    if exam is None or exam.examiner_id != current_user.id:
        abort(404)
    if not slot_creation_open(exam):
        flash("Slot creation is not open for this examination.", "warning")
        return redirect(url_for("examiner.examinations"))

    if request.method == "POST":
        data = _slot_form_data()
        error = _validate_slot(data)
        if error:
            flash(error, "danger")
        else:
            try:
                db.session.add(ExamSlot(
                    examination_id=exam.id,
                    examiner_id=current_user.id,
                    date=date.fromisoformat(data["date"]),
                    start_time=_parse_time(data["start_time"]),
                    end_time=_parse_time(data["end_time"]),
                    maximum_student_capacity=int(data["capacity"]),
                    available_seats=int(data["capacity"]),
                ))
                db.session.commit()
                flash("Slot created successfully.", "success")
                return redirect(url_for("examiner.examinations"))
            except Exception:
                db.session.rollback()
                flash("Unable to create the slot.", "danger")
    return render_template("examiner/slot_form.html", exam=exam, slot=None)


@examiner.route("/slots/<int:slot_id>/edit", methods=["GET", "POST"])
@examiner_required
def edit_slot(slot_id):
    slot = db.session.get(ExamSlot, slot_id)
    if slot is None or slot.examiner_id != current_user.id:
        abort(404)
    exam = slot.examination
    if slots_locked(exam):
        flash("Slots can only be edited before student booking opens.", "warning")
        return redirect(url_for("examiner.examinations"))

    if request.method == "POST":
        data = _slot_form_data()
        error = _validate_slot(data)
        booked = occupied_seats(slot.id)
        if not error and int(data["capacity"]) < booked:
            error = (f"Capacity cannot be lower than the {booked} "
                     "already booked seats.")
        if error:
            flash(error, "danger")
        else:
            try:
                slot.date = date.fromisoformat(data["date"])
                slot.start_time = _parse_time(data["start_time"])
                slot.end_time = _parse_time(data["end_time"])
                slot.maximum_student_capacity = int(data["capacity"])
                sync_slot(slot)
                db.session.commit()
                flash("Slot updated successfully.", "success")
                return redirect(url_for("examiner.examinations"))
            except Exception:
                db.session.rollback()
                flash("Unable to update the slot.", "danger")
    return render_template("examiner/slot_form.html", exam=exam, slot=slot)


@examiner.route("/slots/<int:slot_id>/delete", methods=["POST"])
@examiner_required
def delete_slot(slot_id):
    slot = db.session.get(ExamSlot, slot_id)
    if slot is None or slot.examiner_id != current_user.id:
        abort(404)
    exam = slot.examination
    if slots_locked(exam):
        flash("Slots can only be removed before student booking opens.", "warning")
    elif occupied_seats(slot.id) > 0:
        flash("Slots with bookings cannot be removed.", "danger")
    else:
        try:
            db.session.delete(slot)
            db.session.commit()
            flash("Slot removed successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Unable to remove the slot.", "danger")
    return redirect(url_for("examiner.examinations"))


# -------------------------------------------------------- evaluation rubrics
@examiner.route("/examinations/<int:exam_id>/rubrics/add", methods=["POST"])
@examiner_required
def add_rubric(exam_id):
    exam = db.session.get(Examination, exam_id)
    if exam is None or exam.examiner_id != current_user.id:
        abort(404)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    maximum = request.form.get("maximum_marks", "").strip()
    if not title:
        flash("Criterion title is required.", "danger")
    elif not maximum.isdigit() or not (1 <= int(maximum) <= 1000):
        flash("Maximum marks must be a number between 1 and 1000.", "danger")
    else:
        try:
            db.session.add(Rubric(
                examination_id=exam.id,
                title=title,
                description=description or None,
                maximum_marks=int(maximum),
            ))
            db.session.commit()
            flash("Evaluation criterion added.", "success")
        except Exception:
            db.session.rollback()
            flash("Unable to add the criterion.", "danger")
    return redirect(url_for("examiner.examinations"))


@examiner.route("/rubrics/<int:rubric_id>/delete", methods=["POST"])
@examiner_required
def delete_rubric(rubric_id):
    rubric = db.session.get(Rubric, rubric_id)
    if rubric is None or rubric.examination.examiner_id != current_user.id:
        abort(404)
    try:
        db.session.delete(rubric)
        db.session.commit()
        flash("Evaluation criterion removed.", "success")
    except Exception:
        db.session.rollback()
        flash("This criterion already has evaluation scores and cannot be removed.",
              "danger")
    return redirect(url_for("examiner.examinations"))


# ----------------------------------------------------------------- bookings
@examiner.route("/bookings")
@examiner_required
def bookings():
    status = request.args.get("status", "").strip()
    query = (db.select(Booking)
             .join(ExamSlot, Booking.slot_id == ExamSlot.id)
             .where(ExamSlot.examiner_id == current_user.id))
    if status:
        query = query.where(Booking.status == status)
    items = db.session.scalars(query.order_by(Booking.booked_at.desc())).all()
    return render_template("examiner/bookings.html", bookings=items,
                           selected_status=status)


@examiner.route("/bookings/<int:booking_id>/evaluate", methods=["GET", "POST"])
@examiner_required
def evaluate(booking_id):
    booking = db.session.scalar(
        db.select(Booking)
        .join(ExamSlot, Booking.slot_id == ExamSlot.id)
        .where(Booking.id == booking_id,
               ExamSlot.examiner_id == current_user.id))
    if booking is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("examiner.bookings"))

    exam = booking.slot.examination
    rubrics = db.session.scalars(
        db.select(Rubric)
        .where(Rubric.examination_id == exam.id)
        .order_by(Rubric.id.asc())
    ).all()
    scores = {score.rubric_id: score for score in booking.scores}

    if request.method == "POST":
        if booking.status == "Cancelled":
            flash("Cancelled bookings cannot be evaluated.", "warning")
            return redirect(url_for("examiner.bookings"))
        if not rubrics:
            flash("Add evaluation criteria before evaluating.", "warning")
            return redirect(url_for("examiner.evaluate", booking_id=booking.id))

        feedback = request.form.get("feedback", "").strip()
        updated, total, problem = [], 0, None
        for rubric in rubrics:
            raw = request.form.get(f"marks_{rubric.id}", "").strip()
            try:
                value = float(raw)
            except ValueError:
                problem = f"Enter marks for '{rubric.title}'."
                break
            if value < 0 or value > rubric.maximum_marks:
                problem = (f"Marks for '{rubric.title}' must be between "
                           f"0 and {rubric.maximum_marks}.")
                break
            updated.append((rubric, value))
            total += value

        if problem:
            flash(problem, "danger")
        else:
            try:
                for rubric, value in updated:
                    score = scores.get(rubric.id)
                    if score is None:
                        db.session.add(EvaluationScore(
                            booking_id=booking.id,
                            rubric_id=rubric.id,
                            marks=value,
                        ))
                    else:
                        score.marks = value
                booking.marks = round(total, 2)
                booking.feedback = feedback or None
                if booking.status == "Booked":
                    booking.status = "Completed"
                    booking.evaluated_at = datetime.now()
                db.session.commit()
                flash("Evaluation saved successfully.", "success")
                return redirect(url_for("examiner.bookings"))
            except Exception:
                db.session.rollback()
                flash("Unable to save the evaluation.", "danger")

    return render_template("examiner/evaluate.html", booking=booking,
                           exam=exam, rubrics=rubrics, scores=scores)


# ------------------------------------------------------------------ profile
@examiner.route("/profile", methods=["GET", "POST"])
@examiner_required
def profile():
    if request.method == "GET":
        return render_template("examiner/profile.html")

    name = request.form.get("name", "").strip()
    contact = request.form.get("contact_no", "").strip()
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not name or not contact:
        flash("Name and contact number are required.", "danger")
        return render_template("examiner/profile.html")
    if not (contact.isdigit() and len(contact) == 10):
        flash("Contact number must contain exactly 10 digits.", "danger")
        return render_template("examiner/profile.html")

    changing_pw = any([current_pw, new_pw, confirm_pw])
    if changing_pw:
        if not check_password_hash(current_user.password_hash, current_pw):
            flash("Current password is incorrect.", "danger")
            return render_template("examiner/profile.html")
        if new_pw != confirm_pw or len(new_pw) < 8:
            flash("Enter matching new passwords of at least 8 characters.", "danger")
            return render_template("examiner/profile.html")

    try:
        current_user.name = name
        current_user.contact_no = contact
        if changing_pw:
            current_user.password_hash = generate_password_hash(new_pw)
        profile = current_user.examiner_profile
        if profile is not None:
            profile.qualification = request.form.get("qualification", "").strip() \
                or profile.qualification
            profile.specialization = request.form.get("specialization", "").strip() \
                or profile.specialization
        db.session.commit()
        flash("Profile updated successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Profile update failed.", "danger")
    return redirect(url_for("examiner.profile"))
