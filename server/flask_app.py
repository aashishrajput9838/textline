"""
Flask Application Factory and HTTP REST API Routes for Textline.
"""

import os
import sys
import time
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from google import genai

from config.constants import SUPPORTED_HEALTH_MODELS
from ai.key_manager import discover_all_gemini_keys
from ai.health_registry import (
    KEY_MODEL_HEALTH_REGISTRY,
    update_key_model_health,
    classify_error_code_and_status
)

def get_template_folder() -> str:
    """Resolves template directory for PyInstaller onefile or standard source mode."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'templates')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')

def get_static_folder() -> str:
    """Resolves static asset directory for PyInstaller onefile or standard source mode."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'static')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')

def create_app() -> tuple[Flask, SocketIO]:
    """Factory creating Flask app and Flask-SocketIO instances."""
    template_dir = get_template_folder()
    static_dir = get_static_folder()
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config['SECRET_KEY'] = 'clipboard_gemini_secret_key'
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

    
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", ping_timeout=60, ping_interval=25)
    
    _register_routes(app, socketio)
    return app, socketio

def test_key_model_diagnostic(key_id, api_key, model_name, socketio=None):
    """Tests a single (key_id, model_name) pair independently and records status in health registry."""
    check_id = f"hc_{int(time.time() * 1000)}_{key_id}_{model_name}"
    if not api_key or not api_key.strip() or api_key == "YOUR_GEMINI_API_KEY":
        res = {
            "check_id": check_id,
            "key_id": key_id,
            "model": model_name,
            "status": "INVALID_ARGUMENT",
            "latency_ms": 0,
            "http_code": 400,
            "details": "Not Configured in .env"
        }
        update_key_model_health(key_id, model_name, "INVALID_ARGUMENT", 400, 0, "Not Configured in .env", socketio=socketio)
        return res

    start_time = time.time()
    try:
        # Dynamically resolve genai.Client to respect test patches on app.genai.Client
        app_mod = sys.modules.get("app")
        genai_mod = getattr(app_mod, "genai", genai) if app_mod else genai
        client = genai_mod.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model=model_name,
            contents="Hi"
        )
        latency = int((time.time() - start_time) * 1000)
        if response and response.text:
            res = {
                "check_id": check_id,
                "key_id": key_id,
                "model": model_name,
                "status": "WORKING",
                "latency_ms": latency,
                "http_code": 200,
                "details": "PASS"
            }
            update_key_model_health(key_id, model_name, "WORKING", 200, latency, "PASS", socketio=socketio)
            return res
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        code, status = classify_error_code_and_status(e)
        err_str = str(e)
        short_err = err_str.split("\n")[0] if "\n" in err_str else err_str
        res = {
            "check_id": check_id,
            "key_id": key_id,
            "model": model_name,
            "status": status,
            "latency_ms": latency,
            "http_code": code,
            "details": f"{code} {status}" if short_err.startswith(str(code)) else f"{code} {status}: {short_err}"
        }
        update_key_model_health(key_id, model_name, status, code, latency, short_err, socketio=socketio)
        return res

    res = {
        "check_id": check_id,
        "key_id": key_id,
        "model": model_name,
        "status": "ERROR",
        "latency_ms": 0,
        "http_code": 500,
        "details": "Unknown Error"
    }
    update_key_model_health(key_id, model_name, "ERROR", 500, 0, "Unknown Error", socketio=socketio)
    return res

def run_all_keys_health_check(socketio=None):
    """Executes full diagnostic matrix scan across all configured API keys and models."""
    app_mod = sys.modules.get("app")
    disc_fn = getattr(app_mod, "discover_all_gemini_keys", discover_all_gemini_keys) if app_mod else discover_all_gemini_keys
    health_models = getattr(app_mod, "SUPPORTED_HEALTH_MODELS", SUPPORTED_HEALTH_MODELS) if app_mod else SUPPORTED_HEALTH_MODELS
    
    keys_map = disc_fn()
    results = []
    for key_id, api_key in keys_map.items():
        for model_name in health_models:
            res = test_key_model_diagnostic(key_id, api_key, model_name, socketio=socketio)
            results.append(res)
    return results

def _register_routes(app: Flask, socketio: SocketIO):
    """Registers HTTP REST API routes on Flask app instance."""
    
    @app.route('/')
    def index():
        return render_template('index.html', active_page='monitor')

    @app.route('/monitor')
    def monitor():
        return render_template('index.html', active_page='monitor')

    @app.route('/health')
    def health():
        return render_template('health.html', active_page='health')

    @app.route('/usage')
    def usage():
        return render_template('usage.html', active_page='usage')

    @app.route('/history')
    def history():
        return render_template('history.html', active_page='history')

    @app.route('/api/test-keys')
    def api_test_keys():
        results = run_all_keys_health_check(socketio=socketio)
        return jsonify({
            'status': 'success',
            'count': len(results),
            'results': results,
            'health_matrix': KEY_MODEL_HEALTH_REGISTRY
        })

    @app.route('/api/health-state')
    def api_health_state():
        return jsonify({
            'status': 'success',
            'health_matrix': KEY_MODEL_HEALTH_REGISTRY
        })
