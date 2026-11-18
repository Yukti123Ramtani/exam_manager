from datetime import datetime, timezone

from flask_login import UserMixin

from database import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    contact_no = db.Column(db.String(10), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="Student")  # Admin / Examiner / Student
    status = db.Column(db.String(20), nullable=False, default="Active")  # Active / Inactive
    created_at = db.Column(db.DateTime, default=utcnow)

    examiner_profile = db.relationship(
        "ExaminerProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    bookings = db.relationship(
        "Booking", backref="student", cascade="all, delete-orphan"
    )


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(30), unique=True, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="Active")
    created_at = db.Column(db.DateTime, default=utcnow)

    examinations = db.relationship(
        "Examination", backref="course", cascade="all, delete-orphan"
    )


class ExaminerProfile(db.Model):
    __tablename__ = "examiner_profiles"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    qualification = db.Column(db.String(150))
    specialization = db.Column(db.String(150))
    experience = db.Column(db.Integer)
    approval_status = db.Column(
        db.String(20), nullable=False, default="Pending"
    )  # Pending / Approved / Rejected


class Examination(db.Model):
    __tablename__ = "examinations"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    # NEW: assigned examiner (milestone: "view assigned examinations",
    # "change the assigned examiner")
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    examination_type = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # minutes
    examination_date = db.Column(db.Date, nullable=False)
    # Draft / Slot Creation / Bookings Open / Bookings Closed /
    # Ongoing / Completed / Cancelled
    status = db.Column(db.String(30), nullable=False, default="Draft")

    # NEW: timeline (all optional, set by admin)
    exam_start = db.Column(db.DateTime)
    exam_end = db.Column(db.DateTime)
    examiner_slot_open = db.Column(db.DateTime)
    examiner_slot_close = db.Column(db.DateTime)
    student_booking_open = db.Column(db.DateTime)
    student_booking_close = db.Column(db.DateTime)  # also the cancellation deadline

    created_at = db.Column(db.DateTime, default=utcnow)

    examiner = db.relationship("User", foreign_keys=[examiner_id])
    slots = db.relationship(
        "ExamSlot", backref="examination", cascade="all, delete-orphan"
    )
    rubrics = db.relationship(
        "Rubric", backref="examination", cascade="all, delete-orphan"
    )


class ExamSlot(db.Model):
    __tablename__ = "exam_slots"

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    maximum_student_capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Available")  # Available / Full / Cancelled / Completed

    examiner = db.relationship("User", backref="exam_slots", foreign_keys=[examiner_id])
    bookings = db.relationship(
        "Booking", backref="slot", cascade="all, delete-orphan"
    )


class Rubric(db.Model):
    __tablename__ = "rubrics"

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    maximum_marks = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("exam_slots.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Booked")  # Booked / Cancelled / Completed
    payment_status = db.Column(db.String(20), nullable=False, default="Pending")
    marks = db.Column(db.Numeric(6, 2))
    feedback = db.Column(db.Text)
    booked_at = db.Column(db.DateTime, default=utcnow)
    evaluated_at = db.Column(db.DateTime)

    scores = db.relationship(
        "EvaluationScore", backref="booking", cascade="all, delete-orphan"
    )


class EvaluationScore(db.Model):
    """NEW: per-rubric marks for one booking (milestone: evaluate using rubrics)."""

    __tablename__ = "evaluation_scores"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubrics.id"), nullable=False)
    marks = db.Column(db.Numeric(6, 2), nullable=False)

    rubric = db.relationship("Rubric")
    __table_args__ = (db.UniqueConstraint("booking_id", "rubric_id"),)