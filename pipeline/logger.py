"""
Structured Real-time Pipeline Execution Logger for Textline.
Logs execution stages to console and broadcasts Socket.IO pipeline_log events.
"""

import time
from utils.logging import safe_print

_socketio_instance = None

def set_socketio(sio):
    """Registers global Socket.IO instance for real-time log broadcasting."""
    global _socketio_instance
    _socketio_instance = sio

def emit_pipeline_log(pipeline_id, stage, message, level="INFO", key_id="", model="", http_code=0, error_code="", elapsed_ms=0, socketio=None):
    """
    Emits a real-time structured pipeline execution log event over Socket.IO and logs to console.
    """
    if hasattr(stage, 'value'):
        stage = stage.value

    ts = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"

    data = {
        "pipeline_id": pipeline_id,
        "timestamp": ts,
        "stage": stage,
        "message": message,
        "level": level,
        "elapsed_ms": elapsed_ms,
        "key_id": key_id,
        "model": model,
        "http_code": http_code,
        "error_code": error_code
    }
    
    symbol = "✓" if level in ("SUCCESS", "INFO") else ("→" if level == "RUNNING" else ("⚠" if level == "WARNING" else "✗"))
    log_line = f"[{ts}] [{pipeline_id}] {symbol} [{stage}] {message}"
    safe_print(f"[PIPELINE DEBUG] id={pipeline_id} stage={stage} message={message}", flush=True)
    safe_print(f"[PIPELINE EMIT] socket_id=ALL pipeline_id={pipeline_id} stage={stage} message={message}", flush=True)
    safe_print(log_line, flush=True)
    
    sio = socketio or _socketio_instance
    if not sio:
        import sys
        app_mod = sys.modules.get("app")
        sio = getattr(app_mod, "socketio", None)

    try:
        if sio:
            sio.emit('pipeline_log', {
                'pipeline_id': pipeline_id,
                'timestamp': ts,
                'stage': stage,
                'message': message,
                'level': level,
                'elapsed_ms': elapsed_ms,
                'key_id': key_id,
                'model': model,
                'http_code': http_code,
                'error_code': error_code
            })
            safe_print("[PIPELINE EMIT] socketio.emit('pipeline_log') called OK", flush=True)
        else:
            safe_print("[PIPELINE EMIT] ERROR: socketio is None/falsy! Cannot emit.", flush=True)
    except Exception as e:
        safe_print(f"[!] Failed to emit pipeline_log event: {e}", flush=True)
    return data
