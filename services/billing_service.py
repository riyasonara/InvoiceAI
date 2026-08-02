"""Plan state + usage metering.

Owns "what plan is this org on" and "how much have they used this month".
Stripe itself is handled in stripe_service; this module stays payment-provider
agnostic so limits can be tested without touching Stripe.
"""
from datetime import datetime, timezone

from db import SessionLocal
from models import Organization, Invoice
import plans


class QuotaExceeded(Exception):
    """Raised when an action would exceed the org's plan limit."""


def _current_month_prefix():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_plan_key(org_id):
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        return (org.plan if org else None) or plans.FREE
    finally:
        db.close()


def count_invoices_this_month(org_id):
    """Invoices created this calendar month — the metered unit."""
    db = SessionLocal()
    try:
        return (
            db.query(Invoice)
            .filter(
                Invoice.org_id == org_id,
                Invoice.created_at.like(f"{_current_month_prefix()}%"),
            )
            .count()
        )
    finally:
        db.close()


def get_usage(org_id):
    """Everything the billing UI and quota checks need, in one call."""
    plan_key = get_plan_key(org_id)
    plan = plans.get_plan(plan_key)
    used = count_invoices_this_month(org_id)
    limit = plan["invoice_limit"]

    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        status = org.subscription_status if org else None
        period_end = org.current_period_end if org else None
    finally:
        db.close()

    return {
        "plan": plan_key,
        "plan_name": plan["name"],
        "price_monthly": plan["price_monthly"],
        "email_automation": plan["email_automation"],
        "invoices_used": used,
        "invoice_limit": limit,
        "invoices_remaining": None if limit is None else max(0, limit - used),
        "limit_reached": limit is not None and used >= limit,
        "subscription_status": status,
        "current_period_end": period_end,
    }


def check_invoice_quota(org_id):
    """Raise QuotaExceeded if this org can't process another invoice.

    Called before extraction work begins so users hit the limit *before* we
    spend an AI call on them.
    """
    limit = plans.invoice_limit(get_plan_key(org_id))
    if limit is None:
        return
    if count_invoices_this_month(org_id) >= limit:
        raise QuotaExceeded(
            f"Monthly limit of {limit} invoices reached on the Free plan. "
            "Upgrade to Pro for unlimited invoices."
        )


def has_email_automation(org_id):
    return plans.allows_email_automation(get_plan_key(org_id))


def set_plan(org_id, plan_key, subscription_status=None, stripe_customer_id=None,
             stripe_subscription_id=None, current_period_end=None):
    """Update an org's plan. Only called from verified Stripe webhooks (and
    admin/test tooling) — never from user-supplied redirect parameters.
    """
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if org is None:
            return None
        org.plan = plan_key
        if subscription_status is not None:
            org.subscription_status = subscription_status
        if stripe_customer_id is not None:
            org.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            org.stripe_subscription_id = stripe_subscription_id
        if current_period_end is not None:
            org.current_period_end = current_period_end
        db.commit()
        return {"org_id": org_id, "plan": org.plan, "status": org.subscription_status}
    finally:
        db.close()


def downgrade_to_free(org_id):
    """Drop an org back to Free and CLEAR its subscription fields.

    Needed as its own function because set_plan() treats None as "leave
    unchanged", so it can't blank a field — which is exactly what a cancelled
    or expired subscription must do.
    """
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if org is None:
            return None
        org.plan = plans.FREE
        org.subscription_status = None
        org.stripe_subscription_id = None
        org.current_period_end = None
        # stripe_customer_id is kept: the customer still exists in Stripe and
        # should be reused if they resubscribe.
        db.commit()
        return {"org_id": org_id, "plan": org.plan}
    finally:
        db.close()
