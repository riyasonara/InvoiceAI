"""Stripe integration: Checkout Sessions today, webhook handling next.

Stripe itself never decides an org's plan — only the (signature-verified)
webhook is allowed to do that, in main.py. This module just talks to
Stripe's API and keeps the org<->Stripe-customer link in our database.
"""
import os
from datetime import datetime, timezone

import stripe
from dotenv import load_dotenv

import plans
from db import SessionLocal
from models import Organization
from services import billing_service

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
PRICE_ID = os.getenv("STRIPE_PRICE_ID")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


def is_configured():
    return bool(stripe.api_key and PRICE_ID)


def _get_or_create_customer(org_id, email):
    """Reuse the org's existing Stripe Customer if it has one (so a
    resubscribe after cancelling doesn't fragment into a second customer),
    otherwise create one and remember its id.
    """
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if org.stripe_customer_id:
            return org.stripe_customer_id

        customer = stripe.Customer.create(email=email, metadata={"org_id": str(org_id)})
        org.stripe_customer_id = customer.id
        db.commit()
        return customer.id
    finally:
        db.close()


def create_checkout_session(org_id, admin_email, success_url, cancel_url):
    """A hosted Stripe payment page for this org to subscribe to Pro.

    metadata={"org_id": ...} is what lets the webhook (Stripe calling us
    back, with no session/cookie of its own) know which org just paid.
    """
    customer_id = _get_or_create_customer(org_id, admin_email)
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"org_id": str(org_id)},
        # Also stamped onto the Subscription object itself (not just this
        # Checkout Session), so later events like cancellation — which
        # carry a Subscription, not a Session — can identify the org too.
        subscription_data={"metadata": {"org_id": str(org_id)}},
    )
    return session.url


def create_portal_session(org_id, return_url):
    """A Stripe-hosted page where an admin can update their card, view past
    invoices, or cancel — self-service, so we don't have to build any of
    that ourselves. Returns None if this org has never checked out (no
    Stripe Customer to manage yet).
    """
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        customer_id = org.stripe_customer_id if org else None
    finally:
        db.close()

    if not customer_id:
        return None

    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url


def construct_event(payload, sig_header):
    """Verify a webhook request actually came from Stripe. Raises
    stripe.SignatureVerificationError or ValueError if it didn't — the
    caller (main.py) turns that into a 400, never trusting the payload.
    """
    return stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)


def _period_end(subscription):
    # Stripe moved current_period_end off the Subscription object and onto
    # each subscription item (accounts created after this change no longer
    # have it at the top level at all) — read it from the first item.
    ts = subscription["items"]["data"][0]["current_period_end"]
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def handle_checkout_completed(session):
    """checkout.session.completed: payment cleared, activate Pro."""
    org_id = int(session["metadata"]["org_id"])
    subscription = stripe.Subscription.retrieve(session["subscription"])
    billing_service.set_plan(
        org_id,
        plans.PRO,
        subscription_status="active",
        stripe_customer_id=session["customer"],
        stripe_subscription_id=subscription["id"],
        current_period_end=_period_end(subscription),
    )


def handle_subscription_deleted(subscription):
    """customer.subscription.deleted: the subscription actually ended
    (cancelled, or payment retries exhausted) — drop back to Free.
    """
    org_id = int(subscription["metadata"]["org_id"])
    billing_service.downgrade_to_free(org_id)
