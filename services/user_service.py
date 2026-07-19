import sqlite3


def create_users_table():
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    connection.commit()
    connection.close()


def create_user(email, hashed_password):
    """Insert a new user. Raises sqlite3.IntegrityError if the email is taken
    (the UNIQUE constraint), which the register endpoint will handle later.
    """
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO users (email, hashed_password) VALUES (?, ?)",
        (email, hashed_password),
    )

    connection.commit()
    user_id = cursor.lastrowid
    connection.close()

    return {"id": user_id, "email": email}


def get_user_by_email(email):
    """Return the user dict (including hashed_password) or None if not found."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, email, hashed_password FROM users WHERE email = ?",
        (email,),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return {"id": row[0], "email": row[1], "hashed_password": row[2]}


def get_user_by_id(user_id):
    """Return the user dict for a given id, or None if not found."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id, email, hashed_password FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None

    return {"id": row[0], "email": row[1], "hashed_password": row[2]}
