"""
Environment settings and API key management for Textline.
"""

import os
import sys

# PyInstaller creates a temp folder and stores path in _MEIPASS
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    env_file = os.path.join(exe_dir, '.env')
    try:
        from dotenv import load_dotenv
        if os.path.exists(env_file):
            load_dotenv(env_file)
        else:
            load_dotenv()
    except ImportError:
        pass
else:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

def load_api_keys_map():
    """
    Structured dynamic mapping of custom key IDs / aliases to actual Gemini API keys.
    """
    keys_map = {}
    default_key = os.environ.get("GEMINI_API_KEY")
    if default_key and default_key.strip():
        keys_map["default"] = default_key
        
    for env_var, env_val in os.environ.items():
        if env_var.upper().startswith("GEMINI_API_KEY_") and env_val and env_val.strip():
            raw_key_id = env_var[15:]
            if raw_key_id.lower() in ("1_textline_gemini_9838_alreasoningvalidationsystem", "textline_gemini_9838_alreasoningvalidationsystem"):
                canonical_id = "1_textline_gemini_9838_AlReasoningValidationSystem"
            elif raw_key_id.lower() in ("2_textline_gemini_9838_academicuniverseservice", "textline_gemini_9838_academicuniverseservice"):
                canonical_id = "2_textline_gemini_9838_AcademicUniverseService"
            else:
                canonical_id = raw_key_id

            if canonical_id.lower() not in [k.lower() for k in keys_map]:
                keys_map[canonical_id] = env_val
    return keys_map

# Load dynamic API keys mapping
API_KEYS_MAP = load_api_keys_map()

# OpenAI Backup Provider Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
