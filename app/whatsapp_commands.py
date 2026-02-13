"""
WhatsApp command engine — maps text commands to analytics queries
and returns WhatsApp-friendly formatted responses.
"""
from sqlalchemy.orm import Session
from app import analytics_service as svc


def _fmt_inr(amount: float) -> str:
    """Format number as ₹ with Indian comma grouping."""
    return f"₹{amount:,.2f}"


def _cmd_revenue(company_id: str, db: Session) -> str:
    data = svc.revenue_trend(db, company_id)
    total = sum(d["revenue"] for d in data)
    return f"📊 *Revenue (Last 30 Days)*\n\n{_fmt_inr(total)}"


def _cmd_profit(company_id: str, db: Session) -> str:
    p = svc.profit_summary(db, company_id)
    lines = [
        f"💰 *Profit Summary — {p['period']}*",
        "",
        f"Revenue: {_fmt_inr(p['revenue'])}",
        f"Expenses: {_fmt_inr(p['total_expenses'])}",
        f"Gross Profit: {_fmt_inr(p['gross_profit'])}",
    ]
    return "\n".join(lines)


def _cmd_low_stock(company_id: str, db: Session) -> str:
    data = svc.low_stock(db, company_id)
    products = data.get("products", [])
    raw_materials = data.get("raw_materials", [])

    if not products and not raw_materials:
        return "✅ No low stock items."

    lines = ["⚠️ *Low Stock Alert*", ""]
    for p in products:
        lines.append(f"• {p['name']} ({p['stock']} {p.get('unit', 'pcs')})")
    for r in raw_materials:
        lines.append(f"• {r['name']} ({r['stock']} {r.get('unit', 'pcs')})")

    return "\n".join(lines)


UNKNOWN_REPLY = (
    "❓ Unknown command.\n\n"
    "Try:\n"
    "• *revenue*\n"
    "• *profit*\n"
    "• *low stock*"
)

COMMANDS = {
    "revenue": _cmd_revenue,
    "profit": _cmd_profit,
    "low stock": _cmd_low_stock,
    "lowstock": _cmd_low_stock,
    "low_stock": _cmd_low_stock,
}


def handle_command(text: str, company_id: str, db: Session) -> str:
    """
    Parse user text and dispatch to the matching command handler.
    Returns a WhatsApp-formatted string reply.
    """
    cmd = text.strip().lower()
    handler = COMMANDS.get(cmd)
    if handler:
        return handler(company_id, db)
    return UNKNOWN_REPLY
