from app import app
from database import db
from models import (Booking, Course, EvaluationScore, Examination,
                    ExaminerProfile, ExamSlot, Rubric, User)

with app.app_context():
    for model in (EvaluationScore, Booking, ExamSlot, Rubric, Examination,
                  Course, ExaminerProfile):
        db.session.execute(db.delete(model))
    db.session.execute(db.delete(User).where(User.role != "Admin"))
    db.session.commit()
    print("All exam-management data cleared. Admin account preserved.")