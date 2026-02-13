"""
WhatsApp Cloud API integration.
Uses Graph API v18.0 to send text and document messages.
"""
import os
import logging
import httpx

logger = logging.getLogger("whatsapp_service")

BASE_URL = "https://graph.facebook.com/v18.0"


def _get_credentials() -> tuple[str, str]:
    """Read WhatsApp credentials from env at call time."""
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        raise ValueError(
            "WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID must be set"
        )
    return token, phone_id


async def send_whatsapp_text(to_number: str, message: str) -> dict:
    """
    Send a plain-text WhatsApp message via Cloud API.
    Returns the Graph API JSON response.
    """
    token, phone_id = _get_credentials()

    url = f"{BASE_URL}/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


async def send_whatsapp_document(
    to_number: str, file_bytes: bytes, filename: str
) -> bool:
    """
    Send a PDF document via WhatsApp Cloud API.

    Two-step process:
      1. Upload media to Meta servers
      2. Send document message referencing the uploaded media ID

    Returns True if successful, False otherwise.
    """
    token, phone_id = _get_credentials()
    auth_header = {"Authorization": f"Bearer {token}"}

    try:
        # ── Step 1: Upload media ─────────────────────────────────────
        upload_url = f"{BASE_URL}/{phone_id}/media"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                upload_url,
                headers=auth_header,
                files={"file": (filename, file_bytes, "application/pdf")},
                data={
                    "type": "application/pdf",
                    "messaging_product": "whatsapp",
                },
            )
            resp.raise_for_status()
            media_id = resp.json().get("id")

            if not media_id:
                logger.error("Media upload succeeded but no media ID returned")
                return False

            logger.info(f"Media uploaded: {filename} → media_id={media_id}")

        # ── Step 2: Send document message ────────────────────────────
        msg_url = f"{BASE_URL}/{phone_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": filename,
            },
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                msg_url,
                headers={**auth_header, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()

        logger.info(f"Document sent: {filename} → {to_number}")
        return True

    except httpx.HTTPStatusError as e:
        logger.error(
            f"WhatsApp document API error: {e.response.status_code} "
            f"— {e.response.text[:200]}"
        )
        return False
    except Exception as e:
        logger.error(f"WhatsApp document send failed: {e}")
        return False
