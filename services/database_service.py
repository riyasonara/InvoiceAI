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
            total REAL,
            status TEXT DEFAULT 'pending',
            due_date TEXT,
            created_at TEXT
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

    # Dashboard fields (additive — extraction/upload unaffected, they rely on
    # these column DEFAULTs). status: paid/pending/unpaid. due_date: nullable.
    # created_at: when the row was inserted (upload time).
    if "status" not in existing_columns:
        cursor.execute("ALTER TABLE invoices ADD COLUMN status TEXT DEFAULT 'pending'")
    if "due_date" not in existing_columns:
        cursor.execute("ALTER TABLE invoices ADD COLUMN due_date TEXT")
    if "created_at" not in existing_columns:
        # SQLite forbids a non-constant default (CURRENT_TIMESTAMP) in
        # ALTER ADD COLUMN, so add it plain and backfill existing rows.
        cursor.execute("ALTER TABLE invoices ADD COLUMN created_at TEXT")
        cursor.execute("UPDATE invoices SET created_at = datetime('now') WHERE created_at IS NULL")

    # Stamp created_at on every new insert via a trigger, so the upload flow
    # (save_invoice) stays completely untouched.
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS invoices_set_created_at
        AFTER INSERT ON invoices
        WHEN NEW.created_at IS NULL
        BEGIN
            UPDATE invoices SET created_at = datetime('now') WHERE id = NEW.id;
        END
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


# Columns returned for invoice list/detail rows, in SELECT order.
_INVOICE_COLUMNS = [
    "id", "vendor", "invoice_number", "invoice_date",
    "gst", "total", "status", "due_date", "created_at",
]


def get_all_invoices(org_id, search=None, status=None, from_date=None, to_date=None):
    """Return this organization's invoices, newest first, with optional filters:
    - search: matches vendor OR invoice_number (case-insensitive substring)
    - status: exact status ('paid' | 'pending' | 'unpaid')
    - from_date / to_date: invoice_date range (inclusive, 'YYYY-MM-DD')
    """
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    where = ["org_id = ?"]
    params = [org_id]
    if search:
        where.append("(vendor LIKE ? OR invoice_number LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        where.append("status = ?")
        params.append(status)
    if from_date:
        where.append("invoice_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("invoice_date <= ?")
        params.append(to_date)

    cursor.execute(
        f"SELECT {', '.join(_INVOICE_COLUMNS)} FROM invoices "
        f"WHERE {' AND '.join(where)} ORDER BY id DESC",
        params,
    )
    rows = cursor.fetchall()
    connection.close()

    return [dict(zip(_INVOICE_COLUMNS, row)) for row in rows]


def get_invoice_by_id(org_id, invoice_id):
    """Return one invoice, scoped to the org (so no one reads another org's
    data), or None if it doesn't exist in this org."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    cursor.execute(
        f"SELECT {', '.join(_INVOICE_COLUMNS)} FROM invoices "
        f"WHERE org_id = ? AND id = ?",
        (org_id, invoice_id),
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return None
    return dict(zip(_INVOICE_COLUMNS, row))


def update_invoice(org_id, invoice_id, status=None, due_date=None):
    """Update mutable dashboard fields on an invoice, scoped to the org."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    sets = []
    params = []
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if due_date is not None:
        sets.append("due_date = ?")
        params.append(due_date)

    if sets:
        params.extend([org_id, invoice_id])
        cursor.execute(
            f"UPDATE invoices SET {', '.join(sets)} WHERE org_id = ? AND id = ?",
            params,
        )
        connection.commit()

    connection.close()


def get_dashboard_summary(org_id):
    """Aggregate everything the dashboard cards and charts need, in one call."""
    connection = sqlite3.connect("invoice.db")
    cursor = connection.cursor()

    def scalar(sql, params=(org_id,)):
        return cursor.execute(sql, params).fetchone()[0]

    total_invoices = scalar("SELECT COUNT(*) FROM invoices WHERE org_id = ?")
    total_suppliers = scalar(
        "SELECT COUNT(DISTINCT vendor) FROM invoices WHERE org_id = ? AND vendor IS NOT NULL"
    )
    total_amount = scalar("SELECT COALESCE(SUM(total), 0) FROM invoices WHERE org_id = ?")

    def amount_for(status):
        return cursor.execute(
            "SELECT COALESCE(SUM(total), 0) FROM invoices WHERE org_id = ? AND status = ?",
            (org_id, status),
        ).fetchone()[0]

    paid_amount = amount_for("paid")
    pending_amount = amount_for("pending")
    unpaid_amount = amount_for("unpaid")
    unpaid_count = scalar(
        "SELECT COUNT(*) FROM invoices WHERE org_id = ? AND status = 'unpaid'"
    )

    # Monthly trend + spending, grouped by the invoice's own month (YYYY-MM).
    monthly = cursor.execute("""
        SELECT substr(invoice_date, 1, 7) AS month, COUNT(*), COALESCE(SUM(total), 0)
        FROM invoices
        WHERE org_id = ? AND invoice_date IS NOT NULL AND invoice_date != ''
        GROUP BY month ORDER BY month
    """, (org_id,)).fetchall()
    monthly_trend = [{"month": m, "count": c, "amount": a} for (m, c, a) in monthly]

    # Status distribution (for the donut chart).
    dist = cursor.execute(
        "SELECT COALESCE(status, 'pending'), COUNT(*) FROM invoices WHERE org_id = ? GROUP BY status",
        (org_id,),
    ).fetchall()
    status_distribution = [{"status": s, "count": c} for (s, c) in dist]

    # Top suppliers by total spend.
    top = cursor.execute("""
        SELECT vendor, COUNT(*), COALESCE(SUM(total), 0)
        FROM invoices
        WHERE org_id = ? AND vendor IS NOT NULL
        GROUP BY vendor ORDER BY SUM(total) DESC LIMIT 5
    """, (org_id,)).fetchall()
    top_suppliers = [{"vendor": v, "count": c, "amount": a} for (v, c, a) in top]

    connection.close()

    return {
        "total_invoices": total_invoices,
        "total_suppliers": total_suppliers,
        "total_amount": total_amount,
        "paid_amount": paid_amount,
        "pending_amount": pending_amount,
        "unpaid_amount": unpaid_amount,
        "unpaid_count": unpaid_count,
        "monthly_trend": monthly_trend,
        "status_distribution": status_distribution,
        "top_suppliers": top_suppliers,
    }
