"""
WhatsApp Media Download Service.
Downloads audio/media files from Meta Graph API for processing.
"""
import os
import logging
import httpx

logger = logging.getLogger("whatsapp_media")

BASE_URL = "https://graph.facebook.com/v18.0"


async def download_whatsapp_media(media_id: str) -> bytes | None:
    """
    Download media from WhatsApp Cloud API.

    Flow:
    1. GET media metadata (contains download URL)
    2. GET actual file bytes from download URL

    Returns raw bytes or None on failure.
    """
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    if not token:
        logger.error("WHATSAPP_ACCESS_TOKEN not set")
        return None

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Get media URL
            meta_resp = await client.get(
                f"{BASE_URL}/{media_id}",
                headers=headers,
            )
            meta_resp.raise_for_status()
            media_url = meta_resp.json().get("url")

            if not media_url:
                logger.error(f"No URL in media metadata for {media_id}")
                return None

            # Step 2: Download actual file
            file_resp = await client.get(media_url, headers=headers)
            file_resp.raise_for_status()

            file_bytes = file_resp.content
            size_mb = len(file_bytes) / (1024 * 1024)

            logger.info(
                f"Media downloaded: {media_id} ({size_mb:.1f} MB)"
            )

            return file_bytes

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Media download HTTP error: {e.response.status_code} "
            f"— {e.response.text[:200]}"
        )
        return None
    except Exception as e:
        logger.error(f"Media download failed: {e}")
        return None
