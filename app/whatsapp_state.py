"""
WhatsApp Conversation State Machine.
Tracks per-phone-number session for multi-turn conversations.

Handles:
- Awaiting period selection (7/30/90 days)
- Awaiting customer name for invoice
- Awaiting clarification

Session expires after 5 minutes of inactivity.
"""
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("whatsapp_state")

SESSION_TIMEOUT = 300  # 5 minutes


@dataclass
class UserSession:
    """Pending conversation state for a single user."""
    pending_intent: str = ""          # e.g. "REVENUE", "INVOICE_SEND"
    awaiting: str = ""                # what we're waiting for: "period", "customer_name", etc.
    options: list[str] = field(default_factory=list)
    timestamp: float = 0.0


# ── In-memory store: phone_number → session ──
_sessions: dict[str, UserSession] = {}


def get_session(phone: str) -> UserSession | None:
    """Get active session if exists and not expired."""
    session = _sessions.get(phone)
    if not session:
        return None
    if time.time() - session.timestamp > SESSION_TIMEOUT:
        clear_session(phone)
        return None
    return session


def set_session(phone: str, intent: str, awaiting: str, options: list[str] | None = None):
    """Create or update a session for a phone number."""
    _sessions[phone] = UserSession(
        pending_intent=intent,
        awaiting=awaiting,
        options=options or [],
        timestamp=time.time(),
    )
    logger.info(f"Session set: {phone} → intent={intent}, awaiting={awaiting}")


def clear_session(phone: str):
    """Clear session for a phone number."""
    _sessions.pop(phone, None)


def resolve_follow_up(phone: str, text: str) -> tuple[str, str] | None:
    """
    Check if this message is a follow-up to a pending question.
    Returns (intent, resolved_value) or None if not a follow-up.
    """
    session = get_session(phone)
    if not session:
        return None

    cmd = text.strip().lower()

    # ── Period selection ──
    if session.awaiting == "period":
        period_map = {
            "7": "7", "7 din": "7", "week": "7", "hafta": "7",
            "30": "30", "30 din": "30", "month": "30", "mahina": "30",
            "90": "90", "3 mahina": "90", "quarter": "90", "3 month": "90",
            "1": "7", "2": "30", "3": "90",  # numbered options
        }
        period = period_map.get(cmd)
        if period:
            clear_session(phone)
            return (session.pending_intent, period)

    # ── Customer name ──
    if session.awaiting == "customer_name":
        if len(cmd) >= 2:
            clear_session(phone)
            return (session.pending_intent, cmd)

    # If we got here, user didn't answer the question
    # Clear stale session and return None to process as new message
    clear_session(phone)
    return None
