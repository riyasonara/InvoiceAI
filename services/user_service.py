import sqlite3


def create_users_table():
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


def create_user(email, hashed_password, org_id):
    """Insert a new user into an organization. Raises sqlite3.IntegrityError if
    the email is taken (the UNIQUE constraint), handled by the register endpoint.
    """
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO users (email, hashed_password, org_id) VALUES (?, ?, ?)",
        (email, hashed_password, org_id),
    )

    connection.commit()
    user_id = cursor.lastrowid
    connection.close()

    return {"id": user_id, "email": email, "org_id": org_id}


def get_user_by_email(email):
    """Return the user dict (including hashed_password) or None if not found."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, email, hashed_password, org_id FROM users WHERE email = ?",
        (email,),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return {"id": row[0], "email": row[1], "hashed_password": row[2], "org_id": row[3]}


def get_user_by_id(user_id):
    """Return the user dict for a given id, or None if not found."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, email, hashed_password, org_id FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return {"id": row[0], "email": row[1], "hashed_password": row[2], "org_id": row[3]}
