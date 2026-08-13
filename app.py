import engineio.async_drivers.threading
import sys
import os
import time
import io
import base64
import hashlib
import threading
from PIL import Image, ImageGrab
import pyperclip
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
    template_dir = 'templates'
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

# Initialize Flask App & SocketIO
app = Flask(__name__, template_folder=template_dir)
app.config['SECRET_KEY'] = 'clipboard_gemini_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", ping_timeout=60, ping_interval=25)

# Structured mapping of custom key IDs / aliases to actual Gemini API keys
API_KEYS_MAP = {
    "98381": os.environ.get("GEMINI_API_KEY_98381", os.environ.get("GEMINI_API_KEY")),
    "98382": os.environ.get("GEMINI_API_KEY_98382"),
    "98383": os.environ.get("GEMINI_API_KEY_98383"),
    "98385": os.environ.get("GEMINI_API_KEY_98385"),
    "98386": os.environ.get("GEMINI_API_KEY_98386"),
    "98387": os.environ.get("GEMINI_API_KEY_98387"),
    "98388": os.environ.get("GEMINI_API_KEY_98388"),
    "98389": os.environ.get("GEMINI_API_KEY_98389"),
    "983810": os.environ.get("GEMINI_API_KEY_983810"),
    "aspirinexar": os.environ.get("GEMINI_API_KEY_aspirinexar"),
}

# OpenAI Backup Provider Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")

# Default active Gemini models list for google-genai SDK
DEFAULT_GEMINI_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-latest"]

def get_available_gemini_models(client):
    """Dynamically discover active generateContent models for a given client key."""
    try:
        discovered = ["gemini-flash-latest"]
        for m in client.models.list():
            m_name = getattr(m, 'name', '') or str(m)
            if 'gemini' in m_name.lower():
                clean_name = m_name.replace('models/', '')
                if clean_name not in discovered:
                    discovered.append(clean_name)
        if discovered:
            return discovered
    except Exception:
        pass
    return DEFAULT_GEMINI_MODELS

def generate_content_openai_fallback(prompt, base64_image_url):
    """Backup Vision content generator using OpenAI gpt-4o-mini (Graceful Fail)."""
    if not openai:
        print("[!] OpenAI fallback skipped: 'openai' Python package is not installed.")
        return None
    if not OPENAI_API_KEY or OPENAI_API_KEY in ("YOUR_OPENAI_API_KEY", ""):
        print("[!] OpenAI fallback skipped: API key not found / not configured in .env.")
        return None

    try:
        print("[*] Attempting OpenAI fallback (gpt-4o-mini)...")
        client_oai = openai.OpenAI(api_key=OPENAI_API_KEY)
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
        if response and response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
    except Exception as oai_err:
        print(f"[!] OpenAI Fallback Error: {oai_err}")
    return None

def generate_content_with_fallback(contents, base64_image_url=None):
    """
    Executes content generation using structured Gemini key IDs (98381 -> 983810, aspirinexar).
    Fail-Fast: Skips invalid/dummy/unauthorized keys immediately on first error.
    If ALL Gemini keys fail, gracefully attempts OpenAI (gpt-4o-mini).
    Returns tuple: (raw_answer_text, metadata_dict).
    """
    errors = []
    attempt_count = 0

    valid_keys = {key_id: key_val for key_id, key_val in API_KEYS_MAP.items() if key_val and key_val != "YOUR_GEMINI_API_KEY"}
    
    if not valid_keys:
        gen_key = os.environ.get("GEMINI_API_KEY", "")
        if gen_key:
            valid_keys["DEFAULT"] = gen_key

    # 1. Attempt Gemini multi-key rotation with dynamic model discovery
    for key_id, api_key in valid_keys.items():
        try:
            client = genai.Client(api_key=api_key)
        except Exception as client_err:
            print(f"[!] Failed to initialize Gemini client for Key ID [{key_id}]: {client_err}")
            errors.append(f"Key [{key_id}]: {client_err}")
            continue

        models_to_query = get_available_gemini_models(client)
        
        for model_name in models_to_query:
            attempt_count += 1
            try:
                print(f"[*] Trying Gemini Key ID [{key_id}] with model '{model_name}'...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                if response and response.text:
                    print(f"[+] Success using Gemini Key ID [{key_id}] ({model_name})")
                    meta = {
                        "provider": "Google Gemini",
                        "model": model_name,
                        "key_id": key_id,
                        "is_fallback": attempt_count > 1
                    }
                    return response.text, meta
            except Exception as e:
                err_str = str(e)
                short_err = err_str.split("\n")[0] if "\n" in err_str else err_str
                print(f"[!] Gemini Key ID [{key_id}] ({model_name}) failed: {short_err}")
                errors.append(f"Key [{key_id}] [{model_name}]: {short_err}")
                
                # Fail-Fast: If key is invalid, unauthenticated, forbidden, or model not found/available, skip key immediately
                if any(bad_kw in err_str for bad_kw in [
                    "400", "403", "404", "INVALID_ARGUMENT", "PERMISSION_DENIED", 
                    "NOT_FOUND", "API key not valid", "not available to new users"
                ]):
                    print(f"[!] Key ID [{key_id}] is invalid, restricted, or lacks model access. Skipping key...")
                    break
                
                # If 429 quota exhausted on this model, try next model or next key
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"[!] 429 Quota Limit reached for Key ID [{key_id}] on {model_name}. Trying next model/key...")

    # 2. Graceful Fallback to OpenAI gpt-4o-mini if configured
    if base64_image_url:
        attempt_count += 1
        prompt_str = contents[0] if isinstance(contents, list) and len(contents) > 0 else str(contents)
        openai_result = generate_content_openai_fallback(prompt_str, base64_image_url)
        if openai_result:
            print("[+] Success using OpenAI (gpt-4o-mini) fallback!")
            meta = {
                "provider": "OpenAI",
                "model": "gpt-4o-mini",
                "key_id": "OPENAI",
                "is_fallback": True
            }
            return openai_result, meta

    raise RuntimeError("All Gemini API keys & OpenAI fallbacks failed. Please check your .env configuration!\n\nDetails:\n" + "\n".join(errors))

def format_clipboard_output(raw_answer):
    """Enforces Python Post-Processing Padding (50 single-spaced lines + terminating dot)."""
    clean_code = raw_answer.lstrip() if raw_answer else "No text returned from model."
    return clean_code + "\n" + "\n".join([" "] * 50) + "\n."

def monitor_clipboard():
    """Background thread function to monitor system clipboard for new images."""
    last_image_hash = None
    print("[*] Clipboard monitoring thread started.")

    while True:
        try:
            # Grab image object from Windows clipboard
            clipboard_content = ImageGrab.grabclipboard()

            if isinstance(clipboard_content, Image.Image):
                # Convert PIL Image to PNG bytes
                img_byte_arr = io.BytesIO()
                # Handle RGBA / Palette mode conversions if needed when saving as PNG
                if clipboard_content.mode in ("RGBA", "P"):
                    clipboard_content = clipboard_content.convert("RGB")
                clipboard_content.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()

                # Calculate hash to verify if image is NEW
                current_hash = hashlib.sha256(img_bytes).hexdigest()

                if current_hash != last_image_hash:
                    last_image_hash = current_hash

                    # Convert image bytes to Base64 data URL for UI rendering
                    base64_img = base64.b64encode(img_bytes).decode('utf-8')
                    image_data_url = f"data:image/png;base64,{base64_img}"

                    # 1. Notify frontend: New screenshot detected
                    socketio.emit('status_update', {
                        'status': 'processing',
                        'message': 'New screenshot detected! Processing...',
                        'timestamp': time.strftime("%H:%M:%S")
                    })

                    # 2. Emit Base64 image to frontend for live UI preview
                    socketio.emit('image_preview', {
                        'image_url': image_data_url
                    })

                    # 3. Pure, clean text instructions system prompt
                    prompt = "give me complete code in the given language,\nmake sure -\n1. my code should be very fast in terms of speed.\n2. remove any spaces from the starting of each line in the code.\n\nMost important -- I don't need any explanation or any other content, not even a single irrelevant word. The output should be only the code."
                    
                    try:
                        raw_answer, meta = generate_content_with_fallback([prompt, clipboard_content], base64_image_url=image_data_url)
                        final_clipboard_text = format_clipboard_output(raw_answer)
                        
                        # Auto-copy final formatted text to Windows clipboard
                        pyperclip.copy(final_clipboard_text)

                        # 5. Emit final answer and Done status to frontend with metadata provenance
                        socketio.emit('status_update', {
                            'status': 'success',
                            'message': 'Done! Answer copied to clipboard.',
                            'answer': final_clipboard_text,
                            'timestamp': time.strftime("%H:%M:%S"),
                            'metadata': meta
                        })
                    except Exception as api_err:
                        error_msg = f"AI Generation Error: {str(api_err)}"
                        print(f"[!] {error_msg}")
                        socketio.emit('status_update', {
                            'status': 'error',
                            'message': error_msg,
                            'timestamp': time.strftime("%H:%M:%S")
                        })
                    except Exception as api_err:
                        error_msg = f"AI Generation Error: {str(api_err)}"
                        print(f"[!] {error_msg}")
                        socketio.emit('status_update', {
                            'status': 'error',
                            'message': error_msg,
                            'timestamp': time.strftime("%H:%M:%S")
                        })
        except Exception as e:
            print(f"[!] Clipboard monitor exception: {e}")

        time.sleep(1)

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
            normalized_id = raw_key_id.lower()
            if normalized_id not in seen_normalized:
                seen_normalized.add(normalized_id)
                discovered_keys[raw_key_id] = env_val

    return discovered_keys

def test_single_key_diagnostic(key_id, api_key):
    """Tests a single Gemini API key independently against gemini-flash-latest and measures latency."""
    if not api_key or not api_key.strip() or api_key == "YOUR_GEMINI_API_KEY":
        return {
            "key_id": key_id,
            "model": "gemini-flash-latest",
            "status": "Error",
            "latency_ms": 0,
            "http_code": 400,
            "details": "Not Configured in .env"
        }

    start_time = time.time()
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents="Hi"
        )
        latency = int((time.time() - start_time) * 1000)
        
        if response and response.text:
            return {
                "key_id": key_id,
                "model": "gemini-flash-latest",
                "status": "Working",
                "latency_ms": latency,
                "http_code": 200,
                "details": "PASS"
            }
        else:
            return {
                "key_id": key_id,
                "model": "gemini-flash-latest",
                "status": "Failed",
                "latency_ms": latency,
                "http_code": 200,
                "details": "Empty Response"
            }

    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        err_str = str(e)
        
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            status = "Quota"
            code = 429
            details = "429 Quota Exhausted"
        elif "403" in err_str or "PERMISSION_DENIED" in err_str:
            status = "Unauthorized"
            code = 403
            details = "403 Access Restricted / Denied"
        elif "404" in err_str or "NOT_FOUND" in err_str:
            status = "Error"
            code = 404
            details = "404 Model Unavailable"
        elif "BILLING" in err_str.upper():
            status = "Billing"
            code = 402
            details = "Billing Required"
        elif "400" in err_str or "INVALID_ARGUMENT" in err_str:
            status = "Failed"
            code = 400
            details = "400 Invalid Argument / Key"
        else:
            status = "Error"
            code = 500
            details = err_str.split("\n")[0][:60]

        return {
            "key_id": key_id,
            "model": "gemini-flash-latest",
            "status": status,
            "latency_ms": latency,
            "http_code": code,
            "details": details
        }

def run_all_keys_health_check():
    """Runs independent diagnostic scan across every discovered Gemini API key."""
    all_keys = discover_all_gemini_keys()
    results = []
    
    for key_id, api_key in all_keys.items():
        res = test_single_key_diagnostic(key_id, api_key)
        results.append(res)
        
    return results

@app.route('/')
def index():
    """Render the main single-page dashboard."""
    return render_template('index.html')

@app.route('/api/test-keys')
def api_test_keys():
    """REST Endpoint to trigger independent diagnostic scan for all API keys."""
    results = run_all_keys_health_check()
    return jsonify({
        'status': 'success',
        'count': len(results),
        'results': results
    })

@socketio.on('connect')
def handle_connect():
    """Triggered when a WebSocket client connects."""
    emit('status_update', {
        'status': 'idle',
        'message': 'Connected to server. Monitoring clipboard for screenshots...',
        'timestamp': time.strftime("%H:%M:%S")
    })

@socketio.on('run_key_health_check')
def handle_run_key_health_check():
    """WebSocket event handler to run key diagnostic scan asynchronously."""
    emit('key_health_progress', {'status': 'scanning', 'message': 'Running diagnostic scan across all configured API keys...'})
    results = run_all_keys_health_check()
    emit('key_health_results', {
        'status': 'success',
        'count': len(results),
        'results': results,
        'timestamp': time.strftime("%H:%M:%S")
    })

def print_startup_health_check():
    """Prints server startup health check to terminal."""
    valid_gemini_keys = [k for k, v in API_KEYS_MAP.items() if v and v not in ("YOUR_GEMINI_API_KEY", "")]
    has_openai = bool(OPENAI_API_KEY and OPENAI_API_KEY not in ("YOUR_OPENAI_API_KEY", ""))
    
    print("\n" + "=" * 55)
    print("🚀 TEXTLINE MULTI-PROVIDER AI SERVER INITIALIZED")
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
