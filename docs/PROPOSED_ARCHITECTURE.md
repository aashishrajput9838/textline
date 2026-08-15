# TEXTLINE — PROPOSED MODULAR ARCHITECTURE

> Investigation only. No source files modified.

---

## Phase 4 — Proposed Module Structure

```
textline/
│
├── app.py                      Entry point — server bootstrap only
│
├── config/
│   ├── settings.py             All env var reads, API key loading
│   └── constants.py            DEFAULT_GEMINI_MODELS, SUPPORTED_HEALTH_MODELS, etc.
│
├── server/
│   ├── flask_app.py            Flask app factory, routes (GET /)
│   └── socket_events.py        All @socketio.on() handlers
│
├── clipboard/
│   ├── monitor.py              Clipboard polling loop, hash comparison, thread management
│   ├── reader.py               ImageGrab.grabclipboard() wrapper with timeout
│   ├── hasher.py               SHA-256 image fingerprinting
│   └── writer.py               pyperclip.copy() wrapper with timeout
│
├── image/
│   ├── validator.py            PIL Image type/mode checks
│   ├── converter.py            PNG → BytesIO, Base64 encoding
│   └── preview.py              data:image/png;base64 URL builder
│
├── pipeline/
│   ├── pipeline.py             ScreenshotPipeline.process(image) — orchestrator only
│   ├── context.py              PipelineContext dataclass
│   ├── stages.py               Stage enum + stage transition logic
│   ├── logger.py               emit_pipeline_log() — isolated Socket.IO bridge
│   └── errors.py               PipelineError, TimeoutError, NoModelError
│
├── ai/
│   ├── gemini/
│   │   ├── client.py           genai.Client factory
│   │   ├── key_manager.py      Key rotation, valid_keys filtering
│   │   ├── model_manager.py    Model discovery + filtering
│   │   ├── health.py           KEY_MODEL_HEALTH_REGISTRY, update/get/is_unavailable
│   │   └── quota.py            Quota exhaustion detection + classification
│   │
│   ├── openai/
│   │   └── client.py           OpenAI fallback, explicit timeout
│   │
│   ├── provider.py             Provider enum (GEMINI, OPENAI)
│   └── fallback.py             generate_content_with_fallback() — cleaned
│
├── processing/
│   ├── response_parser.py      Raw response text extraction
│   ├── formatter.py            format_clipboard_output()
│   └── clipboard_output.py     pyperclip write with error handling
│
├── models/
│   ├── pipeline.py             PipelineContext, PipelineResult dataclasses
│   ├── ai.py                   GenerationMeta, AttemptRecord dataclasses
│   └── health.py               HealthEntry, HealthStatus enum
│
├── utils/
│   ├── logging.py              safe_print(), stdout reconfigure
│   └── timing.py               generate_pipeline_id(), elapsed_ms helpers
│
├── templates/
│   └── index.html              Dashboard (unchanged HTML structure)
│
├── static/
│   ├── css/
│   │   └── dashboard.css       Extracted from <style> block
│   └── js/
│       ├── socket_client.js    Socket.IO init, connection handlers
│       ├── pipeline.js         pipeline_log listener, log panel DOM
│       ├── health.js           health_matrix_update listener, health panel
│       ├── usage.js            localStorage usage tracking
│       └── dashboard.js        status_update handler, answer/provenance display
│
└── tests/
    ├── test_clipboard.py       Clipboard detection, hash, timeout
    ├── test_pipeline.py        Full pipeline lifecycle, context, stages
    ├── test_ai.py              Gemini/OpenAI generation, key rotation
    ├── test_health.py          Health registry updates, is_unavailable
    ├── test_fallback.py        Existing test_fallback_system.py (migrated)
    └── test_socket_events.py   pipeline_log emission, socket event names
```

---

## Phase 5 — ScreenshotPipeline Design

```python
class Stage(Enum):
    DETECT          = "DETECT"
    READ_CLIPBOARD  = "READ_CLIPBOARD"
    VALIDATE_IMAGE  = "VALIDATE_IMAGE"
    PREPARE_IMAGE   = "PREPARE_IMAGE"
    SELECT_PROVIDER = "SELECT_PROVIDER"
    SELECT_KEY      = "SELECT_KEY"
    SELECT_MODEL    = "SELECT_MODEL"
    AI_REQUEST      = "AI_REQUEST"
    AI_RESPONSE     = "AI_RESPONSE"
    FORMAT_RESPONSE = "FORMAT_RESPONSE"
    WRITE_CLIPBOARD = "WRITE_CLIPBOARD"
    COMPLETE        = "COMPLETE"

@dataclass
class PipelineContext:
    pipeline_id:    str
    started_at:     float
    image:          Optional[Image.Image]
    image_hash:     Optional[str]
    image_b64_url:  Optional[str]
    selected_key:   Optional[str]
    selected_model: Optional[str]
    provider:       Optional[str]
    stage:          Stage
    status:         str           # "running" | "success" | "error"
    error_code:     Optional[str]
    error_message:  Optional[str]
    timings:        dict[str, int] # stage → elapsed_ms

class ScreenshotPipeline:
    def process(self, image: Image.Image) -> PipelineContext:
        ctx = PipelineContext(pipeline_id=generate_pipeline_id(), ...)
        try:
            ctx = self._read_clipboard(ctx)
            ctx = self._validate_image(ctx)
            ctx = self._prepare_image(ctx)
            ctx = self._run_ai(ctx)
            ctx = self._format_response(ctx)
            ctx = self._write_clipboard(ctx)
            ctx.status = "success"
            ctx.stage = Stage.COMPLETE
        except PipelineError as e:
            ctx.status = "error"
            ctx.error_code = e.error_code
            ctx.error_message = str(e)
        finally:
            self._emit_complete(ctx)   # ALWAYS emits — no stuck PROCESSING
        return ctx
```

---

## Phase 7 — Required Timeouts

| Operation | Current | Required |
|---|---|---|
| `ImageGrab.grabclipboard()` | None | 5s via threading.Timer |
| `client.models.list()` | None | 10s (or remove call, use DEFAULT always) |
| `genai.generate_content()` | None | 30s per attempt |
| `openai.chat.completions.create()` | None | 30s |
| `pyperclip.copy()` | None | 2s |

```python
def with_timeout(func, args, timeout_s, error_code):
    result = [None]
    exc = [None]
    def _run():
        try:
            result[0] = func(*args)
        except Exception as e:
            exc[0] = e
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        raise TimeoutError(f"Operation timed out after {timeout_s}s", error_code=error_code)
    if exc[0]:
        raise exc[0]
    return result[0]
```

---

## Phase 6 — Responsibility Boundaries

| Layer | MUST do | MUST NOT do |
|---|---|---|
| `clipboard/monitor.py` | Detect new images, call pipeline | Know anything about AI, SocketIO, or prompts |
| `pipeline/pipeline.py` | Orchestrate stages, manage context | Make AI calls directly, write clipboard |
| `ai/fallback.py` | AI generation, key/model rotation | Emit SocketIO events, read clipboard |
| `processing/formatter.py` | Format raw text output | Know about AI providers or models |
| `server/socket_events.py` | All SocketIO emit/on | Business logic |
| `templates/index.html` | Presentation, receive events | Business logic |

---

## Phase 8 — Test Migration Table

| Existing Test | Current Location | New Module |
|---|---|---|
| test_0: zero keys | test_fallback_system.py | tests/test_ai.py (key_manager) |
| test_1: key ordering | test_fallback_system.py | tests/test_ai.py (key_manager) |
| test_2: post-processing padding | test_fallback_system.py | tests/test_pipeline.py (formatter) |
| test_3: 404 rotation | test_fallback_system.py | tests/test_fallback.py |
| test_4–6: various errors | test_fallback_system.py | tests/test_fallback.py |
| test_7: env var safety | test_fallback_system.py | tests/test_ai.py |
| test_8: case-insensitive dedup | test_fallback_system.py | tests/test_ai.py (key_manager) |
| test_9: provenance metadata | test_fallback_system.py | tests/test_ai.py |
| test_10–39: various fallback | test_fallback_system.py | tests/test_fallback.py |
| test_40: pipeline_log emission | test_fallback_system.py | tests/test_socket_events.py |
| test_41: terminal error logs | test_fallback_system.py | tests/test_socket_events.py |

**New Tests Required:**

| Test | Module | Scenario |
|---|---|---|
| test_clipboard_timeout | test_clipboard.py | ImageGrab blocks → TimeoutError |
| test_models_list_timeout | test_ai.py | client.models.list() timeout → uses DEFAULT |
| test_gemini_request_timeout | test_fallback.py | generate_content() timeout → next model |
| test_pipeline_stuck_never | test_pipeline.py | Any exception → PIPELINE_COMPLETE always emitted |
| test_pipeline_context_stages | test_pipeline.py | All 12 stages reached on success |
| test_pipeline_context_error | test_pipeline.py | Error stage set correctly on failure |
| test_pipeline_id_unique | test_pipeline.py | pipeline_id differs across calls |
| test_socket_pipeline_log_received | test_socket_events.py | pipeline_log event arrives in frontend test client |
| test_socket_status_processing | test_socket_events.py | status_update processing fired before generation |
| test_socket_status_complete | test_socket_events.py | status_update success fired after generation |

---

## Phase 9 — Migration Plan (Small Safe Phases)

### Phase 9.1 — Extract constants (SAFE, no behavior change)
**Files created**: `config/constants.py`, `config/settings.py`
**Files modified**: `app.py` (imports only)
**Risk**: Zero — read-only constants

### Phase 9.2 — Extract models (SAFE dataclasses)
**Files created**: `models/pipeline.py`, `models/ai.py`, `models/health.py`
**Risk**: Zero — no logic

### Phase 9.3 — Extract utils (SAFE)
**Files created**: `utils/logging.py`, `utils/timing.py`
**Files modified**: `app.py` (imports)
**Risk**: Near-zero

### Phase 9.4 — Extract health registry (SAFE)
**Files created**: `ai/gemini/health.py`
**Files modified**: `app.py` (import health module)
**Verification**: All 42 tests pass

### Phase 9.5 — Extract AI generation (SAFE — matching current behavior)
**Files created**: `ai/gemini/client.py`, `ai/gemini/key_manager.py`, `ai/gemini/model_manager.py`, `ai/fallback.py`, `ai/openai/client.py`
**Files modified**: `app.py` (import from ai/)
**Verification**: All 42 tests pass (test file unchanged)

### Phase 9.6 — Add timeouts (BEHAVIOR CHANGE — REQUIRES NEW TESTS)
**Files modified**: `ai/gemini/client.py`, `ai/gemini/model_manager.py`, `ai/openai/client.py`
**New tests**: timeout scenarios
**Verification**: All 42 + new tests pass

### Phase 9.7 — Extract pipeline with PipelineContext (STRUCTURAL)
**Files created**: `pipeline/pipeline.py`, `pipeline/context.py`, `pipeline/stages.py`, `pipeline/errors.py`, `pipeline/logger.py`
**Files modified**: `clipboard/monitor.py` (call pipeline instead of inline logic)
**Key invariant**: `finally: emit_complete()` block guarantees no stuck PROCESSING
**Verification**: All 42 + new tests pass

### Phase 9.8 — Extract clipboard (SAFE)
**Files created**: `clipboard/monitor.py`, `clipboard/reader.py`, `clipboard/hasher.py`, `clipboard/writer.py`
**Files modified**: `app.py` (import clipboard.monitor)
**Verification**: Live test with screenshot

### Phase 9.9 — Extract server/socket layer (SAFE)
**Files created**: `server/flask_app.py`, `server/socket_events.py`
**Files modified**: `app.py` (imports only)
**Verification**: Socket.IO tests pass

### Phase 9.10 — Extract frontend static files
**Files created**: `static/js/pipeline.js`, `static/js/health.js`, etc.
**Files modified**: `templates/index.html` (script → src references)
**Verification**: Browser DevTools shows all events received

---

## Files Created (New)

```
config/settings.py
config/constants.py
server/flask_app.py
server/socket_events.py
clipboard/monitor.py
clipboard/reader.py
clipboard/hasher.py
clipboard/writer.py
image/validator.py
image/converter.py
image/preview.py
pipeline/pipeline.py
pipeline/context.py
pipeline/stages.py
pipeline/logger.py
pipeline/errors.py
ai/gemini/client.py
ai/gemini/key_manager.py
ai/gemini/model_manager.py
ai/gemini/health.py
ai/gemini/quota.py
ai/openai/client.py
ai/provider.py
ai/fallback.py
processing/response_parser.py
processing/formatter.py
processing/clipboard_output.py
models/pipeline.py
models/ai.py
models/health.py
utils/logging.py
utils/timing.py
static/css/dashboard.css
static/js/socket_client.js
static/js/pipeline.js
static/js/health.js
static/js/usage.js
static/js/dashboard.js
tests/test_clipboard.py
tests/test_pipeline.py
tests/test_ai.py
tests/test_health.py
tests/test_fallback.py
tests/test_socket_events.py
```

## Files Modified (Existing)

```
app.py              — reduced to ~30 lines: import + start server + start clipboard thread
templates/index.html — <script src=...> instead of inline JS
test_fallback_system.py — update imports to new module paths (tests themselves unchanged)
requirements.txt    — no changes
app.spec            — update to include new directories in datas
```

## Files Preserved Unchanged (Behavior)

```
.env                — untouched
textline_logo.ico   — untouched
```

---

## Current Processing Execution Trace (Exact)

```
[T+0ms]    clipboard_thread wakes from time.sleep(1)
[T+0ms]    pipeline_id = None, p_start = time.time()
[T+0ms]    ImageGrab.grabclipboard() called     ← BLOCKING
[T+~2ms]   returns PIL.Image
[T+~3ms]   .convert("RGB") if needed
[T+~5ms]   .save(BytesIO, 'PNG')                ← may take 10–50ms for large images
[T+~15ms]  hashlib.sha256(img_bytes)
[T+~16ms]  current_hash != last_image_hash → TRUE (new screenshot)
[T+~16ms]  last_image_hash = current_hash
[T+~16ms]  pipeline_id = generate_pipeline_id()
[T+~16ms]  emit_pipeline_log(SCREENSHOT_DETECTED)
           → socketio.emit('pipeline_log', {...})     ← event goes into SocketIO queue
[T+~17ms]  emit_pipeline_log(CLIPBOARD_READ_SUCCESS)
[T+~17ms]  emit_pipeline_log(IMAGE_VALIDATION_SUCCESS)
[T+~18ms]  emit_pipeline_log(IMAGE_PREPARATION_START)
[T+~18ms]  base64.b64encode(img_bytes)           ← BLOCKING, 1–10ms
[T+~25ms]  emit_pipeline_log(IMAGE_PREPARATION_SUCCESS)
[T+~26ms]  socketio.emit('status_update', processing)  ← UI SHOWS PROCESSING
[T+~27ms]  socketio.emit('image_preview', image_data_url)
[T+~27ms]  processing_active = True
[T+~28ms]  emit_pipeline_log(GENERATION_START)
[T+~28ms]  generate_content_with_fallback() called
           → emit_pipeline_log(KEY_SELECTION_START)
           → emit_pipeline_log(KEY_SELECTED, key1)
           → genai.Client(api_key=key1)
           → get_available_gemini_models(client)
              → client.models.list()              ← BLOCKING HTTP, 200–5000ms
           → is_key_model_known_unavailable(key1, gemini-2.5-flash)
             → True (QUOTA_EXHAUSTED) → MODEL_SKIPPED, continue
           → is_key_model_known_unavailable(key1, gemini-2.5-flash-lite)
             → True (MODEL_UNAVAILABLE) → MODEL_SKIPPED, continue
           → is_key_model_known_unavailable(key1, gemini-flash-latest)
             → True (QUOTA_EXHAUSTED) → MODEL_SKIPPED, continue
           → emit_pipeline_log(KEY_SELECTED, key2)
           → genai.Client(api_key=key2)
           → get_available_gemini_models(client)
              → client.models.list()              ← BLOCKING HTTP, 200–5000ms
           → all models QUOTA/UNAVAILABLE → all SKIPPED
           → emit_pipeline_log(ALL_ATTEMPTS_EXHAUSTED)
           → generate_content_openai_fallback() → returns None (not configured)
           → raise NoAvailableModelError(...)
[T+?ms]    caught by inner except api_err in monitor_clipboard L612
           → emit_pipeline_log(GENERATION_ERROR)
           → socketio.emit('status_update', error)
           → emit_pipeline_log(PIPELINE_ERROR)
           → emit_pipeline_log(PIPELINE_COMPLETE)
           → processing_active = False
[T+?ms]    time.sleep(1)
```

**The critical observation**: When all models are QUOTA_EXHAUSTED (health registry cached), `client.models.list()` is STILL called for each key. This is a hidden `models.list()` network call inside `get_available_gemini_models()` that happens EVEN WHEN all models are pre-known to be unavailable.

---

## Root Cause Summary for Pipeline Log Being Empty

After complete codebase audit, there are **two separate causes** depending on which binary is running:

### Cause A: Running `dist/app.exe` (Most Likely)

The EXE was built with `console=False` from source that did NOT yet have the `socket.on('pipeline_log')` listener in `index.html`. The template baked into the EXE serves the OLD frontend. The backend correctly emits pipeline_log events, but the OLD frontend has no listener registered for them.

**Fix**: Rebuild EXE after confirming all changes are in place, OR run via `python app.py` directly.

### Cause B: Running `python app.py` but `get_available_gemini_models()` hangs

The clipboard thread calls `client.models.list()` with no timeout. If the Gemini API is slow, this blocks the thread (and delays ALL SocketIO emissions from that thread) for many seconds — potentially past the point where the user considers it "hung".

Pipeline_log events ARE queued but may arrive to the browser in a burst after the models.list() call returns.

**Fix**: Remove `client.models.list()` call (always use `DEFAULT_GEMINI_MODELS`) OR add a 5-second timeout.

### Cause C: SocketIO Threading Mode Dispatch

`emit_pipeline_log` calls `socketio.emit()` from a daemon background thread. In Flask-SocketIO threading mode, this is documented as safe. However, if Werkzeug is not in threaded mode (e.g., `threaded=False` default), broadcasts from background threads may not be delivered until the next request/event cycle.

`socketio.run(app, ..., allow_unsafe_werkzeug=True)` starts Werkzeug in threaded mode by default via Flask-SocketIO's threading async_mode, so this should work — but has not been verified under load.

**Fix**: Use `socketio.start_background_task()` for the clipboard monitoring thread instead of `threading.Thread`, ensuring it runs within Flask-SocketIO's managed thread pool.
