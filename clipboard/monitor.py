"""
Clipboard Monitor thread manager for Textline.
Polls Windows clipboard, performs SHA-256 deduplication, and delegates to ScreenshotPipeline.
"""

import time
import threading
from PIL import Image

from clipboard.reader import read_clipboard_image
from clipboard.hasher import compute_image_hash
from image.converter import convert_to_rgb, image_to_png_bytes
from pipeline.pipeline import ScreenshotPipeline
from utils.timing import generate_pipeline_id

class ClipboardMonitor:
    """
    Thin background thread monitor that polls the Windows clipboard for new screenshots,
    fingerprints image bytes via SHA-256 to avoid duplicate processing, and delegates execution
    to ScreenshotPipeline.
    """

    def __init__(self, socketio=None, poll_interval: float = 1.0):
        self.socketio = socketio
        self.poll_interval = poll_interval
        self.last_image_hash = None
        self.pipeline = ScreenshotPipeline(socketio)
        self._running = False
        self._thread = None

    def start(self, daemon: bool = True):
        """Starts background monitoring thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=daemon)
        self._thread.start()
        print("[*] Clipboard monitoring thread started.")

    def stop(self):
        """Stops background monitoring thread."""
        self._running = False

    def _run_loop(self):
        """Internal polling loop."""
        while self._running:
            try:
                content = read_clipboard_image()
                if isinstance(content, Image.Image):
                    rgb_img = convert_to_rgb(content)
                    img_bytes, _ = image_to_png_bytes(rgb_img)
                    current_hash = compute_image_hash(img_bytes)

                    if current_hash != self.last_image_hash:
                        self.last_image_hash = current_hash
                        pipeline_id = generate_pipeline_id()
                        try:
                            self.pipeline.process(content, pipeline_id=pipeline_id)
                        except Exception as pipe_err:
                            # Error already logged and terminal events emitted inside ScreenshotPipeline.process
                            pass
            except Exception as e:
                print(f"[!] Clipboard monitor exception: {e}")

            time.sleep(self.poll_interval)

def monitor_clipboard(socketio=None):
    """Legacy entry point wrapper for starting clipboard monitoring."""
    monitor = ClipboardMonitor(socketio=socketio)
    monitor.start(daemon=True)
    return monitor
