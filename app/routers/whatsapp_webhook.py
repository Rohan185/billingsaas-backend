"""
WhatsApp Cloud API Webhook receiver.
- GET  /api/webhook/whatsapp  → verification handshake
- POST /api/webhook/whatsapp  → incoming message handler

Supports:
- Text messages → intent router → AI fallback
- Audio/voice messages → Groq Whisper → intent router → AI fallback

Flow:
1. If audio → download → transcribe via Groq Whisper
2. Check conversation state (follow-up to pending question?)
3. Match intent via fuzzy keyword matching
4. Check invoice command patterns
5. Filter greetings / short messages
6. AI fallback with per-user cooldown + language-aware tone
"""
import os
import time
import logging
from fastapi import APIRouter, Query, Request, HTTPException
from app.whatsapp_service import send_whatsapp_text
from app.whatsapp_commands import match_intent, handle_command, HELP_REPLY
from app.whatsapp_invoice_commands import is_invoice_command, handle_invoice_command
from app.ai_advisor_service import generate_business_advice
from app.whatsapp_state import resolve_follow_up, set_session, clear_session
from app.whatsapp_media_service import download_whatsapp_media
from app.whisper_service import transcribe_audio_bytes, detect_language
from app.ai_config import USER_AI_COOLDOWN_SECONDS
from app.database import SessionLocal

logger = logging.getLogger("whatsapp_webhook")

router = APIRouter(prefix="/api/webhook", tags=["WhatsApp Webhook"])

# ── Hardcoded for demo — replace with phone→company lookup later ──
DEMO_COMPANY_ID = "93f43afe-5844-4c2a-9f16-eaf07e0543d5"

# ── Per-user cooldown for AI calls ──
_user_cooldowns: dict[str, float] = {}

# ── Greetings / short messages that show help menu ──
SKIP_MESSAGES = {
    "hi", "hello", "hey", "ok", "okay", "yes", "no",
    "thanks", "thank you", "bye", "hm", "hmm", "ya",
    "haan", "nahi", "theek", "acha", "accha", "sahi",
}

GREETING_REPLY = (
    "Hello boss! Main tumhara Business Assistant hu.\n\n"
    "Ye try karo:\n"
    ". revenue - Last 30 din ka revenue\n"
    ". profit - Profit summary\n"
    ". low stock - Stock alerts\n"
    ". production - Production report\n"
    ". top products - Best sellers\n"
    ". send last invoice - Invoice bhejo\n\n"
    "Ya kuch bhi pucho business ke baare me!\n"
    "Voice message bhi bhej sakte ho!"
)

# ── Audio error replies ──
AUDIO_TOO_LARGE = (
    "Audio thoda bada hai boss.\n"
    "1 minute ke andar ka bhejo."
)
AUDIO_NO_KEY = (
    "Voice message abhi setup nahi hua.\n"
    "Text me bhejo boss."
)
AUDIO_FAILED = (
    "Audio samajh nahi aaya boss.\n"
    "Dobara bhejo ya text me likho."
)


# ── GET: Verification handshake ──────────────────────────────────────
@router.get("/whatsapp")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta sends GET with hub.mode, hub.challenge, hub.verify_token."""
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("Webhook verified successfully")
        return int(hub_challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


# ── POST: Incoming messages ──────────────────────────────────────────
@router.post("/whatsapp")
async def receive_webhook(request: Request):
    """
    Handle incoming WhatsApp messages (text + audio).
    """
    body = await request.json()

    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                for msg in messages:
                    sender = msg["from"]
                    msg_type = msg.get("type", "")
                    msg_id = msg.get("id", "")

                    # ── Audio message ────────────────────────────────
                    if msg_type == "audio":
                        reply = await _handle_audio(msg, sender)
                        await send_whatsapp_text(to_number=sender, message=reply)
                        continue

                    # ── Text message ─────────────────────────────────
                    if msg_type != "text":
                        continue

                    text = msg["text"]["body"]
                    cmd = text.strip().lower()

                    logger.info(
                        f"[WhatsApp] From: {sender} | Msg: {text} | ID: {msg_id}"
                    )

                    db = SessionLocal()
                    try:
                        lang = detect_language(text)
                        reply = await _route_message(sender, text, cmd, db, lang)
                    except Exception as e:
                        logger.error(f"Message routing error: {e}")
                        reply = "Thoda problem hua boss. Dobara try karo."
                    finally:
                        db.close()

                    await send_whatsapp_text(to_number=sender, message=reply)

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return {"status": "ok"}


# ── Audio Handler ────────────────────────────────────────────────────
async def _handle_audio(msg: dict, sender: str) -> str:
    """
    Process voice/audio message:
    1. Download media from Meta
    2. Transcribe via Groq Whisper
    3. Route through intent router
    4. AI fallback if no match
    """
    audio_info = msg.get("audio", {})
    media_id = audio_info.get("id")

    if not media_id:
        logger.error("Audio message has no media_id")
        return AUDIO_FAILED

    logger.info(f"[Audio] From: {sender} | Media ID: {media_id}")

    # Step 1: Download media
    audio_bytes = await download_whatsapp_media(media_id)
    if not audio_bytes:
        return AUDIO_FAILED

    # Step 2: Transcribe
    text, lang = await transcribe_audio_bytes(audio_bytes)

    # Audio bytes not stored — deleted after transcription (GC handles it)

    # Handle error states
    if text == "__TOO_LARGE__":
        return AUDIO_TOO_LARGE
    if text == "__NO_KEY__":
        return AUDIO_NO_KEY
    if text in ("__FAILED__", "__EMPTY__"):
        return AUDIO_FAILED

    logger.info(f"[Audio Transcribed] lang={lang} | Text: {text}")

    # Step 3: Route through normal flow
    cmd = text.strip().lower()

    db = SessionLocal()
    try:
        reply = await _route_message(sender, text, cmd, db, lang)
    except Exception as e:
        logger.error(f"Audio routing error: {e}")
        reply = "Thoda problem hua boss. Dobara try karo."
    finally:
        db.close()

    return reply


# ── Central Routing ──────────────────────────────────────────────────
async def _route_message(
    sender: str, text: str, cmd: str, db, language: str = "hindi"
) -> str:
    """
    Central routing logic with strict priority:
    State → Intent → Invoice → Greeting → AI Fallback
    """

    # ── 1. Check conversation state (follow-up answer?) ──────────────
    follow_up = resolve_follow_up(sender, text)
    if follow_up:
        intent, value = follow_up
        logger.info(f"Follow-up resolved: {intent} → {value}")
        return handle_command(text, DEMO_COMPANY_ID, db, intent=intent)

    # ── 2. Deterministic intent match ────────────────────────────────
    intent = match_intent(text)
    if intent:
        logger.info(f"Intent matched: {intent}")
        result = handle_command(text, DEMO_COMPANY_ID, db, intent=intent)
        if result is not None:
            return result

    # ── 3. Invoice command patterns ──────────────────────────────────
    if is_invoice_command(text):
        logger.info("Invoice command detected")
        return await handle_invoice_command(
            text, sender, DEMO_COMPANY_ID, db
        )

    # ── 4. Greeting or too short → help menu ─────────────────────────
    if cmd in SKIP_MESSAGES or len(cmd) <= 3:
        return GREETING_REPLY

    # ── 5. AI fallback with per-user cooldown ────────────────────────
    now = time.time()
    last_call = _user_cooldowns.get(sender, 0)

    if now - last_call < USER_AI_COOLDOWN_SECONDS:
        wait = int(USER_AI_COOLDOWN_SECONDS - (now - last_call))
        return f"Thoda ruko boss, {wait} second baad pucho."

    _user_cooldowns[sender] = now
    logger.info(f"AI fallback triggered (lang={language})")

    reply = await generate_business_advice(
        DEMO_COMPANY_ID, text, db, language=language
    )
    return reply
