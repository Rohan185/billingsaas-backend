"""
Central AI configuration — single source of truth for model and limits.
"""

# ── Model ──
AI_MODEL = "gpt-4o-mini"

# ── Rate Limiting ──
AI_RATE_LIMIT_SECONDS = 60       # 1 call per 60 seconds globally

# ── Token Safety ──
AI_MAX_TOKENS = 200              # max output tokens per call
AI_TEMPERATURE = 0.5             # lower = more deterministic
AI_MAX_PROMPT_CHARS = 1500       # trim business data to this limit

# ── Allowed models whitelist ──
AI_ALLOWED_MODELS = frozenset({"gpt-4o-mini"})
