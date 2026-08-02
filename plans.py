"""Plan definitions — the single source of truth for what each tier allows.

Limits live here (not scattered through the code) so pricing changes are a
one-file edit. `invoice_limit = None` means unlimited.
"""

FREE = "free"
PRO = "pro"

PLANS = {
    FREE: {
        "key": FREE,
        "name": "Free",
        "price_monthly": 0,
        "invoice_limit": 20,          # invoices processed per calendar month
        "email_automation": False,    # Gmail sync is the paid differentiator
        "features": [
            "20 invoices per month",
            "AI extraction (PDF & scanned)",
            "Dashboard & reports",
            "Unlimited team members",
        ],
    },
    PRO: {
        "key": PRO,
        "name": "Pro",
        "price_monthly": 29,
        "invoice_limit": None,        # unlimited
        "email_automation": True,
        "features": [
            "Unlimited invoices",
            "Automatic email import (Gmail)",
            "AI extraction (PDF & scanned)",
            "Dashboard & reports",
            "Unlimited team members",
        ],
    },
}


def get_plan(plan_key):
    """Plan config for a key, falling back to Free for unknown/missing values."""
    return PLANS.get(plan_key or FREE, PLANS[FREE])


def allows_email_automation(plan_key):
    return get_plan(plan_key)["email_automation"]


def invoice_limit(plan_key):
    return get_plan(plan_key)["invoice_limit"]
