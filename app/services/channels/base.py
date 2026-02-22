"""Abstract base channel for outbound message delivery."""

from abc import ABC, abstractmethod
from typing import TypedDict


class SendResult(TypedDict):
    status: str        # "sent" or "failed"
    provider_id: str   # Channel-specific message ID (empty string on failure)
    error: str         # Error description (empty string on success)


class BaseChannel(ABC):
    """Abstract channel — all outbound message transport must implement this."""

    @abstractmethod
    async def send(
        self,
        to_phone: str,
        body: str,
        *,
        content_sid: str | None = None,
        content_variables: dict[str, str] | None = None,
    ) -> SendResult:
        """
        Send a message to the given phone number.

        Args:
            to_phone: E.164 phone number (e.g. "+972501234567") or channel-prefixed
                      (e.g. "whatsapp:+972501234567").
            body: Message text. Used when content_sid is not provided.
            content_sid: Twilio Content Template SID (e.g. "HXabc...").
                         When provided, body is ignored and the template is used instead.
            content_variables: Template variable substitutions, e.g. {"1": "Alice", "2": "Dr. Cohen"}.
                               Ignored when content_sid is None.

        Returns:
            SendResult dict with "status", "provider_id", "error".
        """
        ...
