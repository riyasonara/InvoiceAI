import sqlite3

from sqlalchemy.exc import IntegrityError

from db import SessionLocal
from models import User


def create_users_table():
    # Schema creation + migration still owns the DDL (raw SQL) for now.
    # The ORM models in models.py map onto exactly this table.
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            org_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Migration for databases created before organizations existed: add the
    # org_id column if it's missing (backfill_user_orgs then fills it in).
    existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)")]
    if "org_id" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN org_id INTEGER")

    connection.commit()
    connection.close()


def _to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "hashed_password": user.hashed_password,
        "org_id": user.org_id,
    }


def create_user(email, hashed_password, org_id):
    """Insert a new user into an organization.

    A duplicate email violates the UNIQUE constraint and raises SQLAlchemy's
    IntegrityError, which the register endpoint catches and turns into a 409.
    """
    db = SessionLocal()
    try:
        user = User(email=email, hashed_password=hashed_password, org_id=org_id)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"id": user.id, "email": user.email, "org_id": user.org_id}
    except IntegrityError:
        db.rollback()
        raise
    finally:
        db.close()


def get_user_by_email(email):
    """Return the user dict (including hashed_password) or None if not found."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        return _to_dict(user) if user else None
    finally:
        db.close()


def get_user_by_id(user_id):
    """Return the user dict for a given id, or None if not found."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        return _to_dict(user) if user else None
    finally:
        db.close()
