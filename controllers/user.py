from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user # type: ignore
from werkzeug.security import check_password_hash, generate_password_hash # type: ignore
from sqlalchemy import func, or_ 

from database import db
from decorators import student_required
from models import Booking, ExamSlot, Examination, User

student = Blueprint("student", __name__, url_prefix="/student")

# Constants
EXAM_STATUSES = ["Approved", "Bookings Open"]
BOOKABLE_STATUS = "Bookings Open"


# Student dashboard
@student.route("/dashboard")
@student_required
def dashboard():
    sid=current_user.id 
    booking_counts={status:db.session.scalar(db.select(func.count(Booking.count))
                                             .where(Booking.student_id==sid,Booking.status==status)
                                               or 0) for status in ("Booked","Completed")}
    exam_count=db.session.scalar
    (db.select(func.count
               (Examination.id)).where(Examination.status==BOOKABLE_STATUS))
    bookings=db.session.scalars
    (db.select(Booking)
     .where(Booking.student_id==sid)
     .order_by(Booking.created_at_desc())).all()
    upcoming=[booking for booking in bookings if booking.status=="Booked"][:3]
    return render_template("student/dashboard.html",active_bookings=booking_counts["Booked"],
                           completed_exams=booking_counts["Completed"],
                           available_exams=exam_count,
                           upcoming_bookings=upcoming,
                           recent_bookings=bookings[:5])
@student.route("/examinations")
@student_required
def examinations():
    query_text=request.args.get("q","").strip()
    exam_type=request.args.get("type","").strip()
    query=db.select(Examination).where(Examination.status.in_(EXAM_STATUSES))
    if query_text:
        query=query.where(or_(Examination.name.ilike(f"%{query_text}%"),
                              Examination.status.ilike(f"%{query_text}")))
    if exam_type:
        query=query.where(Examination.exam_type==exam_type)
    exams=db.session.scalars(query.order_by(Examination.exam_date.asc())).all()
    exam_types=db.session.scalars(db.select(Examination.exam_type.distinct()).order_by
                                  (Examination.exam_type)).all()
    return render_template("student/examination.html",
                           examination=exams,exam_types=exam_type,q=query_text,selected_type=exam_type)

# Examination details

@student.route("/examinations/<int:exam_id>")
@student_required
def examination_detail(exam_id):
    examination=db.session.get(Examination,exam_id)
    if examination is None or examination.status not in EXAM_STATUSES:
        flash("Examination not found","danger")
        return redirect(url_for("student.examinations"))
    slot_query=(
        db.select(ExamSlot)
        .where(ExamSlot.examination_id==examination.id)
        .where(ExamSlot.status=='Available')
        .where(ExamSlot.available_seats > 0)
        .order_by(ExamSlot.date.asc(),ExamSlot.start_time.asc())
    )
    slots=db.session.scalars(slot_query).all()
    booking_query=(db.select(Booking)
                   .join(ExamSlot,Booking.slot_id==ExamSlot.id)
                   .where(Booking.student_id==current_user.id)
                   .where(ExamSlot.examination_id==examination.id)
                   .where(Booking.status=="Booked"))
    existing_query=db.session.get(booking_query)
    existing_booking=db.session.scalar(existing_query)
    return render_template("student/examination.html",examination=examination,
                           slots=slots,existing_booking=existing_booking)

# Book an examination slot

                            


@student.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@student_required
def cancel_booking(booking_id):
    booking = db.session.scalar(
        db.select(Booking).where(
            Booking.id == booking_id,
            Booking.student_id == current_user.id,
        )
    )

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("student.bookings"))

    slot = db.session.get(ExamSlot, booking.slot_id)
    exam = db.session.get(Examination, slot.examination_id)

    blocked = {
        "Cancelled": "Booking is already cancelled.",
        "Ongoing": "Booking can no longer be cancelled.",
        "Completed": "Booking can no longer be cancelled.",
        "Cancelled": "Booking can no longer be cancelled.",
    }

    if booking.status in blocked:
        flash(
            blocked[booking.status],
            "warning" if booking.status == "Cancelled" else "danger",
        )
        return redirect(url_for("student.bookings"))

    try:
        booking.status = "Cancelled"
        slot.available_seats = min(
            slot.maximum_student_capacity,
            slot.available_seats + 1,
        )
        db.session.commit()
        flash("Booking cancelled successfully.", "success")

    except Exception:
        db.session.rollback()
        flash("Unable to cancel the booking.", "danger")

    return redirect(url_for("student.bookings"))



# Student profile
@student.route("/profile",methods=["GET","POST"])
@student_required
def profile():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        contact=request.form.get("contact_no","").strip()
        current_password=request.form.get("current_password","").strip()
        new_password=request.form.get("new_password","").strip()
        confirm_password=request.form.get("confirm_password","").strip()
        if not name or not contact:
            flash("name and contact number are required","danger")
            return render_template("student/profile.html")
        if not contact.isdigit() or len(contact)!=10:
            flash("contact number must contain exactly 10 digits","danger")
            return render_template("student/profile.html")
        password_change=any([current_password,new_password,confirm_password])
        if password_change:
            if not check_password_hash(current_user.password_hash,current_password):
                flash("current password is incorrect","danger")
                return render_template("student/profile.html")
            if new_password!=confirm_password or len(new_password) < 8:
                flash("Entering a matching password of atleast 8 characters","danger")
                return render_template("student/profile.html")
        try:
            current_user.name=name
            current_user.contact_no=contact 
            if password_change:
                current_user.password_hash=generate_password_hash(new_password)
                db.session.commit()
        except Exception:
            db.session.rollback()
            flash("profile update failed","danger")
            return redirect(url_for("student.profile"))
    return render_template("student/profile.html")
    