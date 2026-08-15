import engineio.async_drivers.threading
import sys
import os
import time
import io
import base64
import hashlib
import threading
import functools
from PIL import Image, ImageGrab
import pyperclip

from utils.logging import safe_print, builtins_print
print = safe_print

from google import genai
try:
    import openai
except ImportError:
    openai = None
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

# PyInstaller creates a temp folder and stores path in _MEIPASS
if getattr(sys, 'frozen', False):
    template_dir = os.path.join(sys._MEIPASS, 'templates')
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
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

from server.flask_app import create_app, test_key_model_diagnostic, run_all_keys_health_check
from server.socket_events import register_socket_events

app, socketio = create_app()
register_socket_events(socketio)


from config.settings import load_api_keys_map, API_KEYS_MAP, OPENAI_API_KEY
from config.constants import DEFAULT_GEMINI_MODELS, SUPPORTED_HEALTH_MODELS, PROJECT_METADATA_MAP
from utils.timing import generate_pipeline_id
from ai.health_registry import (
    KEY_MODEL_HEALTH_REGISTRY,
    set_socketio as set_health_socketio,
    classify_error_code_and_status,
    update_key_model_health,
    get_key_model_status,
    is_key_model_known_unavailable
)
from ai.key_manager import discover_all_gemini_keys
from ai.model_manager import get_available_gemini_models
from ai.openai import generate_content_openai_fallback
from ai.gemini import generate_content_with_fallback
from pipeline.logger import emit_pipeline_log, set_socketio as set_logger_socketio
from pipeline.errors import NoAvailableModelError, PipelineTimeoutError

set_health_socketio(socketio)
set_logger_socketio(socketio)



from processing.formatter import format_clipboard_output
from image.validator import validate_image
from image.converter import convert_to_rgb, image_to_png_bytes, image_to_base64_url
from image.preview import build_image_preview_payload
from clipboard.reader import read_clipboard_image
from clipboard.writer import write_to_clipboard
from clipboard.hasher import compute_image_hash
from clipboard.monitor import ClipboardMonitor, monitor_clipboard
from pipeline.stages import PipelineStage
from pipeline.pipeline import ScreenshotPipeline, set_pipeline_socketio

set_pipeline_socketio(socketio)


# Note: discover_all_gemini_keys imported from ai.key_manager


# Note: test_key_model_diagnostic, run_all_keys_health_check, routes, socket handlers imported from server package


def print_startup_health_check():
    """Prints server startup health check to terminal."""
    valid_gemini_keys = [k for k, v in API_KEYS_MAP.items() if v and v not in ("YOUR_GEMINI_API_KEY", "")]
    has_openai = bool(OPENAI_API_KEY and OPENAI_API_KEY not in ("YOUR_OPENAI_API_KEY", ""))
    
    print("\n" + "=" * 55)
    print("=== TEXTLINE MULTI-PROVIDER AI SERVER INITIALIZED ===")
    print("=" * 55)
    print(f"[+] Gemini API Keys Loaded: {len(valid_gemini_keys)} key ID(s) ({', '.join(valid_gemini_keys)})")
    print(f"[+] OpenAI Vision Fallback:  {'Active (gpt-4o-mini)' if has_openai else 'Disabled (Key Not Configured)'}")
    print("=" * 55 + "\n")

if __name__ == '__main__':
    # Print Server Health Check Log
    print_startup_health_check()

    # Start clipboard listener in a daemon thread so it runs in the background
    clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
    clipboard_thread.start()

    # Launch Flask-SocketIO Web Server
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=True)
