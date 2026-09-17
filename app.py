"""
YoungMinds Skill Test Portal
Flask + SQLAlchemy application for engineering students (CSE / ECE / EEE).

Student flow : open link -> enter details -> choose technology -> 15 MCQs -> score
Admin flow   : log in -> view all students and scores -> export CSV
"""

import csv
import io
import random
import re
import secrets
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, session, url_for)
from sqlalchemy import func, select
from werkzeug.security import check_password_hash

from config import Config
from models import Admin, Attempt, Domain, Question, Student, db, seed_database
from questions import BRANCHES, DOMAINS

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
QUESTIONS_PER_TEST = Config.QUESTIONS_PER_TEST
TEST_DURATION_SECONDS = Config.TEST_DURATION_SECONDS
PASS_PERCENTAGE = Config.PASS_PERCENTAGE

# Department -> branch whose technologies are recommended first
DEPARTMENTS = {
    "CSE": "CSE",
    "CSE (AI & ML)": "CSE",
    "CSE (Data Science)": "CSE",
    "CSE (Cyber Security)": "CSE",
    "IT": "CSE",
    "MCA": "CSE",
    "ECE": "ECE",
    "EEE": "EEE",
}
YEARS = ["1st Year", "2nd Year", "3rd Year", "4th Year", "Passed Out"]

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


@app.cli.command("init-db")
def init_db_command():
    """Create tables and seed data:  flask --app app init-db"""
    seed_database(DOMAINS, Config.ADMIN_EMAIL, Config.ADMIN_PASSWORD)
    print("Database initialised.")


@app.cli.command("reset-db")
def reset_db_command():
    """Delete ALL data and recreate tables:  flask --app app reset-db"""
    if input("This deletes all students and results. Type YES to continue: ") != "YES":
        print("Cancelled.")
        return
    db.drop_all()
    seed_database(DOMAINS, Config.ADMIN_EMAIL, Config.ADMIN_PASSWORD)
    print("Database reset.")


# --------------------------------------------------------------------------
# CSRF protection (lightweight, session-based)
# --------------------------------------------------------------------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.context_processor
def inject_globals():
    return {"csrf_token": csrf_token, "current_year": datetime.now().year}


@app.before_request
def verify_csrf():
    if request.method == "POST":
        token = request.form.get("_csrf")
        if not token or token != session.get("_csrf"):
            abort(400, description="Your session expired. Reload the page and try again.")


# --------------------------------------------------------------------------
# Access helpers
# --------------------------------------------------------------------------
def student_required(view):
    """Student must have submitted their details in this browser session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"):
            flash("Enter your details to start a test.", "info")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def current_student():
    sid = session.get("student_id")
    return db.session.get(Student, sid) if sid else None


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{2,119}$")


def validate_details(form):
    data = {
        "name": " ".join(form.get("name", "").split()),
        "department": form.get("department", ""),
        "year": form.get("year", ""),
    }
    errors = {}
    if not NAME_RE.match(data["name"]):
        errors["name"] = "Enter your full name using letters only (at least 3 characters)."
    if data["department"] not in DEPARTMENTS:
        errors["department"] = "Select your department."
    if data["year"] not in YEARS:
        errors["year"] = "Select your year of study."
    return data, errors


def save_student(data):
    """
    Update the student already linked to this browser session (when they edit their details),
    otherwise create a new student record.
    """
    student = current_student()
    if student is None:
        student = Student(**data)
        db.session.add(student)
    else:
        for key, value in data.items():
            setattr(student, key, value)
    db.session.commit()
    return student


# --------------------------------------------------------------------------
# Student flow
# --------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    errors = {}
    if request.method == "POST":
        data, errors = validate_details(request.form)
        if not errors:
            student = save_student(data)
            if session.get("student_id") != student.id:
                session.pop("quiz", None)
                session["my_attempts"] = []
            session["student_id"] = student.id
            session["student_name"] = student.name
            return redirect(url_for("technologies"))
        form = data
    else:
        student = current_student()
        form = ({"name": student.name, "department": student.department, "year": student.year}
                if student else {})

    return render_template("index.html", form=form, errors=errors,
                           departments=DEPARTMENTS.keys(), years=YEARS,
                           qcount=QUESTIONS_PER_TEST, minutes=TEST_DURATION_SECONDS // 60)


@app.route("/start-over")
def start_over():
    for key in ("student_id", "student_name", "quiz", "my_attempts"):
        session.pop(key, None)
    return redirect(url_for("index"))


@app.route("/technologies")
@student_required
def technologies():
    student = current_student()
    if student is None:
        return redirect(url_for("start_over"))

    domains = db.session.scalars(select(Domain).order_by(Domain.sort_order)).all()
    my_branch = DEPARTMENTS.get(student.department, "CSE")
    recommended = [d for d in domains if d.branch == my_branch]
    others = [d for d in domains if d.branch != my_branch]

    recent = []
    attempt_ids = session.get("my_attempts", [])
    if attempt_ids:
        recent = db.session.execute(
            select(Attempt.id, Attempt.score, Attempt.total, Attempt.percentage,
                   Attempt.submitted_at, Attempt.domain_id, Domain.short_name)
            .join(Domain, Attempt.domain_id == Domain.id)
            .where(Attempt.id.in_(attempt_ids), Attempt.student_id == student.id)
            .order_by(Attempt.id.desc())
        ).all()

    best = {}
    for a in recent:
        best[a.domain_id] = max(best.get(a.domain_id, 0), a.percentage)

    return render_template("technologies.html", student=student, recommended=recommended,
                           others=others, recent=recent, best=best, branches=BRANCHES,
                           my_branch=my_branch, minutes=TEST_DURATION_SECONDS // 60,
                           qcount=QUESTIONS_PER_TEST)


def get_domain_or_404(slug):
    return db.first_or_404(select(Domain).filter_by(slug=slug))


@app.route("/test/<slug>")
@student_required
def quiz(slug):
    domain = get_domain_or_404(slug)
    now = datetime.now().timestamp()

    # Resume an in-progress test for this technology (e.g. after a page refresh)
    active = session.get("quiz")
    if not (active and active["slug"] == slug and now - active["started"] < TEST_DURATION_SECONDS):
        ids = db.session.scalars(select(Question.id).where(Question.domain_id == domain.id)).all()
        if len(ids) < QUESTIONS_PER_TEST:
            flash("This test is not ready yet. Choose another technology.", "error")
            return redirect(url_for("technologies"))
        active = {"slug": slug, "qids": random.sample(list(ids), QUESTIONS_PER_TEST), "started": now}
        session["quiz"] = active

    rows = {q.id: q for q in db.session.scalars(select(Question).where(Question.id.in_(active["qids"])))}
    questions = [rows[qid] for qid in active["qids"] if qid in rows]
    remaining = max(0, int(TEST_DURATION_SECONDS - (now - active["started"])))
    return render_template("quiz.html", domain=domain, questions=questions, remaining=remaining)


@app.route("/test/<slug>/submit", methods=["POST"])
@student_required
def submit_quiz(slug):
    domain = get_domain_or_404(slug)
    active = session.get("quiz")
    if not active or active["slug"] != slug:
        flash("This test session has ended. Start the test again.", "error")
        return redirect(url_for("technologies"))

    qids = active["qids"]
    correct_map = dict(db.session.execute(
        select(Question.id, Question.correct_option).where(Question.id.in_(qids))).all())

    answers, score = [], 0
    for qid in qids:
        chosen = request.form.get(f"q{qid}", "").upper()
        chosen = chosen if chosen in ("A", "B", "C", "D") else ""
        correct = correct_map[qid]
        score += int(chosen == correct)
        answers.append({"qid": qid, "chosen": chosen, "correct": correct})

    total = len(qids)
    attempt = Attempt(
        student_id=session["student_id"],
        domain_id=domain.id,
        score=score,
        total=total,
        percentage=round(score * 100.0 / total, 2),
        time_taken=min(int(datetime.now().timestamp() - active["started"]), TEST_DURATION_SECONDS),
        answers=answers,
    )
    db.session.add(attempt)
    db.session.commit()

    session.pop("quiz", None)
    session["my_attempts"] = (session.get("my_attempts") or []) + [attempt.id]
    return redirect(url_for("result", attempt_id=attempt.id))


@app.route("/result/<int:attempt_id>")
@student_required
def result(attempt_id):
    # Without accounts, a student can only view results submitted from their own browser session
    if attempt_id not in session.get("my_attempts", []):
        abort(404)
    attempt = db.session.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != session["student_id"]:
        abort(404)

    qids = [a["qid"] for a in attempt.answers]
    qrows = {q.id: q for q in db.session.scalars(select(Question).where(Question.id.in_(qids)))}

    review = [
        {"question": qrows[a["qid"]].question, "options": qrows[a["qid"]].options,
         "chosen": a["chosen"], "correct": a["correct"]}
        for a in attempt.answers if a["qid"] in qrows
    ]
    unanswered = sum(1 for a in attempt.answers if not a["chosen"])
    passed = attempt.percentage >= PASS_PERCENTAGE
    return render_template("result.html", attempt=attempt, review=review,
                           unanswered=unanswered, passed=passed, pass_mark=PASS_PERCENTAGE)


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin = db.session.scalar(select(Admin).filter_by(email=email))
        if admin and check_password_hash(admin.password_hash, password):
            session["admin_id"] = admin.id
            session["admin_email"] = admin.email
            return redirect(url_for("admin_dashboard"))
        flash("Admin email or password is incorrect.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_email", None)
    return redirect(url_for("admin_login"))


def apply_filters(stmt, include_domain=True):
    """Add search/department/year/technology filters from the query string to a SELECT."""
    q = request.args.get("q", "").strip()
    department = request.args.get("department", "")
    year = request.args.get("year", "")
    domain = request.args.get("domain", "") if include_domain else ""
    filters = {"q": q,
               "department": department if department in DEPARTMENTS else "",
               "year": year if year in YEARS else ""}

    if q:
        stmt = stmt.where(Student.name.ilike(f"%{q}%"))
    if filters["department"]:
        stmt = stmt.where(Student.department == department)
    if filters["year"]:
        stmt = stmt.where(Student.year == year)
    if include_domain:
        filters["domain"] = domain
        if domain:
            stmt = stmt.where(Domain.slug == domain)
    return stmt, filters


def attempts_statement():
    return (
        select(Attempt.id, Attempt.score, Attempt.total, Attempt.percentage,
               Attempt.time_taken, Attempt.submitted_at,
               Student.name, Student.department, Student.year,
               Domain.name.label("domain_name"), Domain.short_name, Domain.branch)
        .select_from(Attempt)
        .join(Student, Attempt.student_id == Student.id)
        .join(Domain, Attempt.domain_id == Domain.id)
        .order_by(Attempt.id.desc())
    )


def students_statement():
    return (
        select(Student.id, Student.name, Student.department, Student.year, Student.created_at, Student.updated_at,
               func.count(Attempt.id).label("attempts"),
               func.max(Attempt.percentage).label("best"),
               func.round(func.avg(Attempt.percentage), 2).label("average"))
        .outerjoin(Attempt, Attempt.student_id == Student.id)
        .group_by(Student.id)
        .order_by(Student.updated_at.desc())
    )


@app.route("/admin")
@admin_required
def admin_dashboard():
    stmt, filters = apply_filters(attempts_statement())
    attempts = db.session.execute(stmt).all()

    summary = {
        "students": db.session.scalar(select(func.count(Student.id))),
        "attempts": db.session.scalar(select(func.count(Attempt.id))),
        "average": db.session.scalar(select(func.round(func.avg(Attempt.percentage), 1))),
        "passed": db.session.scalar(select(func.count(Attempt.id)).where(Attempt.percentage >= PASS_PERCENTAGE)),
    }
    by_domain = db.session.execute(
        select(Domain.short_name, Domain.branch,
               func.count(Attempt.id).label("attempts"),
               func.round(func.avg(Attempt.percentage), 1).label("average"))
        .outerjoin(Attempt, Attempt.domain_id == Domain.id)
        .group_by(Domain.id)
        .order_by(Domain.sort_order)
    ).all()
    domains = db.session.execute(select(Domain.slug, Domain.short_name).order_by(Domain.sort_order)).all()

    return render_template("admin/dashboard.html", attempts=attempts, summary=summary,
                           by_domain=by_domain, domains=domains, departments=DEPARTMENTS.keys(),
                           years=YEARS, filters=filters, pass_mark=PASS_PERCENTAGE)


@app.route("/admin/students")
@admin_required
def admin_students():
    stmt, filters = apply_filters(students_statement(), include_domain=False)
    students = db.session.execute(stmt).all()
    return render_template("admin/students.html", students=students, departments=DEPARTMENTS.keys(),
                           years=YEARS, filters=filters)


def csv_safe(value):
    """Prevent spreadsheet formula injection when the CSV is opened in Excel."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def csv_response(filename, header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow([csv_safe(v) for v in row])
    return Response("\ufeff" + buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/admin/export/results.csv")
@admin_required
def export_results():
    stmt, _ = apply_filters(attempts_statement())
    rows = db.session.execute(stmt).all()
    header = ["Attempt ID", "Student Name", "Department", "Year",
              "Branch", "Technology", "Score", "Total Questions", "Percentage", "Result",
              "Time Taken (mm:ss)", "Submitted On"]
    data = [
        [r.id, r.name, r.department, r.year, r.branch, r.domain_name,
         r.score, r.total, r.percentage,
         "Pass" if r.percentage >= PASS_PERCENTAGE else "Needs improvement",
         mmss(r.time_taken), r.submitted_at]
        for r in rows
    ]
    return csv_response(f"youngminds_test_results_{datetime.now():%Y%m%d_%H%M}.csv", header, data)


@app.route("/admin/export/students.csv")
@admin_required
def export_students():
    stmt, _ = apply_filters(students_statement(), include_domain=False)
    rows = db.session.execute(stmt).all()
    header = ["Student ID", "Name", "Department", "Year",
              "First Visit", "Last Updated", "Tests Taken", "Best %", "Average %"]
    data = [[r.id, r.name, r.department, r.year, r.created_at,
             r.updated_at, r.attempts, r.best, r.average] for r in rows]
    return csv_response(f"youngminds_students_{datetime.now():%Y%m%d_%H%M}.csv", header, data)


# --------------------------------------------------------------------------
# Template filters & error pages
# --------------------------------------------------------------------------
@app.template_filter("mmss")
def mmss(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


@app.template_filter("pct")
def pct(value):
    if value is None:
        return "–"
    value = float(value)
    return f"{value:.0f}%" if value.is_integer() else f"{value:.1f}%"


@app.template_filter("dt")
def dt(value, fmt="%d %b %Y, %I:%M %p"):
    return value.strftime(fmt) if value else ""


@app.errorhandler(400)
@app.errorhandler(404)
def handle_error(err):
    return render_template("error.html", code=err.code, message=err.description), err.code


# Create tables and seed data on startup (safe to run repeatedly)
with app.app_context():
    seed_database(DOMAINS, Config.ADMIN_EMAIL, Config.ADMIN_PASSWORD)

if __name__ == "__main__":
    app.run(debug=True)
