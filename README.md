# Textline ⚡

An automated local productivity dashboard that monitors your Windows clipboard for screenshots, sends them to Gemini 2.5 Flash AI, auto-copies the generated code/answer directly back to your clipboard, and visualizes real-time processing via WebSockets.

---

## ✨ Features

- **⚡ Real-time Clipboard Listener**: Automatically detects new screenshots from `Win + Shift + S` or `PrtScn`.
- **🤖 Powered by Gemini 2.5 Flash**: Fast code extraction and question solving using Google's modern `google-genai` SDK.
- **📋 Auto-Copy to Clipboard**: Instant zero-click output copied right back to your system clipboard.
- **📡 WebSockets Real-Time Dashboard**: Beautiful dark-mode UI with glassmorphism aesthetics showing live connection, screenshot preview, status updates, and session history.

---

## 🛠️ Tech Stack

- **Backend**: Python, Flask, Flask-SocketIO
- **AI Engine**: `google-genai` SDK (Gemini 2.5 Flash)
- **Image & System Utilities**: Pillow (PIL), `pyperclip`
- **Frontend**: HTML5, Vanilla CSS (Glassmorphism & CSS Variables), JavaScript, Socket.IO Client (CDN)

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/aashishrajput9838/textline.git
cd textline
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up API Key
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Run Application
```bash
python app.py
```

Open your browser and navigate to `http://127.0.0.1:5000`.

---

## 💻 Usage

1. Start the Flask application.
2. Open `http://127.0.0.1:5000` in your web browser.
3. Take any screenshot using `Win + Shift + S`.
4. The dashboard will automatically detect the screenshot, send it to Gemini AI, display the result, and copy the answer straight to your clipboard!

---

## 📄 License
MIT License
