import secrets
import sqlite3

from db import SessionLocal
from models import Organization, User


class LastAdminError(Exception):
    """Raised when an action would leave an organization with no admin."""


def create_organizations_table():
    # DDL stays raw for now; the Organization ORM model maps onto this table.
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            invite_code TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Billing columns (additive) — existing workspaces start on the free plan.
    existing = [row[1] for row in cursor.execute("PRAGMA table_info(organizations)")]
    for column, ddl in (
        ("plan", "ALTER TABLE organizations ADD COLUMN plan TEXT DEFAULT 'free'"),
        ("subscription_status", "ALTER TABLE organizations ADD COLUMN subscription_status TEXT"),
        ("stripe_customer_id", "ALTER TABLE organizations ADD COLUMN stripe_customer_id TEXT"),
        ("stripe_subscription_id", "ALTER TABLE organizations ADD COLUMN stripe_subscription_id TEXT"),
        ("current_period_end", "ALTER TABLE organizations ADD COLUMN current_period_end TEXT"),
    ):
        if column not in existing:
            cursor.execute(ddl)

    connection.commit()
    connection.close()


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


def backfill_user_orgs():
    """Migration: every user created before organizations existed gets their
    own personal org, so no one is left without a tenant. Runs once — after
    the first pass, no users have a NULL org_id. (Raw SQL migration.)
    """
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    orphan_users = cursor.execute(
        "SELECT id, email FROM users WHERE org_id IS NULL"
    ).fetchall()

    for user_id, email in orphan_users:
        invite_code = secrets.token_urlsafe(8)
        cursor.execute(
            "INSERT INTO organizations (name, invite_code) VALUES (?, ?)",
            (f"{email}'s Organization", invite_code),
        )
        new_org_id = cursor.lastrowid
        cursor.execute(
            "UPDATE users SET org_id = ? WHERE id = ?",
            (new_org_id, user_id),
        )

    connection.commit()
    connection.close()
