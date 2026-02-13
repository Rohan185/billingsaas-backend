"""
Google Gemini AI integration via REST API.
Uses Gemini 2.0 Flash (free tier via Google AI Studio).
Includes global rate limiter, retry with backoff, and 429 handling.
"""
import os
import time
import logging
import asyncio
import httpx
from collections import deque

logger = logging.getLogger("gemini_service")

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"

# ── Global rate limiter: max 5 calls per 60 seconds ──
_call_timestamps: deque = deque()
GLOBAL_MAX_CALLS = 5
GLOBAL_WINDOW_SECONDS = 60

MAX_RETRIES = 2
RETRY_DELAYS = [5, 10]  # seconds


def _check_global_limit() -> bool:
    now = time.time()
    while _call_timestamps and _call_timestamps[0] < now - GLOBAL_WINDOW_SECONDS:
        _call_timestamps.popleft()
    return len(_call_timestamps) < GLOBAL_MAX_CALLS


def _record_call():
    _call_timestamps.append(time.time())


async def generate_gemini_response(prompt: str) -> str:
    """
    Send prompt to Gemini via REST API with retry logic.
    Reads API key at call time. Fully async via httpx.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return "⚠️ AI advisor not configured. Please set GEMINI_API_KEY."

    if not _check_global_limit():
        return "⚠️ AI is busy right now. Please try again in a minute."

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 300,
        },
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{API_URL}?key={api_key}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code == 429:
                    if attempt < MAX_RETRIES:
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(f"Gemini 429 — retrying in {delay}s (attempt {attempt + 1})")
                        await asyncio.sleep(delay)
                        continue
                    return "⚠️ AI temporarily busy. Please try again in a minute."

                resp.raise_for_status()
                data = resp.json()

                reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                _record_call()

                if len(reply) > 1500:
                    reply = reply[:1497] + "..."
                return reply

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAYS[attempt])
                continue
            logger.error(f"Gemini HTTP error: {e}")
            return "⚠️ AI advisor temporarily unavailable. Please try again."
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return "⚠️ AI advisor temporarily unavailable. Please try again."

    return "⚠️ AI advisor temporarily unavailable. Please try again."
