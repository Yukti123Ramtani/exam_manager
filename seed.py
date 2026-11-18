from datetime import date, datetime, timedelta, timezone
import random

from werkzeug.security import generate_password_hash
from sqlalchemy import func

from app import app
from database import db
from models import (
    Booking,
    Course,
    Examination,
    ExaminerProfile,
    ExamSlot,
    Rubric,
    User,
)


PASSWORD = "Password@123"
PASSWORD_HASH = generate_password_hash(PASSWORD)

BOOKING_HISTORY_STATUSES = {
    "Bookings Open",
    "Bookings Closed",
    "Ongoing",
    "Completed",
    "Cancelled",
}


def random_phone():
    return random.choice("6789") + "".join(
        random.choices("0123456789", k=9)
    )


def random_datetime_before(ref_date, minimum_days=1, maximum_days=60):
    days = random.randint(minimum_days, maximum_days)
    value = datetime.combine(
        ref_date - timedelta(days=days),
        datetime.min.time(),
    )
    return value.replace(tzinfo=timezone.utc)


STUDENT_DATA = [
    ("Aarav Sharma", "aarav.sharma"),
    ("Vivaan Gupta", "vivaan.gupta"),
    ("Aditya Verma", "aditya.verma"),
    ("Vihaan Kapoor", "vihaan.kapoor"),
    ("Arjun Singh", "arjun.singh"),
    ("Krishna Nair", "krishna.nair"),
    ("Rohan Mehta", "rohan.mehta"),
    ("Rahul Joshi", "rahul.joshi"),
    ("Karan Bansal", "karan.bansal"),
    ("Siddharth Rao", "siddharth.rao"),
    ("Neha Iyer", "neha.iyer"),
    ("Ananya Das", "ananya.das"),
    ("Priya Kulkarni", "priya.kulkarni"),
    ("Sneha Patil", "sneha.patil"),
    ("Pooja Reddy", "pooja.reddy"),
    ("Ishita Jain", "ishita.jain"),
    ("Aditi Menon", "aditi.menon"),
    ("Meera Chawla", "meera.chawla"),
    ("Ritika Arora", "ritika.arora"),
    ("Kavya Mishra", "kavya.mishra"),
    ("Tanuj Bhatt", "tanuj.bhatt"),
    ("Simran Kaur", "simran.kaur"),
    ("Dev Malhotra", "dev.malhotra"),
    ("Riya Saxena", "riya.saxena"),
]

BLACKLISTED_STUDENTS = {
    "karan.bansal",
    "ritika.arora",
}


EXAMINER_DATA = [
    (
        "Nikhil Rawat",
        "nikhil.rawat",
        "MSc Computer Science",
        "Software Engineering",
        9,
        "Active",
        "Approved",
    ),
    (
        "Saurabh Negi",
        "saurabh.negi",
        "MTech Information Technology",
        "Database Systems",
        7,
        "Active",
        "Approved",
    ),
    (
        "Manish Bisht",
        "manish.bisht",
        "MCA",
        "Web Development",
        6,
        "Active",
        "Approved",
    ),
    (
        "Ankit Thapa",
        "ankit.thapa",
        "MSc Computer Science",
        "Computer Networks",
        5,
        "Active",
        "Approved",
    ),
    (
        "Deepak Rana",
        "deepak.rana",
        "MTech Information Technology",
        "Cloud Computing",
        8,
        "Active",
        "Approved",
    ),
    (
        "Rahul Chauhan",
        "rahul.chauhan",
        "MSc Computer Science",
        "Data Structures",
        6,
        "Active",
        "Approved",
    ),
    (
        "Vikas Joshi",
        "vikas.joshi",
        "MCA",
        "Operating Systems",
        5,
        "Active",
        "Approved",
    ),
    (
        "Akash Singh",
        "akash.singh",
        "MSc Artificial Intelligence",
        "Artificial Intelligence",
        3,
        "Active",
        "Pending",
    ),
    (
        "Abhishek Mehra",
        "abhishek.mehra",
        "MTech Cybersecurity",
        "Cybersecurity",
        3,
        "Active",
        "Rejected",
    ),
    (
        "Tarun Kapoor",
        "tarun.kapoor",
        "MSc Computer Science",
        "Software Testing",
        4,
        "Blacklisted",
        "Rejected",
    ),
]


COURSE_DATA = [
    (
        "BSc Computer Science",
        "CS101",
        "Fundamentals of programming and computer science.",
    ),
    (
        "Database Management Systems",
        "CS202",
        "SQL, normalization, transactions, and database design.",
    ),
    (
        "Web Application Development",
        "CS303",
        "Frontend, backend, APIs, and full-stack development.",
    ),
    (
        "Computer Networks",
        "CS204",
        "Networking concepts, protocols, and network security.",
    ),
    (
        "Data Structures and Algorithms",
        "CS205",
        "Data structures, algorithms, and complexity analysis.",
    ),
    (
        "Operating Systems",
        "CS206",
        "Processes, memory, scheduling, and file systems.",
    ),
]


EXAMINATION_DATA = [
    {
        "name": "Python Programming Fundamentals",
        "course": "CS101",
        "type": "Theory",
        "duration": 120,
        "capacity": 35,
        "status": "Bookings Open",
    },
    {
        "name": "Advanced SQL Assessment",
        "course": "CS202",
        "type": "Practical",
        "duration": 90,
        "capacity": 30,
        "status": "Bookings Open",
    },
    {
        "name": "Full Stack Web Development",
        "course": "CS303",
        "type": "Practical",
        "duration": 180,
        "capacity": 25,
        "status": "Approved",
    },
    {
        "name": "Network Configuration Test",
        "course": "CS204",
        "type": "Practical",
        "duration": 120,
        "capacity": 20,
        "status": "Bookings Closed",
    },
    {
        "name": "Algorithms and Complexity",
        "course": "CS205",
        "type": "Theory",
        "duration": 150,
        "capacity": 40,
        "status": "Ongoing",
    },
    {
        "name": "Operating Systems Final Exam",
        "course": "CS206",
        "type": "Theory",
        "duration": 120,
        "capacity": 40,
        "status": "Completed",
    },
    {
        "name": "Software Engineering Viva",
        "course": "CS101",
        "type": "Viva",
        "duration": 30,
        "capacity": 15,
        "status": "Cancelled",
    },
    {
        "name": "Data Structures Internal Exam",
        "course": "CS205",
        "type": "Theory",
        "duration": 120,
        "capacity": 35,
        "status": "Draft",
    },
    {
        "name": "Database Design Viva",
        "course": "CS202",
        "type": "Viva",
        "duration": 30,
        "capacity": 20,
        "status": "Approved",
    },
    {
        "name": "Web Technologies Assessment",
        "course": "CS303",
        "type": "Theory",
        "duration": 120,
        "capacity": 35,
        "status": "Bookings Open",
    },
]


def create_students():
    students = []

    for name, username in STUDENT_DATA:
        students.append(
            User(
                name=name,
                email=f"{username}@gmail.com",
                password_hash=PASSWORD_HASH,
                contact_no=random_phone(),
                role="Student",
                status=(
                    "Blacklisted"
                    if username in BLACKLISTED_STUDENTS
                    else "Active"
                ),
            )
        )

    db.session.add_all(students)
    db.session.commit()

    print(f"{len(students)} student accounts created.")
    return students



def create_examiners():
    examiners = []

    for (
        name,
        username,
        qualification,
        specialization,
        experience,
        status,
        approval_status,
    ) in EXAMINER_DATA:
        examiner = User(
            name=name,
            email=f"{username}@gmail.com",
            password_hash=PASSWORD_HASH,
            contact_no=random_phone(),
            role="Examiner",
            status=status,
        )

        profile = ExaminerProfile(
            qualification=qualification,
            specialization=specialization,
            experience=experience,
            approval_status=approval_status,
        )

        examiner.examiner_profile = profile
        db.session.add(examiner)
        examiners.append(examiner)


    db.session.commit()

    print(f"Created {len(examiners)} examiners.")
    return examiners


def create_courses():
    courses = {}

    for name, code, description in COURSE_DATA:
        course = Course(
            name=name,
            code=code,
            description=description,
            status="Active",
        )

        db.session.add(course)
        courses[code] = course

    db.session.commit()

    print(f"Created {len(courses)} courses.")
    return courses


def get_exam_date(status, duration):
    if status == "Completed":
        return date.today() - timedelta(
            days=random.randint(10, 60)
        )

    if status == "Ongoing":
        return date.today() - timedelta(
            days=random.randint(0, max(1, duration // 1440))
        )

    if status == "Cancelled":
        return date.today() + timedelta(
            days=random.randint(5, 45)
        )

    return date.today() + timedelta(
        days=random.randint(10, 90)
    )


def create_rubrics(examination):
    rubric_data = [
        (
            "Technical Knowledge",
            "Understanding of core concepts.",
            30,
        ),
        (
            "Problem Solving",
            "Ability to solve examination problems.",
            30,
        ),
        (
            "Practical Application",
            "Application of concepts in practice.",
            25,
        ),
        (
            "Communication",
            "Clarity and quality of responses.",
            15,
        ),
    ]

    db.session.add_all(
        [
            Rubric(
                examination_id=examination.id,
                title=title,
                description=description,
                maximum_marks=marks,
            )
            for title, description, marks in rubric_data
        ]
    )


def create_exam_slot(examination, examiner, capacity, exam_date):
    start_time = datetime.strptime(
        "09:00",
        "%H:%M",
    ).time()

    end_time = (
        datetime.combine(date.today(), start_time)
        + timedelta(minutes=examination.duration)
    ).time()

    db.session.add(
        ExamSlot(
            examination_id=examination.id,
            examiner_id=examiner.id,
            date=exam_date,
            start_time=start_time,
            end_time=end_time,
            maximum_student_capacity=capacity,
            available_seats=capacity,
            status="Available",
        )
    )


def create_examinations(courses, examiners):
    approved_examiners = [
        examiner
        for examiner in examiners
        if (
            examiner.status == "Active"
            and examiner.examiner_profile
            and examiner.examiner_profile.approval_status == "Approved"
        )
    ]

    examinations = []

    for data in EXAMINATION_DATA:
        exam_date = get_exam_date(
            data["status"],
            data["duration"],
        )

        examination = Examination(
            course=courses[data["course"]],
            name=data["name"],
            description=f"{data['name']} for {courses[data['course']].name}.",
            examination_type=data["type"],
            duration=data["duration"],
            examination_date=exam_date,
            status=data["status"],
        )

        db.session.add(examination)
        db.session.flush()

        create_rubrics(examination)

        if approved_examiners:
            create_exam_slot(
                examination,
                random.choice(approved_examiners),
                data["capacity"],
                exam_date,
            )

        examinations.append(examination)

    db.session.commit()

    print(f"Created {len(examinations)} examinations.")
    return examinations


def booking_details(examination):
    if examination.status == "Cancelled":
        return (
            "Cancelled",
            random.choice(["Refunded", "Paid", "Pending"]),
            None,
            None,
        )

    if examination.status == "Completed":
        status = random.choices(
            ["Completed", "Cancelled"],
            weights=[80, 20],
        )[0]

        return (
            status,
            "Paid" if status == "Completed"
            else random.choice(["Refunded", "Paid", "Pending"]),
            random.randint(45, 100)
            if status == "Completed"
            else None,
            "Assessment completed successfully."
            if status == "Completed"
            else None,
        )

    return (
        "Booked",
        random.choice(["Paid", "Pending"]),
        None,
        None,
    )


def create_bookings(students, examinations):
    active_students = [
        student
        for student in students
        if student.status == "Active"
    ]

    bookings = []

    for examination in examinations:
        if (
            examination.status in {"Draft", "Approved"}
            or not examination.slots
        ):
            continue

        slot = examination.slots[0]

        number_of_students = random.randint(
            max(1, slot.maximum_student_capacity // 3),
            slot.maximum_student_capacity,
        )

        selected_students = random.sample(
            active_students,
            min(number_of_students, len(active_students)),
        )

        for student in selected_students:
            if slot.available_seats <= 0:
                break

            status, payment_status, marks, feedback = booking_details(
                examination
            )

            booking = Booking(
                student_id=student.id,
                slot_id=slot.id,
                status=status,
                payment_status=payment_status,
                marks=marks,
                feedback=feedback,
                booked_at=random_datetime_before(
                    examination.examination_date,
                    1,
                    45,
                ),
            )

            db.session.add(booking)
            bookings.append(booking)

            if status == "Booked":
                slot.available_seats -= 1

    db.session.commit()

    print(f"Created {len(bookings)} bookings.")
    return bookings


def recalculate_available_seats():
    slots = db.session.scalars(
        db.select(ExamSlot)
    ).all()

    for slot in slots:
        if slot.examination.status in {
            "Ongoing",
            "Completed",
            "Cancelled",
        }:
            slot.available_seats = 0
            continue

        booked_count = db.session.scalar(
            db.select(func.count(Booking.id)).where(
                Booking.slot_id == slot.id,
                Booking.status == "Booked",
            )
        ) or 0

        slot.available_seats = max(
            0,
            slot.maximum_student_capacity - booked_count,
        )

    db.session.commit()
    print("Available seats recalculated.")


def clear_existing_data():
    print("Removing existing exam portal data...")

    db.session.query(Booking).delete()
    db.session.query(ExamSlot).delete()
    db.session.query(Rubric).delete()
    db.session.query(Examination).delete()
    db.session.query(Course).delete()
    db.session.query(ExaminerProfile).delete()

    db.session.query(User).filter(
        User.role != "Admin"
    ).delete()

    db.session.commit()
    print("Cleanup complete.")


def main():
    with app.app_context():
        random.seed()
        db.create_all()

        clear_existing_data()

        students = create_students()
        examiners = create_examiners()
        courses = create_courses()
        examinations = create_examinations(
            courses,
            examiners,
        )

        create_bookings(
            students,
            examinations,
        )

        recalculate_available_seats()

        print("=" * 60)
        print("EXAM MANAGEMENT PORTAL - DATABASE SEEDER")
        print("=" * 60)
        print(f"Password for all seeded accounts: {PASSWORD}")
        print("Admin: admin@examportal.com")
        print("Examiner: nikhil.rawat@gmail.com")
        print("Pending examiner: akash.singh@gmail.com")
        print("Rejected examiner: abhishek.mehra@gmail.com")
        print("Student: aarav.sharma@gmail.com")
        print("=" * 60)


if __name__ == "__main__":
    main()
