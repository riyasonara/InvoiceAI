from sqlalchemy.exc import IntegrityError

from db import SessionLocal
from models import User


def _to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "hashed_password": user.hashed_password,
        "org_id": user.org_id,
        "role": user.role,
    }


def create_user(email, hashed_password, org_id, role="member"):
    """Insert a new user into an organization.

    A duplicate email violates the UNIQUE constraint and raises SQLAlchemy's
    IntegrityError, which the register endpoint catches and turns into a 409.
    """
    db = SessionLocal()
    try:
        user = User(email=email, hashed_password=hashed_password, org_id=org_id, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"id": user.id, "email": user.email, "org_id": user.org_id, "role": user.role}
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
