"""WhatsApp delivery routing service.

Routes messages to Green API or Twilio based on the WHATSAPP_PROVIDER setting.
send_whatsapp_message() is the ONLY function the rest of the app should call
for WhatsApp delivery.
"""

from typing import Optional
from loguru import logger
from app.services.channels.base import SendResult


def format_phone_to_green_api(phone: str) -> str:
    """Convert E.164 phone (+972501234567) to Green API chat ID (972501234567@c.us)."""
    return phone.lstrip('+') + '@c.us'


def _build_plain_text(content_variables: dict) -> str:
    """Build a plain-text Hebrew reminder from Twilio template content_variables."""
    if len(content_variables) == 4:
        # Session reminder: 1=patient, 2=therapist, 3=date, 4=time
        patient = content_variables.get("1", "")
        therapist = content_variables.get("2", "")
        date = content_variables.get("3", "")
        time = content_variables.get("4", "")
        parts = [f"שלום {patient},", f"זוהי תזכורת לפגישתך עם {therapist}"]
        if date and date != "לא צוין":
            parts.append(f"בתאריך {date}")
        if time and time != "לא צוינה":
            parts.append(f"בשעה {time}.")
        return " ".join(parts)

    if len(content_variables) == 5:
        # Appointment reminder: 1=patient, 2=therapist, 3=clinic, 4=date, 5=time
        patient = content_variables.get("1", "")
        therapist = content_variables.get("2", "")
        clinic = content_variables.get("3", "")
        date = content_variables.get("4", "")
        time = content_variables.get("5", "")
        return (
            f"שלום {patient}, זוהי תזכורת לפגישתך עם {therapist} "
            f"מקליניקת {clinic} בתאריך {date} בשעה {time}."
        )

    # Fallback: join all variable values
    return " ".join(content_variables.values())


async def send_via_green_api(phone: str, message: str) -> SendResult:
    """Send a plain-text WhatsApp message via Green API."""
    from app.core.config import settings

    try:
        from whatsapp_api_client_python import API
        green_api = API.GreenAPI(settings.GREEN_API_INSTANCE_ID, settings.GREEN_API_TOKEN)
        chat_id = format_phone_to_green_api(phone)
        response = green_api.sending.sendMessage(chat_id, message)
        id_message = str(response.data.get("idMessage", "")) if response.data else ""
        logger.info(f"[GreenAPI] Sent to {chat_id}: idMessage={id_message}")
        return SendResult(status="sent", provider_id=id_message, error="")
    except Exception as e:
        logger.error(f"[GreenAPI] Send failed to {phone}: {e}")
        return SendResult(status="failed", provider_id="", error=str(e))


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
