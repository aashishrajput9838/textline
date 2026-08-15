"""
Model-specific API Key Health Registry for Textline.
Tracks health state per (key_id, model_name) pair and broadcasts live matrix updates over Socket.IO.
"""

import time

# Model-Specific Health Registry: { key_id: { model_name: { "status": str, "http_code": int, "latency_ms": int, "details": str, "updated_at": float } } }
KEY_MODEL_HEALTH_REGISTRY = {}

_socketio_instance = None

def set_socketio(sio):
    """Sets socketio instance for health matrix updates without circular imports."""
    global _socketio_instance
    _socketio_instance = sio

def classify_error_code_and_status(err):
    """Accurately classifies HTTP status code and status string for Gemini errors."""
    err_str = str(err)
    err_str_upper = err_str.upper()
    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "QUOTA" in err_str_upper:
        return 429, "QUOTA_EXHAUSTED"
    if "404" in err_str or "NOT_FOUND" in err_str or "no longer available" in err_str.lower():
        return 404, "MODEL_UNAVAILABLE"
    if "403" in err_str or "PERMISSION_DENIED" in err_str or "UNAUTHORIZED" in err_str_upper:
        return 403, "UNAUTHORIZED"
    if "400" in err_str or "INVALID_ARGUMENT" in err_str:
        return 400, "INVALID_ARGUMENT"
    if "503" in err_str or "UNAVAILABLE" in err_str or "HIGH DEMAND" in err_str_upper:
        return 503, "SERVICE_UNAVAILABLE"
    if "500" in err_str or "INTERNAL" in err_str_upper:
        return 500, "INTERNAL_SERVER_ERROR"
    return 0, "ERROR"

def update_key_model_health(key_id, model, status, code=200, latency_ms=0, details="", socketio=None):
    """Updates global model-specific health state and broadcasts updates to UI clients via SocketIO."""
    if not key_id or not model:
        return
    if key_id not in KEY_MODEL_HEALTH_REGISTRY:
        KEY_MODEL_HEALTH_REGISTRY[key_id] = {}
    
    KEY_MODEL_HEALTH_REGISTRY[key_id][model] = {
        "key_id": key_id,
        "model": model,
        "status": status,
        "http_code": code,
        "latency_ms": latency_ms,
        "details": details or status,
        "updated_at": time.time()
    }
    
    sio = socketio or _socketio_instance
    try:
        if sio:
            sio.emit('health_matrix_update', {
                'key_id': key_id,
                'model': model,
                'status': status,
                'http_code': code,
                'latency_ms': latency_ms,
                'details': details or status,
                'health_matrix': KEY_MODEL_HEALTH_REGISTRY
            })
    except Exception:
        pass

def get_key_model_status(key_id, model):
    """Retrieves current health status for a specific (key_id, model) pair."""
    if key_id in KEY_MODEL_HEALTH_REGISTRY and model in KEY_MODEL_HEALTH_REGISTRY[key_id]:
        return KEY_MODEL_HEALTH_REGISTRY[key_id][model].get("status", "UNKNOWN")
    return "UNKNOWN"

def is_key_model_known_unavailable(key_id, model):
    """Determines if a (key_id, model) combination is known to be permanently or quota unavailable."""
    st = get_key_model_status(key_id, model)
    return st in ("QUOTA_EXHAUSTED", "MODEL_UNAVAILABLE", "UNAUTHORIZED", "INVALID_ARGUMENT")
