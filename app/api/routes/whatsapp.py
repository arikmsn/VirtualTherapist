"""Green-API WhatsApp webhook receiver.

Receives push notifications from Green-API (quotaExceeded, incomingMessageReceived, etc.)
and logs them for observability. Always returns 200 OK so Green-API stops retrying.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from loguru import logger

router = APIRouter()

_QUOTA_EXCEEDED_TYPE = "quotaExceeded"


@router.post("/webhook")
async def green_api_webhook(request: Request):
    """
    Receive and log Green-API webhook events.

    Green-API expects 200 OK; any non-200 triggers retries.
    All parsing errors are swallowed so we never return 4xx/5xx.
    """
    try:
        body = await request.json()
    except Exception:
        # Malformed body — still return 200 so Green-API doesn't retry forever
        logger.warning("[GreenAPI webhook] Received non-JSON body — ignored")
        return JSONResponse(content={"ok": True})

    webhook_type = body.get("typeWebhook", "")

    if webhook_type == _QUOTA_EXCEEDED_TYPE:
        quota = body.get("quotaData") or body.get("quotaData", {})
        method = quota.get("method", "unknown")
        status = quota.get("status", "unknown")
        used = quota.get("used")
        total = quota.get("total")
        # Green-API includes a human-readable description with the allowed chat list
        description = quota.get("description", "")
        logger.warning(
            f"[GreenAPI webhook] quotaExceeded: "
            f"method={method} status={status} used={used} total={total} "
            f"description={description!r}"
        )
    else:
        logger.info(f"[GreenAPI webhook] typeWebhook={webhook_type!r} (no action taken)")

    return JSONResponse(content={"ok": True})
