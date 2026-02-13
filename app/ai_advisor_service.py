"""
AI Business Advisor — gathers real company analytics data and uses
OpenAI gpt-4o-mini to generate contextual business advice.
"""
import json
import logging
from sqlalchemy.orm import Session
from app import analytics_service as svc
from app.ai_service import call_openai

logger = logging.getLogger("ai_advisor")

SYSTEM_PROMPT = (
    "You are a CFO advising a small Indian manufacturing business. "
    "Use the real numbers provided. Be concise, actionable. "
    "Plain text only, no markdown. Use ₹ for currency. "
    "Keep response under 150 words."
)


def _gather_context(company_id: str, db: Session) -> dict:
    """Collect analytics data for AI context."""
    try:
        revenue_data = svc.revenue_trend(db, company_id)
        total_revenue = sum(d["revenue"] for d in revenue_data)
    except Exception:
        total_revenue = 0

    try:
        profit = svc.profit_summary(db, company_id)
    except Exception:
        profit = {"revenue": 0, "total_expenses": 0, "gross_profit": 0}

    try:
        stock = svc.low_stock(db, company_id)
        low_products = len(stock.get("products", []))
        low_materials = len(stock.get("raw_materials", []))
    except Exception:
        low_products = low_materials = 0

    try:
        top = svc.top_products(db, company_id, limit=3)
    except Exception:
        top = []

    return {
        "revenue_30d": total_revenue,
        "profit": profit.get("gross_profit", 0),
        "expenses": profit.get("total_expenses", 0),
        "low_stock_count": low_products + low_materials,
        "top_products": [p.get("product", "") for p in top[:3]],
    }


async def generate_business_advice(
    company_id: str, user_message: str, db: Session
) -> str:
    """
    Generate AI business advice using OpenAI gpt-4o-mini.
    Gathers trimmed analytics, calls AI service, returns formatted reply.
    """
    context = _gather_context(company_id, db)
    context_str = json.dumps(context, default=str)

    full_prompt = f"{SYSTEM_PROMPT}\n\nBusiness data: {context_str}"

    reply = await call_openai(full_prompt, user_message)
    return f"🧠 *AI Business Advisor*\n\n{reply}"
