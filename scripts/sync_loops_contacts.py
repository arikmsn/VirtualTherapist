"""
One-time script: bulk-import all existing therapists into Loops.so.

Run from the repo root:
    python scripts/sync_loops_contacts.py

Requires:
    - DATABASE_URL in environment (same as the app)
    - LOOPS_API_KEY in environment

Behaviour:
    - Queries all active therapists from the DB.
    - POSTs each to /contacts/create (idempotent — Loops upserts by email).
    - Prints a per-contact summary and a final tally.
    - Failures on individual contacts are logged but do NOT abort the run.
"""

import os
import sys
import time
import logging

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.core.database import SessionLocal
from app.models.therapist import Therapist

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LOOPS_API_KEY = os.environ.get("LOOPS_API_KEY")
LOOPS_BASE_URL = "https://app.loops.so/api/v1"

# Conservative rate-limit: Loops free tier allows ~10 req/s; stay well under.
REQUEST_DELAY_SECS = 0.15


def sync_all_therapists() -> None:
    if not LOOPS_API_KEY:
        logger.error("LOOPS_API_KEY is not set. Aborting.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {LOOPS_API_KEY}",
        "Content-Type": "application/json",
    }

    db = SessionLocal()
    try:
        therapists = (
            db.query(Therapist)
            .filter(Therapist.is_active == True)  # noqa: E712
            .order_by(Therapist.id)
            .all()
        )
    finally:
        db.close()

    total = len(therapists)
    logger.info("Found %d active therapists to sync.", total)

    ok_count = 0
    fail_count = 0

    with httpx.Client(timeout=15.0) as client:
        for i, therapist in enumerate(therapists, start=1):
            name_parts = (therapist.full_name or "").split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            payload = {
                "email": therapist.email,
                "firstName": first_name,
                "lastName": last_name,
                "subscribed": True,
                "userGroup": "therapist",
                "source": "bulk_import",
            }

            try:
                resp = client.post(
                    f"{LOOPS_BASE_URL}/contacts/create",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                logger.info("[%d/%d] ✓ %s", i, total, therapist.email)
                ok_count += 1
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "[%d/%d] ✗ %s — HTTP %s: %s",
                    i, total, therapist.email,
                    exc.response.status_code,
                    exc.response.text[:200],
                )
                fail_count += 1
            except Exception as exc:
                logger.warning("[%d/%d] ✗ %s — %s", i, total, therapist.email, exc)
                fail_count += 1

            time.sleep(REQUEST_DELAY_SECS)

    logger.info("Done. %d synced, %d failed (out of %d total).", ok_count, fail_count, total)
    if fail_count:
        sys.exit(1)


if __name__ == "__main__":
    sync_all_therapists()
