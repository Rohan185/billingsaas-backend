"""
Central AI configuration — single source of truth for model, limits, and guardrails.
"""

# ── Model ──
AI_MODEL = "gpt-4o-mini"

# ── Rate Limiting ──
AI_RATE_LIMIT_SECONDS = 10          # global cooldown between AI calls
USER_AI_COOLDOWN_SECONDS = 10       # per-user cooldown

# ── Token Safety ──
AI_MAX_TOKENS = 200                 # max output tokens per call
AI_TEMPERATURE = 0.3                # lower = more deterministic
AI_MAX_PROMPT_CHARS = 2000          # trim business data to this limit

# ── Allowed models whitelist ──
AI_ALLOWED_MODELS = frozenset({"gpt-4o-mini"})

# ── Output Guardrails ──
AI_MAX_LINES = 6                    # max lines in AI response
AI_MAX_WORDS_PER_LINE = 15          # max words per line

# ── Banned Phrases — AI must NEVER say these ──
AI_BANNED_PHRASES = [
    "i don't know",
    "i don't have access",
    "i don't have enough",
    "i cannot access",
    "i'm unable to",
    "i am unable to",
    "based on the data provided",
    "based on the structured data",
    "based on the available data",
    "as an ai",
    "as a language model",
    "i'm just an ai",
    "i don't have real-time",
    "i cannot provide",
    "unfortunately",
    "i apologize",
    "i'm sorry but",
    "let me clarify",
    "it appears that",
    "it seems like",
    "according to the provided",
    "sql",
    "database",
    "backend",
    "api",
    "json",
    "model",
    "token",
    "prompt",
]

# ── DB Safety: AI must never suggest these ──
AI_BLOCKED_KEYWORDS = [
    "delete", "drop", "truncate", "insert into",
    "update set", "alter table", "create table",
    "select * from",
]
