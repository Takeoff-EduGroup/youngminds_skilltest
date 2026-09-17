"""
Application settings.

Edit the values below, or set the same names as environment variables to override them.
All data is stored by SQLAlchemy in a single SQLite file: instance/skilltest.db
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Config:
    # Security - change SECRET_KEY before using the app with real students
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-to-a-long-random-string")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "skilltest.db")
    SQLALCHEMY_ECHO = os.environ.get("SQL_ECHO") == "1"   # set SQL_ECHO=1 to print every SQL query

    # Admin account (created on first run only)
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@youngminds.in")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")

    # Test rules
    QUESTIONS_PER_TEST = 15
    TEST_DURATION_SECONDS = 15 * 60
    PASS_PERCENTAGE = 60
