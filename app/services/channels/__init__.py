"""Channel factory — returns the correct BaseChannel implementation."""

from app.services.channels.base import BaseChannel


def get_channel(channel: str = "whatsapp") -> BaseChannel:
    """
    Return the appropriate channel adapter.

    In development (no Twilio credentials), returns DevLogChannel which
    logs to console instead of sending — no crash, no false sends.
    """
    from app.core.config import settings

    if channel == "whatsapp":
        has_api_key = bool(settings.TWILIO_API_KEY_SID and settings.TWILIO_API_KEY_SECRET)
        has_auth_token = bool(settings.TWILIO_AUTH_TOKEN)
        has_creds = settings.TWILIO_ACCOUNT_SID and settings.TWILIO_WHATSAPP_NUMBER and (has_api_key or has_auth_token)
        if has_creds:
            from app.services.channels.whatsapp import WhatsAppChannel
            return WhatsAppChannel(
                account_sid=settings.TWILIO_ACCOUNT_SID,
                from_number=settings.TWILIO_WHATSAPP_NUMBER,
                api_key_sid=settings.TWILIO_API_KEY_SID,
                api_key_secret=settings.TWILIO_API_KEY_SECRET,
                auth_token=settings.TWILIO_AUTH_TOKEN,
            )
        from app.services.channels.whatsapp import DevLogChannel
        return DevLogChannel()

    raise ValueError(f"Unknown channel: '{channel}'. Supported: 'whatsapp'")
