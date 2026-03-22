"""Loops.so email automation integration.

Notifies Loops when a new therapist signs up:
  1. Creates/upserts the contact.
  2. Sends the user_signed_up event (triggers the welcome sequence).

Failures are logged and swallowed — they must never break registration.
"""

import os
import logging

import httpx

logger = logging.getLogger(__name__)

LOOPS_API_KEY = os.environ.get("LOOPS_API_KEY")
LOOPS_BASE_URL = "https://app.loops.so/api/v1"


async def notify_loops_signup(
    email: str,
    first_name: str = "",
    last_name: str = "",
) -> None:
    """Fire-and-forget: create Loops contact + send user_signed_up event."""
    if not LOOPS_API_KEY:
        logger.warning("LOOPS_API_KEY not set – skipping Loops notification")
        return

    headers = {
        "Authorization": f"Bearer {LOOPS_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            contact_resp = await client.post(
                f"{LOOPS_BASE_URL}/contacts/create",
                headers=headers,
                json={
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "subscribed": True,
                    "source": "signup",
                },
            )
            contact_resp.raise_for_status()

            event_resp = await client.post(
                f"{LOOPS_BASE_URL}/events/send",
                headers=headers,
                json={
                    "email": email,
                    "eventName": "user_signed_up",
                },
            )
            event_resp.raise_for_status()
            logger.info("Loops signup event sent for %s", email)

    except Exception as exc:
        logger.error("Failed to notify Loops for %s: %s", email, exc)
