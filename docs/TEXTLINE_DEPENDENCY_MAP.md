# TEXTLINE — DEPENDENCY MAP

> Investigation only. No source files modified.

---

## Full Pipeline Dependency Chain

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TRIGGER: Win+Shift+S (Windows screenshot to clipboard)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                             [Windows OS]
                                    │ clipboard updated
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ THREAD: clipboard_thread (daemon, started at __main__)                       │
│ LOOP: while True: ... time.sleep(1)                                          │
└─────────────────────────────────────────────────────────────────────────────┘

╔══ STAGE 1: CLIPBOARD DETECTION ════════════════════════════════════════════╗
║ SOURCE:  monitor_clipboard() — L543                                         ║
║ CALL:    clipboard_content = ImageGrab.grabclipboard()                      ║
║ DATA:    PIL.Image | list | None                                            ║
║ BLOCK:   YES — no timeout — Windows clipboard API                           ║
║ EXCEPT:  outer try/except L614 — if exception here:                         ║
║          processing_active not yet set → print only → UI STUCK              ║
╚═════════════════════════════════════════════════════════════════════════════╝
                                    │ PIL.Image object
                                    ▼
╔══ STAGE 2: IMAGE ACQUISITION ══════════════════════════════════════════════╗
║ SOURCE:  monitor_clipboard() — L546–552                                     ║
║ OPS:     .convert("RGB") if needed                                          ║
║          .save(BytesIO, format='PNG')                                       ║
║          hashlib.sha256(img_bytes).hexdigest()                              ║
║ DATA:    img_bytes (bytes), current_hash (str)                              ║
║ BLOCK:   In-memory only. Fast (<10ms).                                      ║
║ EXCEPT:  outer try/except — same STUCK risk as stage 1                      ║
╚═════════════════════════════════════════════════════════════════════════════╝
                                    │ current_hash
                                    ▼
                     ┌──────────────────────────────┐
                     │ current_hash == last_image_hash │
                     │          ? SKIP               │
                     └──────────────────────────────┘
                                    │ hash is NEW
                                    ▼
╔══ STAGE 3: PIPELINE INIT ══════════════════════════════════════════════════╗
║ SOURCE:  monitor_clipboard() — L555–564                                     ║
║ OPS:     last_image_hash = current_hash                                     ║
║          pipeline_id = generate_pipeline_id()                               ║
║          emit_pipeline_log(SCREENSHOT_DETECTED)                             ║
║          emit_pipeline_log(CLIPBOARD_READ_SUCCESS)                          ║
║          emit_pipeline_log(IMAGE_VALIDATION_SUCCESS)                        ║
║ DATA:    pipeline_id (str), width, height                                   ║
║ EXCEPT:  outer try/except — STUCK risk                                      ║
╚═════════════════════════════════════════════════════════════════════════════╝
                                    │
                                    ▼
╔══ STAGE 4: IMAGE PREPARATION ══════════════════════════════════════════════╗
║ SOURCE:  monitor_clipboard() — L566–571                                     ║
║ OPS:     base64.b64encode(img_bytes).decode('utf-8')                        ║
║          image_data_url = "data:image/png;base64,..."                       ║
║          emit_pipeline_log(IMAGE_PREPARATION_START)                         ║
║          emit_pipeline_log(IMAGE_PREPARATION_SUCCESS)                       ║
║ DATA:    image_data_url (str, ~4× image size)                               ║
║ BLOCK:   In-memory. Proportional to image size.                             ║
║ EXCEPT:  outer try/except — STUCK risk                                      ║
╚═════════════════════════════════════════════════════════════════════════════╝
                                    │
                                    ▼
                 socketio.emit('status_update', processing)    ← UI SHOWS PROCESSING
                 socketio.emit('image_preview', image_data_url)
                                    │
                 processing_active = True                      ← GUARD SET
                                    │
                                    ▼
╔══ STAGE 5: AI GENERATION (calls generate_content_with_fallback) ════════════╗
║ SOURCE:  monitor_clipboard() — L590                                          ║
║ CALL:    generate_content_with_fallback(                                     ║
║              contents=[prompt, clipboard_content],                           ║
║              base64_image_url=image_data_url,                                ║
║              pipeline_id=pipeline_id                                         ║
║          )                                                                   ║
║ RETURNS: (text: str, meta: dict)                                             ║
║ RAISES:  NoAvailableModelError                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

  ┌── generate_content_with_fallback internals ─────────────────────────────┐
  │                                                                          │
  │ emit_pipeline_log(KEY_SELECTION_START)                                   │
  │                                                                          │
  │ for key_id, api_key in valid_keys.items():                               │
  │   emit_pipeline_log(KEY_SELECTED)                                        │
  │                                                                          │
  │   client = genai.Client(api_key=api_key)         [may raise]             │
  │                                                                          │
  │   models = get_available_gemini_models(client)   [BLOCKING HTTP CALL]   │
  │   ┌── get_available_gemini_models ─────────────────────────────────┐    │
  │   │ client.models.list()   [BLOCKING, NO TIMEOUT, EVERY SCREENSHOT] │    │
  │   │ on exception: pass → return DEFAULT_GEMINI_MODELS              │    │
  │   └────────────────────────────────────────────────────────────────┘    │
  │                                                                          │
  │   for model_name in models:                                              │
  │     if is_key_model_known_unavailable(key_id, model):                    │
  │       emit_pipeline_log(MODEL_SKIPPED)                                   │
  │       continue                                                           │
  │                                                                          │
  │     for retry_idx in range(3):   [0, 1, 2]                              │
  │       emit_pipeline_log(API_REQUEST_START)                               │
  │       response = client.models.generate_content(...)  [BLOCKING]        │
  │                                                                          │
  │       ── on success (200):                                               │
  │         update_key_model_health(WORKING)                                 │
  │         return response.text, meta                                       │
  │                                                                          │
  │       ── on exception:                                                   │
  │         classify_error_code_and_status(e) → (code, status)              │
  │         update_key_model_health(status)                                  │
  │         emit_pipeline_log(API_RESPONSE, error)                           │
  │         if 503: time.sleep(1.5 or 3.0)  [bounded]                       │
  │         if 400/403: mark entire key bad, break to next key               │
  │         if 404/429: break to next model                                  │
  │                                                                          │
  │ ALL KEYS EXHAUSTED:                                                      │
  │   emit_pipeline_log(ALL_ATTEMPTS_EXHAUSTED)                              │
  │                                                                          │
  │   if base64_image_url:                                                   │
  │     emit_pipeline_log(OPENAI_FALLBACK_START)                             │
  │     openai_result = generate_content_openai_fallback(...)  [BLOCKING]   │
  │     if openai_result: return openai_result, meta                         │
  │                                                                          │
  │   raise NoAvailableModelError(...)                                       │
  └──────────────────────────────────────────────────────────────────────────┘

                                    │ (text, meta) OR exception
                                    ▼
╔══ STAGE 6: ON SUCCESS ══════════════════════════════════════════════════════╗
║ SOURCE:  monitor_clipboard() — L591–611                                      ║
║ OPS:     emit_pipeline_log(GENERATION_SUCCESS)                               ║
║          final_text = format_clipboard_output(raw_answer)                   ║
║          emit_pipeline_log(CLIPBOARD_COPY_START)                            ║
║          pyperclip.copy(final_text)              [BLOCKING, NO TIMEOUT]     ║
║          emit_pipeline_log(CLIPBOARD_COPY_SUCCESS)                          ║
║          socketio.emit('status_update', success)                            ║
║          emit_pipeline_log(PIPELINE_COMPLETE)                               ║
║          processing_active = False                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══ STAGE 6b: ON GENERATION ERROR ════════════════════════════════════════════╗
║ SOURCE:  monitor_clipboard() — L612–628                                      ║
║ OPS:     emit_pipeline_log(GENERATION_ERROR)                                ║
║          socketio.emit('status_update', error)                              ║
║          emit_pipeline_log(PIPELINE_ERROR)                                  ║
║          emit_pipeline_log(PIPELINE_COMPLETE)                               ║
║          processing_active = False                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══ STAGE 6c: UNHANDLED EXCEPTION (processing_active not set) ════════════════╗
║ SOURCE:  monitor_clipboard() — L629–647                                      ║
║ GUARD:   'processing_active' in locals() AND processing_active              ║
║ BUG:     If exception occurs BEFORE processing_active = True (L587):        ║
║          → outer except fires                                               ║
║          → 'processing_active' NOT in locals()                              ║
║          → only print(exception)                                            ║
║          → NO socketio.emit('status_update', error)                         ║
║          → UI STUCK AT PROCESSING FOREVER                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

---

## Function-to-Function Dependency Table

| Caller | → Called Function | Data Passed | Exception Behavior |
|---|---|---|---|
| `monitor_clipboard` | `ImageGrab.grabclipboard()` | (none) | outer except (silent if before processing_active) |
| `monitor_clipboard` | `generate_pipeline_id()` | (none) | silent (trivial) |
| `monitor_clipboard` | `emit_pipeline_log(...)` | pipeline_id, stage, message | exception printed, not re-raised |
| `monitor_clipboard` | `socketio.emit('status_update')` | status dict | exception in outer try (silent) |
| `monitor_clipboard` | `socketio.emit('image_preview')` | image_data_url dict | same |
| `monitor_clipboard` | `generate_content_with_fallback(...)` | [prompt, image], pipeline_id | caught by inner except api_err |
| `monitor_clipboard` | `format_clipboard_output(raw)` | raw text | caught by inner except api_err |
| `monitor_clipboard` | `pyperclip.copy(text)` | formatted text | caught by inner except api_err |
| `generate_content_with_fallback` | `genai.Client(api_key=key)` | api_key | caught, key skipped |
| `generate_content_with_fallback` | `get_available_gemini_models(client)` | client object | exception swallowed inside, returns DEFAULT |
| `generate_content_with_fallback` | `is_key_model_known_unavailable(k, m)` | key_id, model | safe |
| `generate_content_with_fallback` | `emit_pipeline_log(...)` | various | exception printed, not re-raised |
| `generate_content_with_fallback` | `client.models.generate_content(...)` | contents | caught, classified, fallback |
| `generate_content_with_fallback` | `update_key_model_health(...)` | status data | exception swallowed silently |
| `generate_content_with_fallback` | `generate_content_openai_fallback(...)` | prompt, b64_url | returns None on failure |
| `get_available_gemini_models` | `client.models.list()` | (none) | swallowed, returns DEFAULT |
| `update_key_model_health` | `socketio.emit('health_matrix_update')` | health data | swallowed silently |
| `emit_pipeline_log` | `socketio.emit('pipeline_log')` | data dict | exception printed |

---

## Identified Hang Points (Potential Causes of Stuck PROCESSING)

### HANG-1: `client.models.list()` — No Timeout
**Location**: `get_available_gemini_models()` called from `generate_content_with_fallback`, called from `monitor_clipboard`.
**Risk**: Every screenshot triggers 2 network calls (one per key) to list available models. If Gemini API is slow or unresponsive, this blocks the clipboard thread for the entire duration. No timeout. No cancellation.
**Detection**: [PIPELINE EMIT] SCREENSHOT_DETECTED would print but nothing after KEY_SELECTION_START.

### HANG-2: `genai.generate_content()` — No Timeout
**Location**: `generate_content_with_fallback` inner loop.
**Risk**: Each individual model call can take 30–120s. With 2 keys × 3 models × 3 retries = 18 possible calls, maximum block time = 18 × 120s = 36 minutes.
**Detection**: [PIPELINE EMIT] API_REQUEST_START prints but no API_RESPONSE for >10s.

### HANG-3: Exception Before `processing_active = True`
**Location**: `monitor_clipboard`, any exception between hash check (L555) and L587.
**Risk**: Base64 encoding of large images, mode conversion, or BytesIO write could raise MemoryError etc.
**Detection**: UI shows PROCESSING, no [PIPELINE EMIT] lines appear at all after IMAGE_PREPARATION_START.

### HANG-4: `pyperclip.copy()` — No Timeout
**Location**: `monitor_clipboard` L597.
**Risk**: Clipboard write can block if clipboard is locked by another process (e.g., screenshot tool).
**Detection**: CLIPBOARD_COPY_START appears in log but CLIPBOARD_COPY_SUCCESS never does.

### HANG-5: `run_all_keys_health_check()` Blocks SocketIO Thread
**Location**: `handle_run_key_health_check()`.
**Risk**: Triggered by button click. Runs synchronously on SocketIO server thread. Blocks ALL SocketIO events including pipeline_log receipt during the scan. If user clicks "Test Keys" while processing a screenshot, pipeline_log events may be queued and delayed.
**Detection**: Clicking health check button while in PROCESSING causes log events to arrive in bulk after scan completes.
