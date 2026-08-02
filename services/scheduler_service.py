"""In-process auto-sync scheduler.

Every SYNC_INTERVAL_SECONDS, sync + process every connected Gmail account —
so invoices arrive with no clicks at all. Runs as an asyncio task inside the
API process: right-sized for a single server instance. When we scale out,
this loop is replaced by Celery beat + workers; process_attachment/process
_pending stay the unit of work either way, so nothing else changes.

Set SYNC_INTERVAL_SECONDS=0 to disable (e.g. in tests).
"""
import asyncio
import logging
import os

from services import billing_service, processing_service
from services.email_service import list_connected_org_ids, sync_gmail

logger = logging.getLogger("invoiceai.autosync")

SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))


def run_sync_cycle():
    """One pass over all connected accounts. Failures are logged per-org so a
    broken account (e.g. revoked token) never blocks the others.
    """
    for org_id in list_connected_org_ids():
        try:
            # Automatic import is a paid feature — free workspaces keep their
            # connected account but aren't synced until they upgrade.
            if not billing_service.has_email_automation(org_id):
                logger.info("auto-sync org=%s skipped (plan without email automation)", org_id)
                continue

            synced = sync_gmail(org_id) or {}
            processed = processing_service.process_pending(org_id)
            logger.info(
                "auto-sync org=%s scanned=%s new_messages=%s new_attachments=%s "
                "processed=%s completed=%s failed=%s",
                org_id,
                synced.get("scanned", 0), synced.get("new_messages", 0),
                synced.get("new_attachments", 0),
                processed.get("processed", 0), processed.get("completed", 0),
                processed.get("failed", 0),
            )
        except Exception:
            logger.exception("auto-sync failed for org=%s", org_id)


async def _loop():
    logger.info("auto-sync enabled: every %s seconds", SYNC_INTERVAL_SECONDS)
    while True:
        # Sync services are blocking (Gmail + Gemini calls) — run them in a
        # worker thread so the event loop keeps serving requests.
        await asyncio.to_thread(run_sync_cycle)
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


def start():
    """Start the loop (call from FastAPI lifespan). Returns the task, or None
    when auto-sync is disabled.
    """
    if SYNC_INTERVAL_SECONDS <= 0:
        logger.info("auto-sync disabled (SYNC_INTERVAL_SECONDS=0)")
        return None
    return asyncio.create_task(_loop())


def stop(task):
    if task is not None:
        task.cancel()
