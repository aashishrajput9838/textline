"""
OpenAI Vision Fallback Provider for Textline.
"""

import sys
import os

try:
    import openai
except ImportError:
    openai = None

from config.settings import OPENAI_API_KEY

def generate_content_openai_fallback(prompt, base64_image_url):
    """Backup Vision content generator using OpenAI gpt-4o-mini (Graceful Fail)."""
    print("[OPENAI] entering fallback")
    
    # Dynamically resolve openai module and API key to respect test patches on app.openai / app.OPENAI_API_KEY
    app_module = sys.modules.get("app")
    openai_mod = getattr(app_module, "openai", None) or openai
    api_key = getattr(app_module, "OPENAI_API_KEY", None) or OPENAI_API_KEY
    if not api_key or api_key == "YOUR_OPENAI_API_KEY":
        api_key = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")

    if not openai_mod:
        print("[!] OpenAI fallback skipped: 'openai' Python package is not installed.")
        return None
    if not api_key or api_key in ("YOUR_OPENAI_API_KEY", ""):
        print("[!] OpenAI fallback skipped: API key not found / not configured in .env.")
        return None

    try:
        print("[OPENAI] request started (gpt-4o-mini)...")
        client_oai = openai_mod.OpenAI(api_key=api_key)
        response = client_oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": base64_image_url
                            }
                        }
                    ]
                }
            ]
        )
        print(f"[OPENAI] request returned: {'success' if response else 'empty response'}")
        if response and response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
    except Exception as oai_err:
        print(f"[!] OpenAI Fallback Error: {oai_err}")
    return None
