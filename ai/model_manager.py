"""
Model discovery and availability management for Textline.
"""

from config.constants import DEFAULT_GEMINI_MODELS, SUPPORTED_HEALTH_MODELS

def get_available_gemini_models(client=None):
    """
    Dynamically discover active generateContent models for a given client key.
    Strictly constrained to SUPPORTED_HEALTH_MODELS single source of truth and canonical index order.
    """
    allowed_models = set(SUPPORTED_HEALTH_MODELS)
    if client:
        try:
            discovered = []
            for m in client.models.list():
                m_name = getattr(m, 'name', '') or str(m)
                clean_name = m_name.replace('models/', '')
                if clean_name in allowed_models and clean_name not in discovered:
                    discovered.append(clean_name)
            if discovered:
                return [m for m in SUPPORTED_HEALTH_MODELS if m in discovered]
        except Exception:
            pass
    return list(DEFAULT_GEMINI_MODELS)
