import secrets

from db import SessionLocal
from models import Organization, User


class LastAdminError(Exception):
    """Raised when an action would leave an organization with no admin."""


def _to_dict(org: Organization) -> dict:
    return {"id": org.id, "name": org.name, "invite_code": org.invite_code}


def create_organization(name):
    """Create a new organization with a random, shareable invite code."""
    db = SessionLocal()
    try:
        org = Organization(name=name, invite_code=secrets.token_urlsafe(8))
        db.add(org)
        db.commit()
        db.refresh(org)
        return _to_dict(org)
    finally:
        db.close()


def get_organization_by_id(org_id):
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        return _to_dict(org) if org else None
    finally:
        db.close()


def get_organization_by_invite_code(invite_code):
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(invite_code=invite_code).first()
        return _to_dict(org) if org else None
    finally:
        db.close()


def list_members(org_id):
    """Everyone in the organization, oldest first."""
    db = SessionLocal()
    try:
        users = db.query(User).filter_by(org_id=org_id).order_by(User.id).all()
        return [
            {"id": u.id, "email": u.email, "role": u.role, "created_at": u.created_at}
            for u in users
        ]
    finally:
        db.close()


def _count_admins(db, org_id):
    return db.query(User).filter_by(org_id=org_id, role="admin").count()


def update_member_role(org_id, member_id, role):
    """Change a member's role. Refuses to demote the last admin, which would
    leave the workspace with nobody able to manage it. Returns the updated
    member, or None if they aren't in this org.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(org_id=org_id, id=member_id).first()
        if user is None:
            return None
        if user.role == "admin" and role != "admin" and _count_admins(db, org_id) <= 1:
            raise LastAdminError("This is the only admin in the workspace.")

        user.role = role
        db.commit()
        return {"id": user.id, "email": user.email, "role": user.role}
    finally:
        db.close()


def remove_member(org_id, member_id):
    """Remove a member from the organization (same last-admin protection).
    Returns True if removed, False if they aren't in this org.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(org_id=org_id, id=member_id).first()
        if user is None:
            return False
        if user.role == "admin" and _count_admins(db, org_id) <= 1:
            raise LastAdminError("This is the only admin in the workspace.")

        db.delete(user)
        db.commit()
        return True
    finally:
        db.close()


