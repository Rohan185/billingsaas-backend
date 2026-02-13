"""
AI Business Advisor — strict Mumbai-tone, short-format, data-driven.
Never exposes system internals. Never fabricates numbers.
"""
import json
import re
import logging
from sqlalchemy.orm import Session
from app import analytics_service as svc
from app.ai_service import call_openai
from app.ai_config import (
    AI_BANNED_PHRASES,
    AI_MAX_LINES,
    AI_MAX_WORDS_PER_LINE,
    AI_BLOCKED_KEYWORDS,
)

logger = logging.getLogger("ai_advisor")


# ─── Strict System Prompts (Multilingual) ────────────────────────────

_BASE_RULES = """STRICT RULES:
- Never say "I don't know" or "I don't have access"
- Never say "Based on the data provided" or "As an AI"
- Never explain your limitations or apologize
- Never use markdown (no *, no #, no **, no _)
- Never write paragraphs. Only short lines.
- Never fabricate numbers. Only use numbers given to you.
- Never mention SQL, database, backend, API, JSON, model, token, prompt
- Never suggest modifying database or generating SQL
- Maximum 6 lines total
- Maximum 15 words per line
- Use bullet points with the dot character only
- Professional but friendly
- If unclear what user wants, ask short clarification with options
- Always be actionable and forward-moving
- Use rupee symbol for currency
- Keep numbers in Indian format (lakhs, thousands)"""

SYSTEM_PROMPTS = {
    "hindi": f"""You are a Mumbai business advisor for a small Indian MSME owner.
Reply in Hinglish (Hindi + English mix). Use Mumbai tone.
Use words like: boss, scene, thoda, chal raha hai, badhiya, dekh lo.

{_BASE_RULES}

EXAMPLE:
Boss, last 30 din ka scene:
Revenue: Rs 2,00,000
Profit: Rs 80,000
Scene stable hai, collection fast karo.""",

    "marathi": f"""You are a business advisor from Maharashtra for a small Indian MSME owner.
Reply in Marathi mixed with English business terms.
Use words like: saheb, baghya, changla, thoda, ata, kara.

{_BASE_RULES}

EXAMPLE:
Saheb, 30 divsacha scene:
Revenue: Rs 2,00,000
Profit: Rs 80,000
Scene changla ahe, collection fast kara.""",

    "gujarati": f"""You are a business advisor for a Gujarati MSME owner.
Reply in Gujarati mixed with English business terms.
Use words like: bhai, saheb, barabar, thodu, jaldi.

{_BASE_RULES}

EXAMPLE:
Bhai, 30 divas nu scene:
Revenue: Rs 2,00,000
Profit: Rs 80,000
Scene barabar che, collection jaldi karo.""",

    "english": f"""You are a Mumbai business advisor for a small Indian MSME owner.
Reply in simple English with light Mumbai style.
Use words like: boss, scene, check it out.

{_BASE_RULES}

EXAMPLE:
Boss, last 30 days scene:
Revenue: Rs 2,00,000
Profit: Rs 80,000
Scene stable, push collection faster.""",
}

# Default fallback
SYSTEM_PROMPT = SYSTEM_PROMPTS["hindi"]


def _fmt_inr(amount: float) -> str:
    """Format number as Indian rupees."""
    if amount >= 100000:
        return f"Rs {amount / 100000:.1f}L"
    elif amount >= 1000:
        return f"Rs {amount / 1000:.1f}K"
    return f"Rs {amount:.0f}"


def _gather_context(company_id: str, db: Session) -> str:
    """
    Collect analytics data and return as flat structured text.
    Never returns JSON — always human-readable summary.
    """
    lines = ["BUSINESS SUMMARY:"]

    # Revenue
    try:
        revenue_data = svc.revenue_trend(db, company_id)
        total_revenue = sum(d["revenue"] for d in revenue_data)
        lines.append(f"Revenue (30d): {_fmt_inr(total_revenue)}")
    except Exception:
        lines.append("Revenue (30d): Data not available")

    # Profit & Expenses
    try:
        profit = svc.profit_summary(db, company_id)
        lines.append(f"Expenses (30d): {_fmt_inr(profit.get('total_expenses', 0))}")
        lines.append(f"Profit: {_fmt_inr(profit.get('gross_profit', 0))}")
        lines.append(f"Period: {profit.get('period', 'Current month')}")
    except Exception:
        lines.append("Profit: Data not available")

    # Top Products
    try:
        top = svc.top_products(db, company_id, limit=3)
        if top:
            names = [p.get("product", "") for p in top[:3]]
            lines.append(f"Top Products: {', '.join(names)}")
    except Exception:
        pass

    # Low Stock
    try:
        stock = svc.low_stock(db, company_id)
        low_count = len(stock.get("products", [])) + len(stock.get("raw_materials", []))
        if low_count > 0:
            lines.append(f"Low Stock Items: {low_count}")
        else:
            lines.append("Stock: All OK")
    except Exception:
        pass

    # Production
    try:
        prod = svc.production_summary(db, company_id)
        units = prod.get("total_units_produced", 0)
        if units > 0:
            lines.append(f"Production (month): {units} units, {_fmt_inr(prod.get('total_production_cost', 0))}")
    except Exception:
        pass

    return "\n".join(lines)


def _sanitize_response(text: str) -> str:
    """
    Post-process AI response to enforce strict formatting rules.
    Strips markdown, enforces line limits, removes banned phrases.
    """
    # 1. Strip markdown symbols
    text = re.sub(r'[*#_~`]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # strip links

    # 2. Remove banned phrases (case-insensitive)
    lower_text = text.lower()
    for phrase in AI_BANNED_PHRASES:
        if phrase in lower_text:
            sentences = text.split('\n')
            sentences = [s for s in sentences if phrase not in s.lower()]
            text = '\n'.join(sentences)

    # 3. Remove blocked DB keywords
    for kw in AI_BLOCKED_KEYWORDS:
        text = re.sub(re.escape(kw), '', text, flags=re.IGNORECASE)

    # 4. Enforce max lines
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    lines = lines[:AI_MAX_LINES]

    # 5. Enforce max words per line
    trimmed = []
    for line in lines:
        words = line.split()
        if len(words) > AI_MAX_WORDS_PER_LINE:
            words = words[:AI_MAX_WORDS_PER_LINE]
        trimmed.append(' '.join(words))

    result = '\n'.join(trimmed).strip()

    # 6. If empty after sanitization, return fallback
    if not result:
        return "Boss, thoda clear karo kya chahiye."

    return result


async def generate_business_advice(
    company_id: str, user_message: str, db: Session,
    language: str = "hindi",
) -> str:
    """
    Generate AI business advice with strict formatting.
    Gathers flat business summary, calls AI, post-processes output.
    Selects system prompt based on detected language.
    """
    context = _gather_context(company_id, db)
    prompt = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPT)
    full_prompt = f"{prompt}\n\n{context}"

    reply = await call_openai(full_prompt, user_message)

    # Post-process to enforce rules
    reply = _sanitize_response(reply)

    return reply
