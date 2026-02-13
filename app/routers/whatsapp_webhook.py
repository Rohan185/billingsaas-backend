"""
WhatsApp Cloud API Webhook receiver.
- GET  /api/webhook/whatsapp  → verification handshake
- POST /api/webhook/whatsapp  → incoming message handler with command engine + AI fallback
"""
import os
import time
import logging
from fastapi import APIRouter, Query, Request, HTTPException
from app.whatsapp_service import send_whatsapp_text
from app.whatsapp_commands import handle_command, COMMANDS
from app.whatsapp_invoice_commands import is_invoice_command, handle_invoice_command
from app.ai_advisor_service import generate_business_advice
from app.database import SessionLocal

logger = logging.getLogger("whatsapp_webhook")

router = APIRouter(prefix="/api/webhook", tags=["WhatsApp Webhook"])

# ── Hardcoded for demo — replace with phone→company lookup later ──
DEMO_COMPANY_ID = "93f43afe-5844-4c2a-9f16-eaf07e0543d5"

# ── Per-user cooldown: 30 seconds between AI calls ──
_user_cooldowns: dict[str, float] = {}
USER_COOLDOWN_SECONDS = 30

# ── Greetings / short messages that skip AI ──
SKIP_MESSAGES = {"hi", "hello", "hey", "ok", "okay", "yes", "no", "thanks", "thank you", "bye", "hm", "hmm", "ya", "haan", "nahi"}

GREETING_REPLY = (
    "👋 Hello! I'm your Business Assistant.\n\n"
    "Try these commands:\n"
    "• *revenue* — Last 30 days revenue\n"
    "• *profit* — Profit summary\n"
    "• *low stock* — Stock alerts\n"
    "• *send last invoice* — Send latest invoice\n"
    "• *send invoice to <name>* — Send to customer\n\n"
    "Or ask me anything about your business!"
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
    Handle incoming WhatsApp messages.
    1. Check known commands (revenue, profit, low stock)
    2. Check invoice commands (send last invoice, send to <name>, copy)
    3. Filter greetings and short messages
    4. Enforce per-user cooldown
    5. Fallback to AI Business Advisor
    """
    body = await request.json()

    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                for msg in messages:
                    if msg.get("type") != "text":
                        continue

                    sender = msg["from"]
                    text = msg["text"]["body"]
                    cmd = text.strip().lower()
                    msg_id = msg.get("id", "")

                    logger.info(
                        f"[WhatsApp] From: {sender} | Msg: {text} | ID: {msg_id}"
                    )

                    db = SessionLocal()
                    try:
                        if cmd in COMMANDS:
                            # ── Known data command ──
                            reply = handle_command(text, DEMO_COMPANY_ID, db)

                        elif is_invoice_command(text):
                            # ── Invoice command (send, copy) ──
                            reply = await handle_invoice_command(
                                text, sender, DEMO_COMPANY_ID, db
                            )

                        elif cmd in SKIP_MESSAGES or len(cmd) <= 5:
                            # ── Greeting or too short ──
                            reply = GREETING_REPLY

                        else:
                            # ── AI fallback with per-user cooldown ──
                            now = time.time()
                            last_call = _user_cooldowns.get(sender, 0)

                            if now - last_call < USER_COOLDOWN_SECONDS:
                                wait = int(USER_COOLDOWN_SECONDS - (now - last_call))
                                reply = f"⏳ Please wait {wait} seconds before asking again."
                            else:
                                _user_cooldowns[sender] = now
                                reply = await generate_business_advice(
                                    DEMO_COMPANY_ID, text, db
                                )
                    except Exception as e:
                        logger.error(f"Command/AI error: {e}")
                        reply = "⚠️ Something went wrong. Please try again."
                    finally:
                        db.close()

                    await send_whatsapp_text(to_number=sender, message=reply)

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return {"status": "ok"}

