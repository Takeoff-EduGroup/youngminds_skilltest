"""
Database models (Flask-SQLAlchemy ORM).

Tables
    students   - details entered by the student before taking a test
    admins     - admin accounts
    domains    - technologies (AI/ML, MERN, VLSI, ...)
    questions  - MCQs for each technology
    attempts   - one row per submitted test
"""

import random
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, event, inspect, select
from sqlalchemy.engine import Engine
from werkzeug.security import generate_password_hash

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    """Enable foreign keys (for cascading deletes) and WAL mode (better concurrent access)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    department = db.Column(db.String(60), nullable=False, index=True)
    year = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    attempts = db.relationship("Attempt", back_populates="student",
                               cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f"<Student {self.id} {self.name}>"


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Admin {self.email}>"


class Domain(db.Model):
    __tablename__ = "domains"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    short_name = db.Column(db.String(60), nullable=False)
    branch = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    questions = db.relationship("Question", back_populates="domain",
                                cascade="all, delete-orphan", passive_deletes=True)
    attempts = db.relationship("Attempt", back_populates="domain",
                               cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f"<Domain {self.slug}>"


class Question(db.Model):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("correct_option IN ('A','B','C','D')", name="ck_questions_correct_option"),
    )

    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domains.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, nullable=False)
    option_b = db.Column(db.Text, nullable=False)
    option_c = db.Column(db.Text, nullable=False)
    option_d = db.Column(db.Text, nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)

    domain = db.relationship("Domain", back_populates="questions")

    @property
    def options(self):
        return {"A": self.option_a, "B": self.option_b, "C": self.option_c, "D": self.option_d}

    def __repr__(self):
        return f"<Question {self.id}>"


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domains.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    time_taken = db.Column(db.Integer, nullable=False)          # seconds
    answers = db.Column(db.JSON, nullable=False)                 # [{qid, chosen, correct}, ...]
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    student = db.relationship("Student", back_populates="attempts")
    domain = db.relationship("Domain", back_populates="attempts")

    def __repr__(self):
        return f"<Attempt {self.id} {self.score}/{self.total}>"


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------
def _check_schema():
    """Stop with a clear message if the database file was created by an older version of the app."""
    columns = {c["name"] for c in inspect(db.engine).get_columns("students")}
    if "email" in columns or "phone" in columns:
        raise SystemExit(
            "\nThe database file was created by an older version (with email/phone).\n"
            "Delete instance/skilltest.db (export CSVs first if you need the old data) "
            "and start the app again.\n")


def seed_database(domains_data, admin_email, admin_password):
    """
    Create tables, insert any technologies that don't exist yet (with their
    questions) and create the default admin. Safe to run on every start.
    """
    db.create_all()
    _check_schema()

    existing = {d.slug: d for d in db.session.scalars(select(Domain))}
    rng = random.Random(2026)  # fixed seed -> reproducible option order
    letters = ["A", "B", "C", "D"]

    for order, data in enumerate(domains_data):
        domain = existing.get(data["slug"])
        if domain:
            domain.sort_order = order
            continue

        domain = Domain(slug=data["slug"], name=data["name"], short_name=data["short"],
                        branch=data["branch"], description=data["description"], sort_order=order)
        for text_, options, correct_idx in data["questions"]:
            correct_text = options[correct_idx]
            shuffled = options[:]
            rng.shuffle(shuffled)
            domain.questions.append(Question(
                question=text_,
                option_a=shuffled[0], option_b=shuffled[1],
                option_c=shuffled[2], option_d=shuffled[3],
                correct_option=letters[shuffled.index(correct_text)],
            ))
        db.session.add(domain)

    email = admin_email.lower()
    if not db.session.scalar(select(Admin).filter_by(email=email)):
        db.session.add(Admin(email=email, password_hash=generate_password_hash(admin_password)))

    db.session.commit()
