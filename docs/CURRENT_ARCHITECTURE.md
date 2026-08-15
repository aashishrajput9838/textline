# TEXTLINE — CURRENT ARCHITECTURE AUDIT

> **As of: 2026-08-15 — `app.py` (831 lines) + `templates/index.html` (1564 lines)**
> No source files were modified during this audit.

---

## 1. Directory Tree

```
c:\github\textline\
├── app.py                     (831 lines, 39 922 bytes)  — entire backend
├── templates/
│   └── index.html             (1564 lines, 60 072 bytes) — entire frontend
├── test_fallback_system.py    (1228 lines, 56 783 bytes) — 42 unit tests
├── requirements.txt           (7 lines)
├── app.spec                   (40 lines)                 — PyInstaller config
├── .env                       (5 lines)                  — API keys
├── docs/                      (this directory)
├── dist/app.exe               — compiled binary (--noconsole --onefile)
└── textline_logo.ico / .jpg
```

---

## 2. All Global State Variables

| Variable | Type | Location | Purpose |
|---|---|---|---|
| `API_KEYS_MAP` | `dict[str, str]` | L97 | Maps canonical key ID → raw API key value. Loaded once at import. |
| `OPENAI_API_KEY` | `str` | L100 | Raw OpenAI key from env. May be placeholder string. |
| `DEFAULT_GEMINI_MODELS` | `list[str]` | L103 | `["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]` |
| `PROJECT_METADATA_MAP` | `dict` | L177 | Hardcoded project metadata per key ID. |
| `SUPPORTED_HEALTH_MODELS` | `list[str]` | L189 | Models for health-check matrix (same 3). |
| `KEY_MODEL_HEALTH_REGISTRY` | `dict` | L192 | `{key_id: {model: {status, http_code, latency_ms, ...}}}`. Mutated from multiple threads. **No lock.** |
| `app` | `Flask` | L70 | Flask application instance. |
| `socketio` | `SocketIO` | L74 | Flask-SocketIO, `async_mode="threading"`. |

---

## 3. All Functions and Their Callers

### A. Bootstrap
- `load_api_keys_map()` — L77–95. Caller: module init (L97). Reads env vars, builds key dict.
- `print_startup_health_check()` — L809–819. Caller: `__main__`. Prints startup banner.

### B. Error Classification
- `classify_error_code_and_status(err)` — L105–121. Callers: `generate_content_with_fallback`, `test_key_model_diagnostic`. Pattern-matches exception string → (http_code, status_str).

### C. Gemini Client Helpers
- `get_available_gemini_models(client)` — L123–137. Caller: `generate_content_with_fallback`. Calls `client.models.list()` (BLOCKING, no timeout), returns filtered model list or DEFAULT fallback.
- `generate_content_openai_fallback(prompt, b64_url)` — L139–174. Caller: `generate_content_with_fallback`. Synchronous OpenAI call. No timeout. Returns text or None.

### D. Health Registry
- `update_key_model_health(key_id, model, status, code, latency, details)` — L194–223. Callers: `generate_content_with_fallback`, `test_key_model_diagnostic`. Mutates `KEY_MODEL_HEALTH_REGISTRY`, emits `health_matrix_update`. Exception swallowed silently.
- `get_key_model_status(key_id, model)` — L276–280. Caller: `is_key_model_known_unavailable`.
- `is_key_model_known_unavailable(key_id, model)` — L282–285. Caller: `generate_content_with_fallback`.

### E. Pipeline Logging
- `generate_pipeline_id()` — L225–229. Caller: `monitor_clipboard`. Returns `YYYYMMDD-HHMMSS-XXXX`.
- `emit_pipeline_log(pipeline_id, stage, message, ...)` — L231–274. Callers: `monitor_clipboard`, `generate_content_with_fallback`. Prints to stdout AND calls `socketio.emit('pipeline_log', ...)`.

### F. Core AI Generation
- `generate_content_with_fallback(contents, base64_image_url, pipeline_id)` — L287–520. Caller: `monitor_clipboard`. Full key×model rotation. Returns `(text, meta)` or raises `NoAvailableModelError`.
- `NoAvailableModelError` — L522–526. Raised by `generate_content_with_fallback`, caught by inner except in `monitor_clipboard`.

### G. Formatting
- `format_clipboard_output(raw_answer)` — L528–531. Caller: `monitor_clipboard`. Strip whitespace, append 50 blank lines + `.`.

### H. Clipboard Monitor
- `monitor_clipboard()` — L533–649. Caller: `__main__` via `threading.Thread(daemon=True)`. Infinite loop, polls clipboard every 1s, drives full pipeline.

### I. Health Check Infrastructure
- `discover_all_gemini_keys()` — L651–682. Caller: `run_all_keys_health_check`. Deduplicates keys.
- `test_key_model_diagnostic(key_id, api_key, model_name)` — L684–747. Caller: `run_all_keys_health_check`. Single live "Hi" call to test health. No timeout.
- `run_all_keys_health_check()` — L749–759. Callers: `api_test_keys`, `handle_run_key_health_check`. Full matrix scan. Synchronous, blocks caller thread.

### J. Flask Routes
- `GET /` → `index()` — L761–764. Renders `index.html`.
- `GET /api/test-keys` → `api_test_keys()` — L766–775.
- `GET /api/health-state` → `api_health_state()` — L777–783.

### K. Socket.IO Handlers
- `connect` → `handle_connect()` — L785–795. Emits `status_update(idle)` + `health_matrix_update`.
- `run_key_health_check` → `handle_run_key_health_check()` — L797–807. **Blocks SocketIO event thread** during full health scan.

---

## 4. All Socket.IO Events

### Backend → Frontend

| Event | Emitted From | Key Payload |
|---|---|---|
| `status_update` | `handle_connect`, `monitor_clipboard` (4 sites) | `status`, `message`, `timestamp`, `pipeline_id?`, `answer?`, `metadata?` |
| `health_matrix_update` | `handle_connect`, `update_key_model_health` | `key_id`, `model`, `status`, `health_matrix` |
| `pipeline_log` | `emit_pipeline_log` (~25 call sites) | `pipeline_id`, `stage`, `message`, `level`, `timestamp`, `elapsed_ms` |
| `image_preview` | `monitor_clipboard` L580 | `image_url`, `pipeline_id` |
| `key_health_progress` | `handle_run_key_health_check` | `status`, `message` |
| `key_health_results` | `handle_run_key_health_check` | `results`, `health_matrix` |

### Frontend → Backend

| Event | Trigger | Handler |
|---|---|---|
| `run_key_health_check` | Button click | `handle_run_key_health_check` |

---

## 5. Screenshot Processing Lifecycle (Exact)

```
THREAD: clipboard_thread (daemon=True)

while True:
  pipeline_id = None
  p_start = time.time()
  
  try:
    clipboard_content = ImageGrab.grabclipboard()     [BLOCKING, NO TIMEOUT]
    
    if isinstance(clipboard_content, Image.Image):
      [convert RGBA/P → RGB]
      [save to BytesIO as PNG]
      current_hash = sha256(img_bytes)
      
      if current_hash != last_image_hash:             [NEW SCREENSHOT]
        last_image_hash = current_hash
        pipeline_id = generate_pipeline_id()
        
        emit_pipeline_log(SCREENSHOT_DETECTED)
        emit_pipeline_log(CLIPBOARD_READ_SUCCESS)
        emit_pipeline_log(IMAGE_VALIDATION_SUCCESS)
        emit_pipeline_log(IMAGE_PREPARATION_START)
        [base64.b64encode(img_bytes)]
        emit_pipeline_log(IMAGE_PREPARATION_SUCCESS)
        
        socketio.emit('status_update', processing)   [status_update WORKS]
        socketio.emit('image_preview', ...)
        
        processing_active = True
        emit_pipeline_log(GENERATION_START)
        
        try:
          raw_answer, meta = generate_content_with_fallback(...)  [BLOCKING, NO TIMEOUT]
          emit_pipeline_log(GENERATION_SUCCESS)
          final_text = format_clipboard_output(raw_answer)
          pyperclip.copy(final_text)                 [BLOCKING, NO TIMEOUT]
          socketio.emit('status_update', success)
          emit_pipeline_log(PIPELINE_COMPLETE)
          processing_active = False
          
        except Exception as api_err:
          [emit status_update error, PIPELINE_ERROR, PIPELINE_COMPLETE]
          processing_active = False
          
  except Exception as e:
    if processing_active:                            [BUG: set only at L587]
      [emit status_update error]
    else:
      print(exception)                               [UI left in PROCESSING if exception before processing_active=True]
      
  time.sleep(1)
```

---

## 6. Blocking Operations

| Operation | Caller | Thread | Timeout | Risk |
|---|---|---|---|---|
| `ImageGrab.grabclipboard()` | `monitor_clipboard` | clipboard_thread | ❌ None | Can block if clipboard locked by another process |
| `client.models.list()` | `get_available_gemini_models` | clipboard_thread | ❌ None | **HTTP call on every screenshot. Can block 1–30s.** |
| `genai.generate_content(...)` | `generate_content_with_fallback` | clipboard_thread | ❌ None | Up to 18 retries × 60s = 18 minutes possible |
| `time.sleep(wait_sec)` | `generate_content_with_fallback` L443 | clipboard_thread | 1.5–3s | 503 retry backoff — bounded |
| `openai.chat.completions.create(...)` | `generate_content_openai_fallback` | clipboard_thread | ❌ None | Can block indefinitely |
| `pyperclip.copy(...)` | `monitor_clipboard` | clipboard_thread | ❌ None | Clipboard write may block |
| `genai.generate_content("Hi")` | `test_key_model_diagnostic` | SocketIO thread | ❌ None | Can block SocketIO event thread |
| `time.sleep(1)` | `monitor_clipboard` | clipboard_thread | 1s | Fixed polling interval |

**MOST CRITICAL**: `get_available_gemini_models(client)` is called for EACH KEY on EACH screenshot. This is 2 blocking network calls before generation even starts, with zero timeout.

---

## 7. All Exception Swallowing Sites

| Location | Exception Caught | Action |
|---|---|---|
| `update_key_model_health` L222 | `Exception` | `pass` — completely silent |
| `get_available_gemini_models` L135 | `Exception` | `pass` — returns DEFAULT_GEMINI_MODELS |
| `safe_print` L36 | `Exception` | `pass` — print failure dropped |
| `sys.stdout.reconfigure` L17 | `Exception` | `pass` |
| `sys.stderr.reconfigure` L21 | `Exception` | `pass` |
| dotenv import L59, L66 | `ImportError` | `pass` |

---

## 8. State Transition Gaps (PROCESSING Never Resolved)

The UI gets stuck in PROCESSING if ANY exception fires:
1. Before `processing_active = True` (L587) — the outer except (L629) does NOT emit error
2. During clipboard read BEFORE `current_hash != last_image_hash` test
3. During base64 encoding (between PREPARATION_START emit and PREPARATION_SUCCESS emit)

No `finally:` block guarantees the status returns from PROCESSING to a terminal state.

---

## 9. Synchronization Primitives

**NONE.** There are zero `threading.Lock`, `threading.Event`, `threading.Queue`, or any other synchronization objects in the entire codebase. `KEY_MODEL_HEALTH_REGISTRY` is written from both the clipboard thread and the SocketIO handler thread with no protection.

---

## 10. The EXE vs Python Server Conflict

**`app.spec` has `console=False`** — the compiled EXE runs with NO console output. All `[PIPELINE EMIT]` debug prints are invisible when running from `dist/app.exe`.

**The template baked into `dist/app.exe`** was compiled at build time. The most recent `app.exe` was built with `python -m PyInstaller --noconsole --onefile --icon=textline_logo.ico --add-data "templates;templates" app.py` BEFORE our pipeline_log listener additions. This means `dist/app.exe` serves the OLD `index.html` without the `socket.on('pipeline_log')` listener.

**If the user launches `dist/app.exe`**, they get the old template. The pipeline_log events are emitted by the correct app.py code but the frontend has no listener registered. This is the primary reason the pipeline log panel stays empty.

**Confirmed by**: Two browser tabs shown in metadata both pointing to `127.0.0.1:5000`, and the user reporting that running `cls` and a new PyInstaller build both happened in the same terminal session. The `dist/app.exe` served the page the user was viewing.
