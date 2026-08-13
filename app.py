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
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# PyInstaller creates a temp folder and stores path in _MEIPASS
if getattr(sys, 'frozen', False):
    template_dir = os.path.join(sys._MEIPASS, 'templates')
else:
    template_dir = 'templates'

# Initialize Flask App & SocketIO
app = Flask(__name__, template_folder=template_dir)
app.config['SECRET_KEY'] = 'clipboard_gemini_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure Gemini API Client (using google-genai SDK)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

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

                    # 3. Send image to Gemini API with strict system prompt
                    prompt = "give me complete  code in given language , \nmake sure -\n1. my code should be very fast in terms of speed .\n2. remoove any spaces from the starting of the each line in code .\n\nmost important -- i dont need any explanation or any othr content even a single words that is unrelasvebt .  the output shopud be only the code i want "
                    
                    try:
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[prompt, clipboard_content]
                        )
                        answer = response.text.strip() if response and response.text else "No text returned from model."
                        
                        # 4. Auto-copy answer to Windows clipboard
                        pyperclip.copy(answer)

                        # 5. Emit final answer and Done status to frontend
                        socketio.emit('status_update', {
                            'status': 'success',
                            'message': 'Done! Answer copied to clipboard.',
                            'answer': answer,
                            'timestamp': time.strftime("%H:%M:%S")
                        })
                    except Exception as api_err:
                        error_msg = f"Gemini API Error: {str(api_err)}"
                        print(f"[!] {error_msg}")
                        socketio.emit('status_update', {
                            'status': 'error',
                            'message': error_msg,
                            'timestamp': time.strftime("%H:%M:%S")
                        })
        except Exception as e:
            print(f"[!] Clipboard monitor exception: {e}")

        time.sleep(1)

@app.route('/')
def index():
    """Render the main single-page dashboard."""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Triggered when a WebSocket client connects."""
    emit('status_update', {
        'status': 'idle',
        'message': 'Connected to server. Monitoring clipboard for screenshots...',
        'timestamp': time.strftime("%H:%M:%S")
    })

if __name__ == '__main__':
    # Start clipboard listener in a daemon thread so it runs in the background
    clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
    clipboard_thread.start()

    # Launch Flask-SocketIO Web Server
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)
