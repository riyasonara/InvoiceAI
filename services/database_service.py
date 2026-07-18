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

    connection.commit()
    connection.close()


def save_invoice(invoice):
    connection = sqlite3.connect("invoice.db")

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO invoices (
            vendor,
            invoice_number,
            invoice_date,
            gst,
            total
        )
        VALUES (?, ?, ?, ?, ?)
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