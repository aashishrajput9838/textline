"""
Flask-SocketIO Event Handlers for Textline Dashboard.
"""

import time
from flask_socketio import SocketIO, emit
from ai.health_registry import KEY_MODEL_HEALTH_REGISTRY
from server.flask_app import run_all_keys_health_check

def register_socket_events(socketio: SocketIO):
    """Registers Socket.IO event handlers for dashboard communication."""

    @socketio.on('connect')
    def handle_connect():
        emit('status_update', {
            'status': 'idle',
            'message': 'Connected to server. Monitoring clipboard for screenshots...',
            'timestamp': time.strftime("%H:%M:%S")
        })
        emit('health_matrix_update', {
            'health_matrix': KEY_MODEL_HEALTH_REGISTRY
        })

    @socketio.on('run_key_health_check')
    def handle_run_key_health_check():
        emit('key_health_progress', {'status': 'scanning', 'message': 'Running diagnostic scan across all configured API keys & models matrix...'})
        results = run_all_keys_health_check(socketio=socketio)
        emit('key_health_results', {
            'status': 'success',
            'count': len(results),
            'results': results,
            'health_matrix': KEY_MODEL_HEALTH_REGISTRY
        })
