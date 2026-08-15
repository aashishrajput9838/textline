"""
Model discovery and availability management for Textline.
"""

from config.constants import DEFAULT_GEMINI_MODELS

EXCLUDED_MODEL_KEYWORDS = [
    "1.5", "2.0", "2.5-pro", "experimental",
    "tts", "video", "audio", "embed", "imagen", "bidi", "realtime", "computer-use"
]

def get_available_gemini_models(client):
    """Dynamically discover active generateContent models for a given client key."""
    try:
        discovered = list(DEFAULT_GEMINI_MODELS)
        for m in client.models.list():
            m_name = getattr(m, 'name', '') or str(m)
            if 'gemini' in m_name.lower():
                clean_name = m_name.replace('models/', '')
                clean_lower = clean_name.lower()
                if clean_name not in discovered:
                    if not any(kw in clean_lower for kw in EXCLUDED_MODEL_KEYWORDS):
                        discovered.append(clean_name)
        if discovered:
            return discovered
    except Exception:
        pass
    return list(DEFAULT_GEMINI_MODELS)
