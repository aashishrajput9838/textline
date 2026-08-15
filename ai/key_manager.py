"""
API Key Discovery and Key Management for Textline.
"""

import os
from config.settings import API_KEYS_MAP

def discover_all_gemini_keys():
    """Dynamically discovers all GEMINI_API_KEY_* environment variables from .env and API_KEYS_MAP,
    deduplicating key identifiers case-insensitively while preserving canonical casing for the first seen key ID.
    """
    discovered_keys = {}
    seen_normalized = set()
    
    # 1. First add all structured keys from API_KEYS_MAP
    for k_id, k_val in API_KEYS_MAP.items():
        if k_val and k_val.strip() and k_val != "YOUR_GEMINI_API_KEY":
            normalized_id = k_id.lower()
            if normalized_id not in seen_normalized:
                seen_normalized.add(normalized_id)
                discovered_keys[k_id] = k_val

    # 2. Check os.environ for any additional GEMINI_API_KEY_* variables
    for env_var, env_val in os.environ.items():
        if env_var.upper().startswith("GEMINI_API_KEY_") and env_val and env_val.strip():
            raw_key_id = env_var[15:]
            if raw_key_id.lower() in ("1_textline_gemini_9838_alreasoningvalidationsystem", "textline_gemini_9838_alreasoningvalidationsystem"):
                canonical_id = "1_textline_gemini_9838_AlReasoningValidationSystem"
            elif raw_key_id.lower() in ("2_textline_gemini_9838_academicuniverseservice", "textline_gemini_9838_academicuniverseservice"):
                canonical_id = "2_textline_gemini_9838_AcademicUniverseService"
            else:
                canonical_id = raw_key_id

            normalized_id = canonical_id.lower()
            if normalized_id not in seen_normalized:
                seen_normalized.add(normalized_id)
                discovered_keys[canonical_id] = env_val

    return discovered_keys
