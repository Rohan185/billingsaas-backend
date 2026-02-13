"""
OpenAI gpt-4o-mini service with strict enforcement.
- Model locked to gpt-4o-mini (raises on any other)
- Global 60s cooldown between calls
- max_tokens=200, temperature=0.5, no streaming
- Token usage logged to console
"""
import os
import time
import logging
import httpx
from app.ai_config import (
    AI_MODEL,
    AI_ALLOWED_MODELS,
    AI_RATE_LIMIT_SECONDS,
    AI_MAX_TOKENS,
    AI_TEMPERATURE,
    AI_MAX_PROMPT_CHARS,
)

logger = logging.getLogger("ai_service")

# ── Global rate limiter (in-memory, single instance) ──
_last_call_timestamp: float = 0.0


def _enforce_model(model: str):
    """Raise if model is not in the allowed whitelist."""
    if model not in AI_ALLOWED_MODELS:
        raise RuntimeError(
            f"Unauthorized model usage detected: '{model}'. "
            f"Only {AI_ALLOWED_MODELS} is permitted."
        )


def _check_cooldown() -> int | None:
    """Return remaining seconds if in cooldown, else None."""
    global _last_call_timestamp
    elapsed = time.time() - _last_call_timestamp
    if elapsed < AI_RATE_LIMIT_SECONDS:
        return int(AI_RATE_LIMIT_SECONDS - elapsed)
    return None


def _trim_prompt(text: str) -> str:
    """Trim prompt to max allowed characters."""
    if len(text) > AI_MAX_PROMPT_CHARS:
        return text[:AI_MAX_PROMPT_CHARS] + "\n[...data trimmed for safety]"
    return text


async def call_openai(system_prompt: str, user_message: str) -> str:
    """
    Call OpenAI gpt-4o-mini with strict controls.
    Returns plain text response or error message.
    """
    global _last_call_timestamp

    # 1. Enforce model
    _enforce_model(AI_MODEL)

    # 2. Check cooldown
    remaining = _check_cooldown()
    if remaining is not None:
        return f"⏳ AI is cooling down. Please wait {remaining} seconds before next request."

    # 3. Check API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return "⚠️ AI advisor not configured. Please set OPENAI_API_KEY."

    # 4. Trim prompts
    system_prompt = _trim_prompt(system_prompt)
    user_message = _trim_prompt(user_message)

    # 5. Build request
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": messages,
                    "max_tokens": AI_MAX_TOKENS,
                    "temperature": AI_TEMPERATURE,
                    "stream": False,
                },
            )

            if resp.status_code == 429:
                logger.warning("OpenAI 429 — rate limited by API")
                return "⚠️ AI temporarily busy. Please try again in a minute."

            resp.raise_for_status()
            data = resp.json()

            # Record successful call
            _last_call_timestamp = time.time()

            # Log token usage
            usage = data.get("usage", {})
            logger.info(
                f"[AI USAGE] model={AI_MODEL} "
                f"prompt_tokens={usage.get('prompt_tokens', '?')} "
                f"completion_tokens={usage.get('completion_tokens', '?')} "
                f"total_tokens={usage.get('total_tokens', '?')}"
            )

            reply = data["choices"][0]["message"]["content"].strip()

            if len(reply) > 1500:
                reply = reply[:1497] + "..."

            return reply

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return "⚠️ AI temporarily busy. Please try again in a minute."
        logger.error(f"OpenAI HTTP error: {e}")
        return "⚠️ AI advisor temporarily unavailable. Please try again."
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "⚠️ AI advisor temporarily unavailable. Please try again."
