"""WhatsApp channel via Twilio WhatsApp Business API."""

import json
from loguru import logger
from app.services.channels.base import BaseChannel, SendResult


class WhatsAppChannel(BaseChannel):
    """
    Sends WhatsApp messages via Twilio's WhatsApp Business API.

    Supports two auth methods (API Key preferred):
      - API Key: provide api_key_sid + api_key_secret + account_sid
      - Auth Token (legacy): provide account_sid + auth_token

    from_number must be in the form "whatsapp:+14155238886".
    to_phone is normalized to "whatsapp:+..." format automatically.
    """

    def __init__(
        self,
        account_sid: str,
        from_number: str,
        *,
        api_key_sid: str | None = None,
        api_key_secret: str | None = None,
        auth_token: str | None = None,
    ):
        from twilio.rest import Client
        if api_key_sid and api_key_secret:
            # Recommended: API Key auth (SK... key)
            self.client = Client(api_key_sid, api_key_secret, account_sid=account_sid)
        elif auth_token:
            # Legacy: Auth Token auth
            self.client = Client(account_sid, auth_token)
        else:
            raise ValueError("Twilio requires either API Key (api_key_sid + api_key_secret) or auth_token")
        self.from_number = (
            from_number if from_number.startswith("whatsapp:")
            else f"whatsapp:{from_number}"
        )

    async def send(
        self,
        to_phone: str,
        body: str,
        *,
        content_sid: str | None = None,
        content_variables: dict[str, str] | None = None,
    ) -> SendResult:
        to = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
        try:
            if content_sid:
                kwargs: dict = {"from_": self.from_number, "to": to, "content_sid": content_sid}
                cv_serialized: str | None = None
                if content_variables is not None:
                    cv_serialized = json.dumps(content_variables)
                    kwargs["content_variables"] = cv_serialized
                logger.info(
                    f"[DEV] WhatsApp TEMPLATE payload → to={to} "
                    f"content_sid={content_sid} "
                    f"content_variables={cv_serialized!r}"
                )
                msg = self.client.messages.create(**kwargs)
                logger.info(f"WhatsApp template sent: sid={msg.sid} to={to} content_sid={content_sid}")
            else:
                msg = self.client.messages.create(body=body, from_=self.from_number, to=to)
                logger.info(f"WhatsApp sent: sid={msg.sid} to={to}")
            return SendResult(status="sent", provider_id=msg.sid, error="")
        except Exception as e:
            logger.error(f"WhatsApp send failed to={to}: {e}")
            return SendResult(status="failed", provider_id="", error=str(e))


class DevLogChannel(BaseChannel):
    """
    Development fallback — logs instead of sending.
    Used when Twilio credentials are not configured.
    """

    async def send(
        self,
        to_phone: str,
        body: str,
        *,
        content_sid: str | None = None,
        content_variables: dict[str, str] | None = None,
    ) -> SendResult:
        if content_sid:
            logger.info(
                f"[DEV] WhatsApp TEMPLATE (not sent) → {to_phone}:\n"
                f"content_sid={content_sid}, vars={content_variables}"
            )
        else:
            logger.info(f"[DEV] WhatsApp message (not sent) → {to_phone}:\n{body}")
        return SendResult(status="sent", provider_id="dev-log", error="")
