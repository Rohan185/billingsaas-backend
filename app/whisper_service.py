"""
Groq Whisper Transcription Service.
Uses Groq's whisper-large-v3-turbo for fast, accurate audio transcription.

Features:
- Auto language detection (Hindi, Marathi, Gujarati, English)
- No forced translation
- Clean trimmed output
- Safe error handling
"""
import os
import io
import logging
from groq import Groq

logger = logging.getLogger("whisper_service")

# ── Config ──
WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
WHISPER_MAX_FILE_MB = 10

# ── Language detection keywords for reply tone ──
HINDI_MARKERS = {
    "kya", "hai", "ka", "ki", "ko", "se", "me", "ye", "wo", "kaise",
    "kitna", "kitne", "kitni", "kahan", "kyun", "kab", "aaj", "kal",
    "scene", "boss", "bhai", "yaar", "maal", "paisa", "bikri",
    "bhejo", "bhej", "bana", "banao", "dikha", "dikhao", "bata",
    "thoda", "zyada", "khatam", "kam", "bahut", "acha", "sahi",
    "nahi", "haan", "aur", "lekin", "phir", "abhi", "pehle",
}

MARATHI_MARKERS = {
    "kay", "ahe", "cha", "chi", "che", "ya", "te", "he", "mala",
    "kasa", "kiti", "kuthe", "ka", "ata", "udya", "mhanje",
    "sangha", "dya", "ghe", "watla", "kela", "zala", "nahi",
    "pan", "ani", "tar", "mag", "baghya",
}

GUJARATI_MARKERS = {
    "su", "che", "ma", "thi", "ne", "par", "kem", "ketlu",
    "kya", "aaje", "kale", "bhai", "saheb", "kemnu", "batavo",
    "hoy", "nathi", "pan", "ane", "to", "pachi",
}


def detect_language(text: str) -> str:
    """
    Detect likely language from transcribed text.
    Returns: 'hindi', 'marathi', 'gujarati', or 'english'
    """
    words = set(text.lower().split())

    hindi_score = len(words & HINDI_MARKERS)
    marathi_score = len(words & MARATHI_MARKERS)
    gujarati_score = len(words & GUJARATI_MARKERS)

    if marathi_score >= 2 and marathi_score > hindi_score:
        return "marathi"
    if gujarati_score >= 2 and gujarati_score > hindi_score:
        return "gujarati"
    if hindi_score >= 1:
        return "hindi"
    return "english"


async def transcribe_audio_bytes(audio_bytes: bytes) -> tuple[str, str]:
    """
    Transcribe audio using Groq Whisper v3 Turbo.

    Args:
        audio_bytes: Raw audio file bytes

    Returns:
        Tuple of (transcribed_text, detected_language)

    If transcription fails, returns fallback text.
    """
    # Check file size
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > WHISPER_MAX_FILE_MB:
        logger.warning(f"Audio too large: {size_mb:.1f} MB (max {WHISPER_MAX_FILE_MB} MB)")
        return ("__TOO_LARGE__", "hindi")

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.error("GROQ_API_KEY not set")
        return ("__NO_KEY__", "hindi")

    try:
        client = Groq(api_key=api_key)

        # Create file-like object from bytes
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.ogg"  # WhatsApp sends OGG/Opus

        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model=WHISPER_MODEL,
            response_format="text",
        )

        # Groq returns plain text string
        text = str(transcription).strip()

        if not text:
            logger.warning("Whisper returned empty transcription")
            return ("__EMPTY__", "hindi")

        # Detect language
        lang = detect_language(text)

        logger.info(
            f"Transcription OK: lang={lang}, "
            f"chars={len(text)}, words={len(text.split())}"
        )

        return (text, lang)

    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return ("__FAILED__", "hindi")
