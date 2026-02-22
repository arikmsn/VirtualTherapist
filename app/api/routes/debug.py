"""
Debug / diagnostic routes — only mounted in development / staging.
Never mounted in production (enforced in main.py).
"""

from fastapi import APIRouter, Depends
from app.api.deps import get_current_therapist
from app.models.therapist import Therapist

router = APIRouter()


@router.get("/twilio-test")
async def twilio_test(
    _: Therapist = Depends(get_current_therapist),  # require a logged-in therapist
):
    """
    Verify Twilio credentials and WhatsApp number configuration.

    Makes two lightweight API calls:
      1. Fetch account details  — proves Account SID + API Key auth work.
      2. List incoming numbers  — confirms the configured WhatsApp number
         belongs to this account (skipped for shared Sandbox numbers).

    Returns {"ok": true, ...} on success, {"ok": false, "error": ...} on failure.
    """
    from app.core.config import settings

    # ── 1. Check settings are present ──────────────────────────────────────
    missing = [
        f
        for f in ["TWILIO_ACCOUNT_SID", "TWILIO_WHATSAPP_NUMBER"]
        if not getattr(settings, f)
    ]
    has_api_key = bool(settings.TWILIO_API_KEY_SID and settings.TWILIO_API_KEY_SECRET)
    has_auth_token = bool(settings.TWILIO_AUTH_TOKEN)
    if not (has_api_key or has_auth_token):
        missing.append("TWILIO_API_KEY_SID+TWILIO_API_KEY_SECRET (or TWILIO_AUTH_TOKEN)")

    if missing:
        return {
            "ok": False,
            "error": f"Missing required env vars: {', '.join(missing)}",
            "hint": "Check your .env file and restart the server.",
        }

    # ── 2. Build client ─────────────────────────────────────────────────────
    try:
        from twilio.rest import Client

        if has_api_key:
            client = Client(
                settings.TWILIO_API_KEY_SID,
                settings.TWILIO_API_KEY_SECRET,
                account_sid=settings.TWILIO_ACCOUNT_SID,
            )
        else:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    except Exception as exc:
        return {"ok": False, "stage": "client_init", "error": str(exc)}

    # ── 3. Fetch account (proves auth) ──────────────────────────────────────
    try:
        account = client.api.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
    except Exception as exc:
        return {
            "ok": False,
            "stage": "account_fetch",
            "error": str(exc),
            "hint": _auth_hint(str(exc)),
        }

    # ── 4. Verify the WhatsApp number exists in the account ─────────────────
    whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER  # e.g. "whatsapp:+972..."
    bare_number = whatsapp_number.replace("whatsapp:", "").strip()
    number_status = "not_checked"
    number_hint = ""

    # The shared Sandbox number (+14155238886) is Twilio-owned — skip ownership check.
    SANDBOX_NUMBER = "+14155238886"
    if bare_number == SANDBOX_NUMBER:
        number_status = "sandbox_shared"
        number_hint = "Using the shared WhatsApp Sandbox — no ownership check needed."
    else:
        try:
            matches = client.incoming_phone_numbers.list(phone_number=bare_number, limit=1)
            if matches:
                number_status = "found_in_account"
            else:
                number_status = "not_found_in_account"
                number_hint = (
                    f"The number {bare_number} was not found in your Twilio account. "
                    "Check the TWILIO_WHATSAPP_NUMBER in .env — it must match a number "
                    "you own in the Twilio console."
                )
        except Exception as exc:
            number_status = "check_failed"
            number_hint = str(exc)

    return {
        "ok": number_status not in ("not_found_in_account",),
        "auth": "api_key" if has_api_key else "auth_token",
        "account": {
            "sid": account.sid,
            "friendly_name": account.friendly_name,
            "status": account.status,  # "active" is good
        },
        "whatsapp_number": whatsapp_number,
        "number_status": number_status,
        "number_hint": number_hint or None,
    }


# ── helpers ─────────────────────────────────────────────────────────────────

def _auth_hint(error_msg: str) -> str:
    e = error_msg.lower()
    if "20003" in e or "authenticate" in e or "unauthorized" in e:
        return (
            "Authentication failed (HTTP 401 / error 20003). "
            "Check TWILIO_ACCOUNT_SID and TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET "
            "(or TWILIO_AUTH_TOKEN) in your .env. "
            "API Keys must be created under the same Account SID shown in the Twilio console."
        )
    if "20404" in e or "not found" in e:
        return "Account SID not found — double-check TWILIO_ACCOUNT_SID in .env."
    if "connection" in e or "timeout" in e:
        return "Network error connecting to Twilio. Check your internet / firewall."
    return "See Twilio error code at https://www.twilio.com/docs/api/errors"
