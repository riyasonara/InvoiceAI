import secrets
import sqlite3

from db import SessionLocal
from models import Organization


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
