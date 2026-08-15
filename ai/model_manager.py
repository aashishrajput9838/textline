"""
Model discovery and availability management for Textline.
"""

from config.constants import DEFAULT_GEMINI_MODELS

def get_available_gemini_models(client):
    """Dynamically discover active generateContent models for a given client key."""
    try:
        discovered = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]
        for m in client.models.list():
            m_name = getattr(m, 'name', '') or str(m)
            if 'gemini' in m_name.lower():
                clean_name = m_name.replace('models/', '')
                if clean_name not in discovered and "1.5" not in clean_name and "2.0" not in clean_name and "2.5-pro" not in clean_name and "experimental" not in clean_name:
                    discovered.append(clean_name)
        if discovered:
            return discovered
    except Exception:
        pass
    return DEFAULT_GEMINI_MODELS
