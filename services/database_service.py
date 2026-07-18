import sqlite3

def create_database():
    connection = sqlite3.connect("invoice.db")

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor TEXT,
            invoice_number TEXT,
            invoice_date TEXT,
            gst REAL,
            total REAL
        )
    """)

    # An invoice is identified by (vendor, invoice_number) together.
    # This unique index makes the database itself reject duplicates,
    # and gives save_invoice() a conflict target to upsert against.
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_vendor_number
        ON invoices (vendor, invoice_number)
    """)

    connection.commit()
    connection.close()


def save_invoice(invoice):
    connection = sqlite3.connect("invoice.db")

    cursor = connection.cursor()

    # UPSERT: try to insert; if (vendor, invoice_number) already exists,
    # update that existing row instead of creating a duplicate.
    # "excluded" refers to the values we tried to insert.
    cursor.execute("""
        INSERT INTO invoices (
            vendor,
            invoice_number,
            invoice_date,
            gst,
            total
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (vendor, invoice_number)
        DO UPDATE SET
            invoice_date = excluded.invoice_date,
            gst = excluded.gst,
            total = excluded.total
    """, (
        invoice["vendor"],
        invoice["invoice_number"],
        invoice["invoice_date"],
        invoice["gst"],
        invoice["total"]
    ))

    connection.commit()
    connection.close()


def get_all_invoices():
    connection = sqlite3.connect("invoice.db")

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM invoices")

    rows = cursor.fetchall()

    connection.close()

    invoices = []
    for row in rows:
        invoice = {
            "id": row[0],
            "vendor": row[1],
            "invoice_number": row[2],
            "invoice_date": row[3],
            "gst": row[4],
            "total": row[5]
        }
        invoices.append(invoice)

    return invoices