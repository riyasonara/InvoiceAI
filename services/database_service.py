import sqlite3

from sqlalchemy import func, or_, distinct

from db import SessionLocal
from models import Invoice


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


def _invoice_to_dict(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "vendor": inv.vendor,
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date,
        "gst": inv.gst,
        "total": inv.total,
        "status": inv.status,
        "due_date": inv.due_date,
        "created_at": inv.created_at,
    }


def save_invoice(invoice, user_id, org_id):
    """UPSERT scoped to the org: update the existing (org, vendor, number) row
    or insert a new one. Get-or-create keeps this dialect-agnostic (works on
    Postgres too). New rows leave created_at NULL so the DB trigger stamps it.
    """
    db = SessionLocal()
    try:
        existing = (
            db.query(Invoice)
            .filter_by(org_id=org_id, vendor=invoice["vendor"], invoice_number=invoice["invoice_number"])
            .first()
        )
        if existing is not None:
            existing.invoice_date = invoice["invoice_date"]
            existing.gst = invoice["gst"]
            existing.total = invoice["total"]
            existing.user_id = user_id  # record the latest uploader
        else:
            db.add(Invoice(
                user_id=user_id,
                org_id=org_id,
                vendor=invoice["vendor"],
                invoice_number=invoice["invoice_number"],
                invoice_date=invoice["invoice_date"],
                gst=invoice["gst"],
                total=invoice["total"],
            ))
        db.commit()
    finally:
        db.close()


def get_all_invoices(org_id, search=None, status=None, from_date=None, to_date=None):
    """This org's invoices, newest first, with optional search / status /
    invoice-date-range filters.
    """
    db = SessionLocal()
    try:
        query = db.query(Invoice).filter(Invoice.org_id == org_id)
        if search:
            like = f"%{search}%"
            query = query.filter(or_(Invoice.vendor.like(like), Invoice.invoice_number.like(like)))
        if status:
            query = query.filter(Invoice.status == status)
        if from_date:
            query = query.filter(Invoice.invoice_date >= from_date)
        if to_date:
            query = query.filter(Invoice.invoice_date <= to_date)

        rows = query.order_by(Invoice.id.desc()).all()
        return [_invoice_to_dict(inv) for inv in rows]
    finally:
        db.close()


def get_invoice_id(org_id, vendor, invoice_number):
    """Look up an invoice's id by its unique key (used to link email attachments)."""
    db = SessionLocal()
    try:
        inv = db.query(Invoice).filter_by(
            org_id=org_id, vendor=vendor, invoice_number=invoice_number,
        ).first()
        return inv.id if inv else None
    finally:
        db.close()


def get_invoice_by_id(org_id, invoice_id):
    """One invoice, scoped to the org (so no one reads another org's data)."""
    db = SessionLocal()
    try:
        inv = db.query(Invoice).filter_by(org_id=org_id, id=invoice_id).first()
        return _invoice_to_dict(inv) if inv else None
    finally:
        db.close()


def update_invoice(org_id, invoice_id, status=None, due_date=None):
    """Update mutable dashboard fields on an invoice, scoped to the org."""
    db = SessionLocal()
    try:
        inv = db.query(Invoice).filter_by(org_id=org_id, id=invoice_id).first()
        if inv is not None:
            if status is not None:
                inv.status = status
            if due_date is not None:
                inv.due_date = due_date
            db.commit()
    finally:
        db.close()


def get_dashboard_summary(org_id):
    """Aggregate everything the dashboard cards and charts need, in one call."""
    db = SessionLocal()
    try:
        org_filter = Invoice.org_id == org_id

        total_invoices = db.query(func.count()).filter(org_filter).scalar()
        total_suppliers = (
            db.query(func.count(distinct(Invoice.vendor)))
            .filter(org_filter, Invoice.vendor.isnot(None))
            .scalar()
        )
        total_amount = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(org_filter).scalar()

        def amount_for(status_value):
            return (
                db.query(func.coalesce(func.sum(Invoice.total), 0))
                .filter(org_filter, Invoice.status == status_value)
                .scalar()
            )

        paid_amount = amount_for("paid")
        pending_amount = amount_for("pending")
        unpaid_amount = amount_for("unpaid")
        unpaid_count = db.query(func.count()).filter(org_filter, Invoice.status == "unpaid").scalar()

        # Monthly trend + spending, grouped by the invoice's own month (YYYY-MM).
        month = func.substr(Invoice.invoice_date, 1, 7)
        monthly_rows = (
            db.query(month, func.count(), func.coalesce(func.sum(Invoice.total), 0))
            .filter(org_filter, Invoice.invoice_date.isnot(None), Invoice.invoice_date != "")
            .group_by(month).order_by(month).all()
        )
        monthly_trend = [{"month": m, "count": c, "amount": a} for (m, c, a) in monthly_rows]

        # Status distribution (for the donut chart).
        dist_rows = (
            db.query(func.coalesce(Invoice.status, "pending"), func.count())
            .filter(org_filter).group_by(Invoice.status).all()
        )
        status_distribution = [{"status": s, "count": c} for (s, c) in dist_rows]

        # Top suppliers by total spend.
        top_rows = (
            db.query(Invoice.vendor, func.count(), func.coalesce(func.sum(Invoice.total), 0))
            .filter(org_filter, Invoice.vendor.isnot(None))
            .group_by(Invoice.vendor).order_by(func.sum(Invoice.total).desc()).limit(5).all()
        )
        top_suppliers = [{"vendor": v, "count": c, "amount": a} for (v, c, a) in top_rows]

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
    finally:
        db.close()
