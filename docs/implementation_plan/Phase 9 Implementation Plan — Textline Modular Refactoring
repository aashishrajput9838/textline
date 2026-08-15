# Phase 9 Implementation Plan — Textline Modular Refactoring

> **Status**: Ready for User Review (No source code files modified yet)  
> **Goal**: Refactor `app.py` (831 lines) and `templates/index.html` (1564 lines) into a clean, decoupled modular package structure (`textline/`) while preserving 100% of existing behavior, Gemini key/model fallback logic, quota accounting, provenance calculation, and passing all 42 unit tests at every stage.

---

## User Review Required

> [!IMPORTANT]
> **Zero Behavior Change Guarantee**:
> 1. Gemini model-selection order (`gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-flash-latest`), key-rotation order, 503 exponential backoff, health registry status classifications (`QUOTA_EXHAUSTED`, `MODEL_UNAVAILABLE`, `UNAUTHORIZED`, `INVALID_ARGUMENT`), and metadata provenance will NOT be altered.
> 2. All 42 existing unit tests in `test_fallback_system.py` will pass at EVERY extraction step without modification to test logic.
> 3. PyInstaller build (`app.spec`) will be updated to bundle all new package directories (`config`, `server`, `clipboard`, `image`, `pipeline`, `ai`, `processing`, `models`, `utils`, `static`) so that `dist/app.exe` functions identically.

---

## Part A: Current Module & Function Map (`app.py`)

Below is the complete audit map of every symbol and function currently in `app.py`:

```text
app.py (831 lines)
 ├── UTF-8 Reconfiguration (L13–23) & safe_print() (L25–39)
 ├── PyInstaller _MEIPASS / dotenv loading (L48–67)
 ├── Flask & SocketIO initialization (L69–74)
 │    ├── app = Flask(...)
 │    └── socketio = SocketIO(..., async_mode="threading")
 ├── API_KEYS_MAP & load_api_keys_map() (L77–97)
 ├── OPENAI_API_KEY & DEFAULT_GEMINI_MODELS (L99–103)
 ├── classify_error_code_and_status(err) (L105–121)
 ├── get_available_gemini_models(client) (L123–137)
 ├── generate_content_openai_fallback(prompt, base64_image_url) (L139–174)
 ├── PROJECT_METADATA_MAP & SUPPORTED_HEALTH_MODELS (L177–189)
 ├── KEY_MODEL_HEALTH_REGISTRY & update_key_model_health() (L192–224)
 ├── generate_pipeline_id() (L225–229)
 ├── emit_pipeline_log() (L231–274)
 ├── get_key_model_status() & is_key_model_known_unavailable() (L276–285)
 ├── generate_content_with_fallback() (L287–520)
 ├── NoAvailableModelError (L522–526)
 ├── format_clipboard_output() (L528–531)
 ├── monitor_clipboard() (L533–649)
 ├── discover_all_gemini_keys() (L651–682)
 ├── test_key_model_diagnostic() (L684–747)
 ├── run_all_keys_health_check() (L749–759)
 ├── Flask HTTP Routes (L761–783)
 │    ├── GET / -> index()
 │    ├── GET /api/test-keys -> api_test_keys()
 │    └── GET /api/health-state -> api_health_state()
 ├── Socket.IO Handlers (L785–807)
 │    ├── @socketio.on('connect') -> handle_connect()
 │    └── @socketio.on('run_key_health_check') -> handle_run_key_health_check()
 ├── print_startup_health_check() (L809–820)
 └── __main__ (L821–831)
      ├── clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
      └── socketio.run(app, host='127.0.0.1', port=5000)
```

---

## Part B: Proposed Migration Map

The table below details exactly where every existing element will be relocated:

| Current File & Symbol (`app.py`) | Target Module & File | Target Symbol / Function |
|---|---|---|
| `safe_print`, UTF-8 setup | `utils/logging.py` | `safe_print()`, `setup_utf8_logging()` |
| `generate_pipeline_id` | `utils/timing.py` | `generate_pipeline_id()`, `get_timestamp_str()` |
| `DEFAULT_GEMINI_MODELS`, `SUPPORTED_HEALTH_MODELS`, `PROJECT_METADATA_MAP` | `config/settings.py` | Exported constants |
| `load_api_keys_map()`, `OPENAI_API_KEY` | `config/settings.py` | `API_KEYS_MAP`, `load_api_keys_map()` |
| `app`, `socketio` | `server/flask_app.py` | `create_app()`, `get_socketio()` |
| `index()`, `api_test_keys()`, `api_health_state()` | `server/flask_app.py` | Route handlers |
| `handle_connect()`, `handle_run_key_health_check()` | `server/socket_events.py` | Socket.IO event listeners |
| `ImageGrab.grabclipboard()` | `clipboard/reader.py` | `read_clipboard_image(timeout=5.0)` |
| `hashlib.sha256(img_bytes)` | `clipboard/hasher.py` | `compute_image_hash(img_bytes)` |
| `pyperclip.copy()` | `clipboard/writer.py` | `write_to_clipboard(text, timeout=2.0)` |
| RGB mode conversion & `b64encode` | `image/converter.py` | `convert_to_rgb()`, `image_to_base64()` |
| PIL image type validation | `image/validator.py` | `validate_image(image)` |
| `data:image/png;base64` builder | `image/preview.py` | `build_image_data_url(b64_str)` |
| `KEY_MODEL_HEALTH_REGISTRY`, `update_key_model_health()` | `ai/health_registry.py` | `HealthRegistry` class & methods |
| `get_key_model_status()`, `is_key_model_known_unavailable()` | `ai/health_registry.py` | `get_status()`, `is_known_unavailable()` |
| `classify_error_code_and_status()` | `ai/health_registry.py` | `classify_error_code_and_status()` |
| `discover_all_gemini_keys()` | `ai/key_manager.py` | `discover_all_gemini_keys()` |
| `get_available_gemini_models()` | `ai/model_manager.py` | `get_available_gemini_models()` |
| `genai.Client` call & Gemini logic | `ai/gemini.py` | `GeminiProvider` class |
| `generate_content_openai_fallback()` | `ai/openai.py` | `OpenAIProvider` class |
| `emit_pipeline_log()` | `pipeline/logger.py` | `PipelineLogger.emit()` |
| `NoAvailableModelError` | `pipeline/errors.py` | `NoAvailableModelError`, `PipelineTimeoutError` |
| Execution stage enum | `pipeline/stages.py` | `PipelineStage` Enum |
| State/Context dataclass | `models/pipeline_context.py` | `PipelineContext` dataclass |
| Attempt breakdown dataclass | `models/attempt_record.py` | `AttemptRecord` dataclass |
| Orchestrator (`generate_content_with_fallback`) | `pipeline/pipeline.py` | `ScreenshotPipeline.process(ctx)` |
| `format_clipboard_output()` | `processing/formatter.py` | `format_clipboard_output()` |
| `monitor_clipboard()` loop | `clipboard/monitor.py` | `ClipboardMonitor.start()` (thin loop) |
| Embedded JavaScript | `static/js/*.js` | `socket.js`, `pipeline-log.js`, `status.js`, `api-health.js`, `dashboard.js` |

---

## Part C: Dependency Risk Analysis

| Risk Area | Specific Risk | Mitigation Strategy |
|---|---|---|
| **1. Circular Imports** | `pipeline/pipeline.py` imports `ai/gemini.py`, which imports `pipeline/logger.py`, which imports `server/flask_app.py` (`socketio`). | Dependency inversion: `PipelineLogger` accepts `socketio` instance or callback. `ai/` modules accept `PipelineLogger` interface, never import server. |
| **2. Global State** | `KEY_MODEL_HEALTH_REGISTRY` and `API_KEYS_MAP` are mutated/read across threads. | Wrap `KEY_MODEL_HEALTH_REGISTRY` in a thread-safe `HealthRegistry` singleton with `threading.RLock()`. |
| **3. Socket.IO Threading** | `socketio.emit()` called from background daemon thread (`monitor_clipboard`). | Flask-SocketIO `async_mode="threading"` allows background thread emits. Keep reference in `server/flask_app.py`. |
| **4. Test Dependencies** | `test_fallback_system.py` directly patches `app.API_KEYS_MAP`, `app.genai.Client`, `app.KEY_MODEL_HEALTH_REGISTRY`, `app.socketio`. | Maintain backward-compatible aliases in `app.py` (`app.API_KEYS_MAP = settings.API_KEYS_MAP`, etc.) so `test_fallback_system.py` passes without needing test code edits. |
| **5. PyInstaller Packaging** | Executable missing new package directories or serving stale static files. | Update `app.spec` `datas` parameter to bundle `('static', 'static')` and `('templates', 'templates')`. Verify PyInstaller hook inclusions. |

---

## Part D: Migration Order & Execution Sequence

We will execute the refactoring in **10 small, isolated, fully testable phases**:

```text
Phase 9.1: Utils & Config Extraction
  └── Create utils/ & config/ -> test_fallback_system.py (42/42 pass)

Phase 9.2: Dataclasses & Errors
  └── Create models/ & pipeline/errors.py, stages.py -> test_fallback_system.py (42/42 pass)

Phase 9.3: Health Registry & Key/Model Managers
  └── Create ai/health_registry.py, key_manager.py, model_manager.py -> test_fallback_system.py (42/42 pass)

Phase 9.4: AI Providers (Gemini & OpenAI)
  └── Create ai/gemini.py, ai/openai.py -> test_fallback_system.py (42/42 pass)

Phase 9.5: Image & Processing Handlers
  └── Create image/ & processing/ -> test_fallback_system.py (42/42 pass)

Phase 9.6: Pipeline Logger & Context Orchestrator
  └── Create pipeline/logger.py, context.py, pipeline.py -> test_fallback_system.py (42/42 pass)

Phase 9.7: Clipboard Reader/Hasher/Writer & Monitor
  └── Create clipboard/ -> test_fallback_system.py (42/42 pass)

Phase 9.8: Server & Socket Event Handler Modularization
  └── Create server/flask_app.py, socket_events.py -> test_fallback_system.py (42/42 pass)

Phase 9.9: Frontend JS Modularization
  └── Extract static/js/*.js & update templates/index.html -> manual browser check

Phase 9.10: Reorganize Tests & PyInstaller Build Verification
  └── Create modular tests/, update app.spec, run PyInstaller --clean, verify app.exe
```

---

## Part E: Test & Verification Checkpoints

After **EVERY SINGLE PHASE**, the following automated verification command MUST be executed:

```powershell
python -m unittest test_fallback_system.py
```
**Required Result**: `Ran 42 tests in ~0.07s OK (RESULTS -> FAILURES: 0, ERRORS: 0, TOTAL: 42)`.

At **Phase 9.10**, the executable build verification command MUST be executed:

```powershell
python -m PyInstaller app.spec --clean
```
**Required Result**: `Build complete! The results are available in: C:\github\textline\dist\app.exe`.

---

## Verification Plan

### Automated Testing
- Execute unit test suite after each step:
  `python -m unittest test_fallback_system.py`
- Verify 42/42 tests pass with 0 failures and 0 errors.

### Standalone Binary Testing
- Build single-file executable:
  `python -m PyInstaller app.spec --clean`
- Confirm `dist/app.exe` launches and serves dashboard with live pipeline logs.
