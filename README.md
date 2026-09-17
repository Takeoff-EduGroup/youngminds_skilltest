# YoungMinds Skill Test Portal

MCQ skill-test web application for engineering students.

**Stack:** Flask (backend) · SQLAlchemy ORM (database) · HTML, CSS, JavaScript (frontend)

All data is stored through SQLAlchemy in one file, `instance/skilltest.db`, which is created automatically.
No database server, username or password is needed.

## How it works
**Students (no registration or login)**
1. Open the link and enter name, department and year of study (all required)
2. Choose a technology (technologies for their department are shown first)
3. Answer 15 MCQs within 15 minutes and see the score with a full answer review

**Admin** (`/admin/login`)
- Test results with student details; search by name, filter by department, year and technology
- Students page with tests taken, best and average score
- Export results or students to CSV

Each time a student fills the details form, a new student record is created. If they click
**Edit my details** during the same visit, their existing record is updated instead, and their scores stay linked.

## Technologies (15 questions each)
| Branch | Technologies |
|--------|--------------|
| CSE    | AI/ML, Data Science, Computer Science, Python Full Stack, Java Full Stack, Data Analysis, MERN Stack, Web Development |
| ECE    | MATLAB, VLSI, Embedded Systems |
| EEE    | Simulink |

## Run it
```bash
# 1. Create and activate an environment (conda or venv)
conda create -n skilltest python=3.11 -y
conda activate skilltest
#   or:  python -m venv venv  then  venv\Scripts\activate  (Windows) / source venv/bin/activate

# 2. Install packages
pip install -r requirements.txt

# 3. Start the app
python app.py
```
- Student page: http://127.0.0.1:5000
- Admin panel: http://127.0.0.1:5000/admin/login (`admin@youngminds.in` / `Admin@123`)

To let students on the same network use it, change the last line of `app.py` to
`app.run(host="0.0.0.0", port=5000)` and share `http://<your-computer-IP>:5000`.

## Settings
Edit `config.py`:
- `SECRET_KEY` - change to a long random string
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` - admin login (applied when the admin account is first created)
- `QUESTIONS_PER_TEST`, `TEST_DURATION_SECONDS`, `PASS_PERCENTAGE` - test rules

## Project structure
```
app.py              Flask routes, scoring, admin views, CSV export
models.py           SQLAlchemy models and data seeding
config.py           Settings
questions.py        Question bank
instance/           skilltest.db (created automatically)
templates/          HTML pages (student + admin)
static/css/         Stylesheet
static/js/          main.js (form validation), quiz.js (quiz, timer)
static/images/      Logo
```

## SQLAlchemy models (`models.py`)
| Model | Table | Fields |
|-------|-------|--------|
| `Student`  | students  | name, department, year, created_at, updated_at |
| `Admin`    | admins    | email, password_hash |
| `Domain`   | domains   | slug, name, short_name, branch, description |
| `Question` | questions | domain_id, question, option_a-d, correct_option |
| `Attempt`  | attempts  | student_id, domain_id, score, total, percentage, time_taken, answers, submitted_at |

Relationships: `Student.attempts`, `Domain.questions`, `Attempt.student`, `Attempt.domain`.

## Useful commands
```bash
flask --app app init-db      # create tables and load questions (also happens on startup)
flask --app app reset-db     # delete ALL data and start fresh (asks for confirmation)
flask --app app shell        # Python shell with the app loaded
```
Example queries in the shell:
```python
from models import db, Student, Attempt, Domain
from sqlalchemy import select

db.session.scalars(select(Student).where(Student.department == "ECE")).all()

student = db.session.scalar(select(Student).filter_by(name="Anjali Reddy"))
[(a.domain.short_name, a.score) for a in student.attempts]
```
Set the environment variable `SQL_ECHO=1` before starting to print every SQL query SQLAlchemy runs.

## Adding or changing questions
- **New technology:** add a dictionary to `DOMAINS` in `questions.py` (at least 15 questions) and restart.
  It is added automatically; existing data is untouched.
- **Changing an existing technology's questions:** edit `questions.py`, then in `flask --app app shell`:
  ```python
  from models import db, Domain
  from sqlalchemy import select
  d = db.session.scalar(select(Domain).filter_by(slug="vlsi"))
  db.session.delete(d)      # also removes its questions and past attempts
  db.session.commit()
  ```
  Restart the app and the technology is reloaded from `questions.py`.

## Upgrading from an older version
If you ran an earlier version that collected email and phone, delete `instance/skilltest.db`
(export the CSVs first if you need that data) and start the app again. The app detects the old
database and tells you if this is needed.

## Backup
Copy `instance/skilltest.db` to keep a backup of all students and results.
