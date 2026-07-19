import sqlite3


def create_database():
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    # Fresh installs get user_id from the start.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            vendor TEXT,
            invoice_number TEXT,
            invoice_date TEXT,
            gst REAL,
            total REAL
        )
    """)

    # Migration for databases created before user_id existed: add the column
    # if it's missing. ALTER TABLE appends it at the end, but we always select
    # columns by name, so its physical position never matters.
    existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(invoices)")]
    if "user_id" not in existing_columns:
        cursor.execute("ALTER TABLE invoices ADD COLUMN user_id INTEGER")

    # Uniqueness is now PER OWNER: the same (vendor, invoice_number) can exist
    # for different users, but not twice within one account. Replace the old
    # global index with a composite one that includes user_id.
    cursor.execute("DROP INDEX IF EXISTS idx_invoices_vendor_number")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_user_vendor_number
        ON invoices (user_id, vendor, invoice_number)
    """)

    connection.commit()
    connection.close()


def save_invoice(invoice, user_id):
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    # UPSERT scoped to the owner: the conflict target is now
    # (user_id, vendor, invoice_number).
    cursor.execute("""
        INSERT INTO invoices (
            user_id,
            vendor,
            invoice_number,
            invoice_date,
            gst,
            total
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, vendor, invoice_number)
        DO UPDATE SET
            invoice_date = excluded.invoice_date,
            gst = excluded.gst,
            total = excluded.total
    """, (
        user_id,
        invoice["vendor"],
        invoice["invoice_number"],
        invoice["invoice_date"],
        invoice["gst"],
        invoice["total"]
    ))

    connection.commit()
    connection.close()


def get_all_invoices(user_id):
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    # Explicit columns (not SELECT *) so the order is guaranteed. Return only
    # THIS user's invoices, newest first.
    cursor.execute("""
        SELECT id, vendor, invoice_number, invoice_date, gst, total
        FROM invoices
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))
    rows = cursor.fetchall()

    connection.close()

    invoices = []
    for row in rows:
        invoices.append({
            "id": row[0],
            "vendor": row[1],
            "invoice_number": row[2],
            "invoice_date": row[3],
            "gst": row[4],
            "total": row[5],
        })

    return invoices
