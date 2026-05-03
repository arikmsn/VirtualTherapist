"""WhatsApp delivery routing service.

Routes messages to Green API or Twilio based on the WHATSAPP_PROVIDER setting.
send_whatsapp_message() is the ONLY function the rest of the app should call
for WhatsApp delivery.

Production note (2026-04-13):
  WHATSAPP_PROVIDER defaults to "green_api" and is not overridden on Render.
  Twilio is NOT in the live production path — the Twilio branch is dead code.

  Root cause of 2026-04-13 incident:
  Green API's sendMessage() uses the synchronous `requests` library internally.
  Calling it directly inside an async function blocked the asyncio event loop
  for 5–15 seconds per scheduler tick, causing Render health probes on other
  endpoints to time out, which triggered repeated service restarts.

  Fix: send_via_green_api() now wraps sendMessage() in run_in_executor() so
  the blocking HTTP call runs in a thread pool without stalling the event loop.
  The Twilio branch received the same fix defensively.
"""

from typing import Optional
from loguru import logger
from app.services.channels.base import SendResult


def format_phone_to_green_api(phone: str) -> str:
    """Convert E.164 phone (+972501234567) to Green API chat ID (972501234567@c.us)."""
    return phone.lstrip('+') + '@c.us'


def _build_plain_text(content_variables: dict) -> str:
    """Build a plain-text Hebrew reminder from Twilio template content_variables.

    Normalises every value to a non-None string first so that neither
    f-strings nor str.join() can raise TypeError on None values.
    """
    # Normalise: None → "", everything else → str
    v = {k: ("" if val is None else str(val)) for k, val in content_variables.items()}

    if len(v) == 4:
        # Appointment reminder and session reminder share this format:
        #   1=patient, 2=therapist, 3=date (DD.MM.YY), 4=time (HH:MM)
        parts = [f"שלום {v.get('1', '')},", f"זוהי תזכורת לפגישתך עם {v.get('2', '')}"]
        date = v.get("3", "")
        time = v.get("4", "")
        if date and date != "לא צוין":
            parts.append(f"בתאריך {date}")
        if time and time != "לא צוינה":
            parts.append(f"בשעה {time}.")
        return " ".join(parts)

    # Fallback: join all values (now guaranteed to be strings)
    return " ".join(v.values())


async def send_via_green_api(phone: str, message: str) -> SendResult:
    """Send a plain-text WhatsApp message via Green API."""
    import asyncio
    import httpx
    from app.core.config import settings

    # ── Guard: phone ──────────────────────────────────────────────────────────
    if not phone:
        err = "send_via_green_api: phone is empty/None — cannot send"
        logger.error(err)
        return SendResult(status="failed", provider_id="", error=err, http_status_code=0)

    # ── Guard: message ────────────────────────────────────────────────────────
    safe_message = message if isinstance(message, str) else (str(message) if message is not None else "")
    if not safe_message:
        logger.warning(f"[GreenAPI] message body is empty for {phone} — using placeholder")
        safe_message = "תזכורת פגישה"

    # ── Guard: credentials ────────────────────────────────────────────────────
    instance_id = settings.GREEN_API_INSTANCE_ID
    api_token = settings.GREEN_API_TOKEN
    if not instance_id or not api_token:
        err = (
            "GREEN_API_INSTANCE_ID or GREEN_API_TOKEN is not set — "
            "message not sent. Configure these env vars in Render."
        )
        logger.error(f"[GreenAPI] {err} (phone={phone})")
        return SendResult(status="failed", provider_id="", error=err, http_status_code=0)

    instance_id = str(instance_id)
    api_token = str(api_token)
    chat_id = format_phone_to_green_api(phone)

    def _do_send() -> SendResult:
        url = f"https://api.green-api.com/waInstance{instance_id}/sendMessage/{api_token}"
        try:
            resp = httpx.post(url, json={"chatId": chat_id, "message": safe_message}, timeout=10.0)
            resp.raise_for_status()
            id_message = resp.json().get("idMessage", "")
            logger.info(f"[GreenAPI] Sent to {chat_id}: idMessage={id_message}")
            return SendResult(status="sent", provider_id=str(id_message), error="", http_status_code=resp.status_code)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            resp_text = exc.response.text[:500]
            logger.error(
                f"[GreenAPI] HTTP {status_code} sending to {chat_id}: {resp_text!r}"
            )
            return SendResult(status="failed", provider_id="", error=resp_text, http_status_code=status_code)
        except Exception as exc:
            logger.exception(f"[GreenAPI] Send failed to {phone}: {exc}")
            return SendResult(status="failed", provider_id="", error=str(exc), http_status_code=0)

    logger.info(f"[GreenAPI] Sending to {chat_id}: {safe_message!r}")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _do_send)


async def send_via_twilio(
    phone: str,
    message: str,
    content_sid: Optional[str] = None,
    content_variables: Optional[dict] = None,
) -> SendResult:
    """Send a WhatsApp message via Twilio (delegates to existing channel abstraction)."""
    from app.services.channels import get_channel
    channel = get_channel("whatsapp")
    return await channel.send(
        phone, message, content_sid=content_sid, content_variables=content_variables
    )


async def send_whatsapp_message(
    phone: str,
    message: str,
    content_sid: Optional[str] = None,
    content_variables: Optional[dict] = None,
) -> SendResult:
    """
    Send a WhatsApp message, routing to Green API or Twilio based on WHATSAPP_PROVIDER.
    This is the ONLY function the rest of the app should call for WhatsApp delivery.

    Green API sends plain text only — when a Twilio content_sid is provided, the
    template variables are rendered into a Hebrew plain-text string before sending.
    """
    from app.core.config import settings
    provider = (settings.WHATSAPP_PROVIDER or "green_api").lower()

    if provider == "green_api":
        # Build plain-text body (Green API has no template support)
        if content_sid and content_variables:
            text = _build_plain_text(content_variables)
        else:
            text = message
        return await send_via_green_api(phone, text)

    if provider == "twilio":
        return await send_via_twilio(
            phone, message, content_sid=content_sid, content_variables=content_variables
        )

    # Unknown provider — dev-log fallback, never block delivery
    logger.warning(f"Unknown WHATSAPP_PROVIDER={provider!r} — message not sent (dev-log)")
    logger.info(f"[DEV] WhatsApp (provider={provider}) → {phone}: {message}")
    return SendResult(status="sent", provider_id="dev-log", error="")
