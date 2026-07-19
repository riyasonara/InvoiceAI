import sqlite3


def create_database():
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    # Fresh installs get both user_id (who uploaded it) and org_id (the tenant
    # that owns it) from the start.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            org_id INTEGER,
            vendor TEXT,
            invoice_number TEXT,
            invoice_date TEXT,
            gst REAL,
            total REAL
        )
    """)

    # Migration: add org_id if the table predates organizations.
    existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(invoices)")]
    if "org_id" not in existing_columns:
        cursor.execute("ALTER TABLE invoices ADD COLUMN org_id INTEGER")

    # Backfill each invoice's org_id from the org of the user who uploaded it.
    cursor.execute("""
        UPDATE invoices
        SET org_id = (SELECT org_id FROM users WHERE users.id = invoices.user_id)
        WHERE org_id IS NULL
    """)

    # Uniqueness is now PER ORGANIZATION: teammates can't create duplicates of
    # the same invoice within their org. Replace the old per-user index.
    cursor.execute("DROP INDEX IF EXISTS idx_invoices_user_vendor_number")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_org_vendor_number
        ON invoices (org_id, vendor, invoice_number)
    """)

    connection.commit()
    connection.close()


def save_invoice(invoice, user_id, org_id):
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    # UPSERT scoped to the organization: conflict target is
    # (org_id, vendor, invoice_number). user_id records the latest uploader.
    cursor.execute("""
        INSERT INTO invoices (
            user_id,
            org_id,
            vendor,
            invoice_number,
            invoice_date,
            gst,
            total
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (org_id, vendor, invoice_number)
        DO UPDATE SET
            invoice_date = excluded.invoice_date,
            gst = excluded.gst,
            total = excluded.total,
            user_id = excluded.user_id
    """, (
        user_id,
        org_id,
        invoice["vendor"],
        invoice["invoice_number"],
        invoice["invoice_date"],
        invoice["gst"],
        invoice["total"]
    ))

    connection.commit()
    connection.close()


def get_all_invoices(org_id):
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    # Return every invoice belonging to THIS organization, newest first.
    cursor.execute("""
        SELECT id, vendor, invoice_number, invoice_date, gst, total
        FROM invoices
        WHERE org_id = ?
        ORDER BY id DESC
    """, (org_id,))
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
