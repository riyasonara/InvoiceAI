import secrets
import sqlite3


def create_organizations_table():
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


def create_organization(name):
    """Create a new organization with a random, shareable invite code."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    invite_code = secrets.token_urlsafe(8)
    cursor.execute(
        "INSERT INTO organizations (name, invite_code) VALUES (?, ?)",
        (name, invite_code),
    )

    connection.commit()
    org_id = cursor.lastrowid
    connection.close()

    return {"id": org_id, "name": name, "invite_code": invite_code}


def get_organization_by_id(org_id):
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, name, invite_code FROM organizations WHERE id = ?",
        (org_id,),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return {"id": row[0], "name": row[1], "invite_code": row[2]}


def get_organization_by_invite_code(invite_code):
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, name, invite_code FROM organizations WHERE invite_code = ?",
        (invite_code,),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return {"id": row[0], "name": row[1], "invite_code": row[2]}


def backfill_user_orgs():
    """Migration: every user created before organizations existed gets their
    own personal org, so no one is left without a tenant. Runs once — after
    the first pass, no users have a NULL org_id.
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
