from datetime import datetime

from sqlalchemy import func

from database import db
from models import Booking

ACTIVE_BOOKING = ("Booked", "Completed")
EXAM_STATUSES = ("Draft", "Slot Creation", "Bookings Open", "Bookings Closed",
                 "Ongoing", "Completed", "Cancelled")


def parse_dt(value):
    """Parse an <input type=datetime-local> value; empty -> None."""
    value = (value or "").strip()
    return datetime.fromisoformat(value) if value else None


def occupied_seats(slot_id):
    return db.session.scalar(
        db.select(func.count(Booking.id)).where(
            Booking.slot_id == slot_id, Booking.status.in_(ACTIVE_BOOKING))
    ) or 0


def sync_slot(slot):
    """Recalculate seats and Available/Full status from real bookings."""
    db.session.flush()
    slot.available_seats = max(slot.maximum_student_capacity - occupied_seats(slot.id), 0)
    if slot.status in ("Available", "Full"):
        slot.status = "Full" if slot.available_seats == 0 else "Available"


def _within(start, end):
    now = datetime.now()
    return (start is None or now >= start) and (end is None or now <= end)


def slot_creation_open(exam):
    """Examiner may create slots only while admin has opened slot creation."""
    return exam.status == "Slot Creation" and _within(
        exam.examiner_slot_open, exam.examiner_slot_close)


def booking_open(exam):
    """Students may book only while admin has opened booking."""
    return exam.status == "Bookings Open" and _within(
        exam.student_booking_open, exam.student_booking_close)


def slots_locked(exam):
    """Examiner may edit/remove slots only before student booking starts."""
    return exam.status not in ("Draft", "Slot Creation")


def deadline_passed(exam):
    return (exam.student_booking_close is not None
            and datetime.now() > exam.student_booking_close)