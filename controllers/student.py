from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for # type: ignore
from flask_login import current_user # type: ignore
from sqlalchemy import func, or_ # type: ignore
from werkzeug.security import check_password_hash, generate_password_hash # type: ignore

from database import db
from decorators import student_required
from helpers import ACTIVE_BOOKING, booking_open, deadline_passed, occupied_seats, sync_slot
from models import Booking, Examination, ExamSlot

student = Blueprint("student", __name__, url_prefix="/student")

VISIBLE_STATUSES = ["Bookings Open", "Bookings Closed"]
BOOKABLE_STATUS = "Bookings Open"


def _active_booking_for_exam(student_id, exam_id):
    return db.session.scalar(
        db.select(Booking)
        .join(ExamSlot, Booking.slot_id == ExamSlot.id)
        .where(Booking.student_id == student_id,
               ExamSlot.examination_id == exam_id,
               Booking.status.in_(ACTIVE_BOOKING)))


# Student dashboard
@student.route("/dashboard")
@student_required
def dashboard():
    sid = current_user.id
    counts = {
        status: db.session.scalar(
            db.select(func.count(Booking.id)).where(
                Booking.student_id == sid, Booking.status == status)) or 0
        for status in ("Booked", "Completed")
    }
    available_exams = db.session.scalar(
        db.select(func.count(Examination.id)).where(
            Examination.status == BOOKABLE_STATUS)) or 0
    bookings = db.session.scalars(
        db.select(Booking).where(Booking.student_id == sid)
        .order_by(Booking.booked_at.desc())).all()
    upcoming = [b for b in bookings if b.status == "Booked"][:3]
    return render_template(
        "student/dashboard.html",
        active_bookings=counts["Booked"],
        completed_exams=counts["Completed"],
        available_exams=available_exams,
        upcoming_bookings=upcoming,
        recent_bookings=bookings[:5],
    )


# Search / filter examinations
@student.route("/examinations")
@student_required
def examinations():
    query_text = request.args.get("q", "").strip()
    exam_type = request.args.get("type", "").strip()

    query = db.select(Examination).where(Examination.status.in_(VISIBLE_STATUSES))
    if query_text:
        query = query.where(or_(Examination.name.ilike(f"%{query_text}%"),
                                Examination.description.ilike(f"%{query_text}%")))
    if exam_type:
        query = query.where(Examination.examination_type == exam_type)

    exams = db.session.scalars(query.order_by(Examination.examination_date.asc())).all()
    exam_types = db.session.scalars(
        db.select(Examination.examination_type).distinct()
        .order_by(Examination.examination_type)).all()
    return render_template(
        "student/examinations.html", examinations=exams, exam_types=exam_types,
        q=query_text, selected_type=exam_type)


# Examination details + available slots
@student.route("/examinations/<int:exam_id>")
@student_required
def examination_detail(exam_id):
    exam = db.session.get(Examination, exam_id)
    if exam is None or exam.status not in VISIBLE_STATUSES:
        flash("Examination not found.", "danger")
        return redirect(url_for("student.examinations"))

    slots = db.session.scalars(
        db.select(ExamSlot)
        .where(ExamSlot.examination_id == exam.id,
               ExamSlot.status == "Available",
               ExamSlot.available_seats > 0)
        .order_by(ExamSlot.date.asc(), ExamSlot.start_time.asc())).all()
    existing = _active_booking_for_exam(current_user.id, exam.id)
    return render_template(
        "student/examination_detail.html", examination=exam, slots=slots,
        existing_booking=existing, booking_open=booking_open(exam))


# Book an examination slot
@student.route("/slots/<int:slot_id>/book", methods=["POST"])
@student_required
def book_slot(slot_id):
    slot = db.session.get(ExamSlot, slot_id)
    if slot is None:
        abort(404)
    exam = slot.examination
    back = url_for("student.examination_detail", exam_id=exam.id)

    if exam.status not in VISIBLE_STATUSES:
        flash("This examination is not available.", "danger")
    elif not booking_open(exam):
        flash("Student booking is closed for this examination.", "danger")
    elif (slot.status != "Available" or slot.available_seats <= 0
          or occupied_seats(slot.id) >= slot.maximum_student_capacity):
        flash("This slot is full or unavailable.", "danger")
    elif _active_booking_for_exam(current_user.id, exam.id):
        flash("You already have a booking for this examination.", "warning")
    else:
        try:
            db.session.add(Booking(student_id=current_user.id, slot_id=slot.id))
            sync_slot(slot)  # reduces seats, marks slot Full when capacity reached
            db.session.commit()
            flash("Slot booked successfully.", "success")
            return redirect(url_for("student.bookings"))
        except Exception:
            db.session.rollback()
            flash("Unable to book the slot.", "danger")
    return redirect(back)


# Booking history / status / results
@student.route("/bookings")
@student_required
def bookings():
    status = request.args.get("status", "").strip()
    query = db.select(Booking).where(Booking.student_id == current_user.id)
    if status:
        query = query.where(Booking.status == status)
    items = db.session.scalars(query.order_by(Booking.booked_at.desc())).all()
    return render_template("student/bookings.html", bookings=items,
                           selected_status=status, now=datetime.now())


@student.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@student_required
def cancel_booking(booking_id):
    booking = db.session.scalar(
        db.select(Booking).where(Booking.id == booking_id,
                                 Booking.student_id == current_user.id))
    if booking is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("student.bookings"))

    slot = booking.slot
    exam = slot.examination

    if booking.status == "Cancelled":
        flash("Booking is already cancelled.", "warning")
    elif booking.status != "Booked":
        flash("This booking can no longer be cancelled.", "danger")
    elif exam.status not in ("Bookings Open", "Bookings Closed") or deadline_passed(exam):
        flash("The booking deadline has passed.", "danger")
    else:
        try:
            booking.status = "Cancelled"
            sync_slot(slot)  # frees the seat and re-opens a Full slot
            db.session.commit()
            flash("Booking cancelled successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Unable to cancel the booking.", "danger")
    return redirect(url_for("student.bookings"))


# Student profile
@student.route("/profile", methods=["GET", "POST"])
@student_required
def profile():
    if request.method == "GET":
        return render_template("student/profile.html")

    name = request.form.get("name", "").strip()
    contact = request.form.get("contact_no", "").strip()
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if not name or not contact:
        flash("Name and contact number are required.", "danger")
        return render_template("student/profile.html")
    if not (contact.isdigit() and len(contact) == 10):
        flash("Contact number must contain exactly 10 digits.", "danger")
        return render_template("student/profile.html")

    changing_pw = any([current_pw, new_pw, confirm_pw])
    if changing_pw:
        if not check_password_hash(current_user.password_hash, current_pw):
            flash("Current password is incorrect.", "danger")
            return render_template("student/profile.html")
        if new_pw != confirm_pw or len(new_pw) < 8:
            flash("Enter matching new passwords of at least 8 characters.", "danger")
            return render_template("student/profile.html")

    try:
        current_user.name = name
        current_user.contact_no = contact
        if changing_pw:
            current_user.password_hash = generate_password_hash(new_pw)
        db.session.commit()  # always commit, not only on password change
        flash("Profile updated successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Profile update failed.", "danger")
    return redirect(url_for("student.profile"))