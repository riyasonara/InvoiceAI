from sqlalchemy import func, or_, distinct

from db import SessionLocal
from models import Invoice


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
        "reviewed": inv.reviewed,
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
            existing.reviewed = False   # figures changed → needs re-review
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


def get_all_invoices(org_id, search=None, status=None, from_date=None, to_date=None, reviewed=None):
    """This org's invoices, newest first, with optional search / status /
    invoice-date-range / reviewed filters.
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
        if reviewed is not None:
            query = query.filter(Invoice.reviewed == reviewed)

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


def update_invoice(org_id, invoice_id, **fields):
    """Update an invoice's editable fields, scoped to the org.

    Only the fields passed (and not None) are changed — partial update. The
    caller decides which are editable; this just applies what it's given.
    Editing vendor/invoice_number can collide with the (org, vendor, number)
    unique index, which raises IntegrityError for the web layer to turn into
    a 409. Returns True if the invoice existed, False otherwise.
    """
    editable = ("status", "due_date", "vendor", "invoice_number",
                "invoice_date", "gst", "total", "reviewed")
    db = SessionLocal()
    try:
        inv = db.query(Invoice).filter_by(org_id=org_id, id=invoice_id).first()
        if inv is None:
            return False
        for name in editable:
            if name in fields and fields[name] is not None:
                setattr(inv, name, fields[name])
        db.commit()
        return True
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
        needs_review = db.query(func.count()).filter(org_filter, Invoice.reviewed.is_(False)).scalar()

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
            "needs_review": needs_review,
            "monthly_trend": monthly_trend,
            "status_distribution": status_distribution,
            "top_suppliers": top_suppliers,
        }
    finally:
        db.close()
