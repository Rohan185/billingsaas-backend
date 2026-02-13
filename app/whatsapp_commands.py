"""
WhatsApp command engine — maps text commands to analytics queries
and returns WhatsApp-friendly formatted responses.

Supports:
- Exact keyword matching
- Fuzzy Hindi/English alias matching
- AI intent classifier fallback (cheap classification call)
- New commands: production, top products, pending, help
"""
import re
import logging
from sqlalchemy.orm import Session
from app import analytics_service as svc

logger = logging.getLogger("whatsapp_commands")


def _fmt_inr(amount: float) -> str:
    """Format number as Indian rupees."""
    if amount >= 100000:
        return f"Rs {amount / 100000:.1f}L"
    elif amount >= 1000:
        return f"Rs {amount / 1000:.1f}K"
    return f"Rs {amount:.0f}"


# ── Command Handlers ─────────────────────────────────────────────────

def _cmd_revenue(company_id: str, db: Session, days: int = 30) -> str:
    data = svc.revenue_trend(db, company_id)
    total = sum(d["revenue"] for d in data)
    return (
        f"Revenue (Last {days} Days)\n\n"
        f"Total: {_fmt_inr(total)}\n"
        f"{len(data)} din me transactions aaye."
    )


def _cmd_profit(company_id: str, db: Session) -> str:
    p = svc.profit_summary(db, company_id)
    return (
        f"Profit Summary - {p['period']}\n\n"
        f"Revenue: {_fmt_inr(p['revenue'])}\n"
        f"Expenses: {_fmt_inr(p['total_expenses'])}\n"
        f"Profit: {_fmt_inr(p['gross_profit'])}"
    )


def _cmd_low_stock(company_id: str, db: Session) -> str:
    data = svc.low_stock(db, company_id)
    products = data.get("products", [])
    raw_materials = data.get("raw_materials", [])

    if not products and not raw_materials:
        return "Stock sab theek hai boss. Koi low stock nahi."

    lines = ["Low Stock Alert\n"]
    for p in products:
        lines.append(f". {p['name']} ({p['stock']} {p.get('unit', 'pcs')})")
    for r in raw_materials:
        lines.append(f". {r['name']} ({r['stock']} {r.get('unit', 'pcs')})")

    return "\n".join(lines)


def _cmd_production(company_id: str, db: Session) -> str:
    p = svc.production_summary(db, company_id)
    return (
        f"Production Summary - {p['period']}\n\n"
        f"Units Produced: {p['total_units_produced']}\n"
        f"Batches: {p['total_batches']}\n"
        f"Cost: {_fmt_inr(p['total_production_cost'])}"
    )


def _cmd_top_products(company_id: str, db: Session) -> str:
    top = svc.top_products(db, company_id, limit=5)
    if not top:
        return "Abhi tak koi product sell nahi hua boss."

    lines = ["Top Products\n"]
    for i, p in enumerate(top, 1):
        lines.append(f"{i}. {p['product']} - {p['qty_sold']} sold ({_fmt_inr(p['revenue'])})")

    return "\n".join(lines)


HELP_REPLY = (
    "Business Assistant\n\n"
    "Commands:\n"
    ". revenue - Last 30 days revenue\n"
    ". profit - Profit summary\n"
    ". low stock - Stock alerts\n"
    ". production - Production summary\n"
    ". top products - Best sellers\n"
    ". send last invoice - Send latest invoice\n"
    ". send invoice to <name>\n\n"
    "Ya kuch bhi pucho business ke baare me!"
)


# ── Intent Matching ──────────────────────────────────────────────────
# Each intent maps to keyword patterns (Hindi + English + slang)

INTENT_PATTERNS: dict[str, list[str]] = {
    "REVENUE": [
        "revenue", "sales", "bikri", "sell", "kitna aaya",
        "paisa kitna", "revenue ka scene", "total sales",
        "earning", "income", "kamai", "turnover",
    ],
    "PROFIT": [
        "profit", "margin", "munafa", "fayda", "net profit",
        "gross profit", "profit kitna", "profit scene",
        "kamaa", "earn",
    ],
    "LOW_STOCK": [
        "low stock", "lowstock", "stock alert", "stock khatam",
        "maal khatam", "stock kam", "stock check", "inventory",
        "stock scene", "maal kitna", "godown",
    ],
    "PRODUCTION": [
        "production", "manufacturing", "produce", "utpaadan",
        "batch", "factory", "production scene", "kitna bana",
    ],
    "TOP_PRODUCTS": [
        "top product", "best seller", "sabse zyada",
        "hit product", "popular", "top selling", "best product",
    ],
    "HELP": [
        "help", "commands", "menu", "kya kar sakta",
        "options", "features", "madad",
    ],
}

# Pre-compile patterns for efficiency
_compiled_patterns: dict[str, list[re.Pattern]] = {}
for intent, keywords in INTENT_PATTERNS.items():
    _compiled_patterns[intent] = [
        re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords
    ]


# ── Intent Handlers Map ──────────────────────────────────────────────

INTENT_HANDLERS = {
    "REVENUE": _cmd_revenue,
    "PROFIT": _cmd_profit,
    "LOW_STOCK": _cmd_low_stock,
    "PRODUCTION": _cmd_production,
    "TOP_PRODUCTS": _cmd_top_products,
}


def match_intent(text: str) -> str | None:
    """
    Match user text to a known intent using keyword patterns.
    Returns intent string or None if no match.
    """
    cmd = text.strip().lower()

    # 1. Exact match on first word
    first_word = cmd.split()[0] if cmd else ""
    for intent, keywords in INTENT_PATTERNS.items():
        if first_word in keywords or cmd in keywords:
            return intent

    # 2. Fuzzy match - check if any keyword appears in the message
    for intent, patterns in _compiled_patterns.items():
        for pattern in patterns:
            if pattern.search(cmd):
                return intent

    return None


def handle_command(
    text: str, company_id: str, db: Session, intent: str | None = None
) -> str:
    """
    Execute a command based on intent.
    If intent is provided, use it directly. Otherwise, match from text.
    Returns a WhatsApp-formatted string reply.
    """
    if intent is None:
        intent = match_intent(text)

    if intent == "HELP":
        return HELP_REPLY

    handler = INTENT_HANDLERS.get(intent)
    if handler:
        try:
            return handler(company_id, db)
        except Exception as e:
            logger.error(f"Command handler error [{intent}]: {e}")
            return "Thoda problem hua boss. Dobara try karo."

    return None  # No match — caller should try AI fallback
