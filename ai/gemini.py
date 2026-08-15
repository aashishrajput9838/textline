"""
Google Gemini AI Provider & Multi-Key/Multi-Model Fallback Engine for Textline.
"""

import time
import os
from google import genai

from config.settings import API_KEYS_MAP
from config.constants import PROJECT_METADATA_MAP
from ai.model_manager import get_available_gemini_models
from ai.health_registry import (
    KEY_MODEL_HEALTH_REGISTRY,
    update_key_model_health,
    get_key_model_status,
    is_key_model_known_unavailable,
    classify_error_code_and_status
)
from ai.openai import generate_content_openai_fallback
from pipeline.logger import emit_pipeline_log
from pipeline.errors import NoAvailableModelError

def generate_content_with_fallback(contents, base64_image_url=None, pipeline_id="LOCAL"):
    """
    Executes content generation using structured Gemini key IDs and model-specific health states.
    Skips combinations already known to be QUOTA_EXHAUSTED, MODEL_UNAVAILABLE, or UNAUTHORIZED.
    Real generation attempts update the model-specific health registry in real-time.
    """
    errors = []
    attempts_breakdown = []
    attempt_count = 0

    valid_keys = {key_id: key_val for key_id, key_val in API_KEYS_MAP.items() if key_val and key_val != "YOUR_GEMINI_API_KEY"}
    
    if not valid_keys:
        gen_key = os.environ.get("GEMINI_API_KEY", "")
        if gen_key:
            valid_keys["DEFAULT"] = gen_key

    initial_key_id = None
    initial_model = None
    last_attempt_key_id = ""
    last_attempt_model = ""

    emit_pipeline_log(pipeline_id, "KEY_SELECTION_START", "Selecting API key...", level="RUNNING")

    # 1. Attempt Gemini multi-key rotation with dynamic model discovery
    for key_id, api_key in valid_keys.items():
        emit_pipeline_log(pipeline_id, "KEY_SELECTED", f"Key selected: {key_id}", level="SUCCESS", key_id=key_id)
        try:
            client = genai.Client(api_key=api_key)
        except Exception as client_err:
            print(f"[!] Failed to initialize Gemini client for Key ID [{key_id}]: {client_err}")
            emit_pipeline_log(pipeline_id, "KEY_ERROR", f"Key client init failed for [{key_id}]: {client_err}", level="ERROR", key_id=key_id, error_code="INVALID_ARGUMENT")
            errors.append(f"Key [{key_id}]: {client_err}")
            update_key_model_health(key_id, "all-models", "INVALID_ARGUMENT", 400, 0, f"Client Init Failed: {str(client_err)[:50]}")
            attempts_breakdown.append({
                "attempt_id": f"att_{int(time.time() * 1000)}_{attempt_count}",
                "key_id": key_id,
                "model": "client-init",
                "status_code": 400,
                "classification": "INVALID_ARGUMENT",
                "success": False
            })
            continue

        models_to_query = get_available_gemini_models(client)
        
        for model_name in models_to_query:
            if "2.5-pro" in model_name or "2.0-flash" in model_name:
                continue

            emit_pipeline_log(pipeline_id, "MODEL_SELECTION_START", f"Checking model availability for {model_name}...", level="RUNNING", key_id=key_id, model=model_name)

            # Consult latest known model-specific state before attempting!
            if is_key_model_known_unavailable(key_id, model_name):
                known_st = get_key_model_status(key_id, model_name)
                print(f"[*] Skipping known unavailable Key ID [{key_id}] with model '{model_name}' ({known_st})")
                emit_pipeline_log(pipeline_id, "MODEL_SKIPPED", f"{model_name} = {known_st}", level="WARNING", key_id=key_id, model=model_name, error_code=known_st)
                attempts_breakdown.append({
                    "attempt_id": f"att_skipped_{int(time.time() * 1000)}_{attempt_count}",
                    "key_id": key_id,
                    "model": model_name,
                    "status_code": 429 if known_st == "QUOTA_EXHAUSTED" else (404 if known_st == "MODEL_UNAVAILABLE" else 400),
                    "classification": known_st,
                    "success": False
                })
                continue

            if initial_key_id is None:
                initial_key_id = key_id
                initial_model = model_name

            max_retries = 2
            for retry_idx in range(max_retries + 1):
                attempt_count += 1
                att_id = f"att_{int(time.time() * 1000)}_{attempt_count}"
                model_start = time.time()
                try:
                    print(f"[GEMINI] before API request: {key_id} / {model_name} (Attempt {retry_idx + 1})")
                    emit_pipeline_log(pipeline_id, "API_REQUEST_START", f"Requesting Gemini API ({model_name} / Key: {key_id})...", level="RUNNING", key_id=key_id, model=model_name)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
                    latency = int((time.time() - model_start) * 1000)
                    print(f"[GEMINI] API request returned: 200 WORKING ({latency}ms)")
                    print(f"[GEMINI] attempt completed ({attempt_count})")
                    emit_pipeline_log(pipeline_id, "API_RESPONSE", f"Gemini API returned 200 WORKING ({latency}ms)", level="SUCCESS", key_id=key_id, model=model_name, http_code=200, elapsed_ms=latency)
                    
                    if response and response.text:
                        print(f"[+] Success using Gemini Key ID [{key_id}] ({model_name})")
                        update_key_model_health(key_id, model_name, "WORKING", 200, latency, "PASS")
                        attempts_breakdown.append({
                            "attempt_id": att_id,
                            "key_id": key_id,
                            "model": model_name,
                            "status_code": 200,
                            "classification": "WORKING",
                            "success": True
                        })
                        model_fallback = (model_name != initial_model)
                        key_fallback = (key_id != initial_key_id)
                        if model_fallback:
                            emit_pipeline_log(pipeline_id, "MODEL_FALLBACK", f"Model fallback triggered to {model_name}", level="INFO", key_id=key_id, model=model_name)
                        if key_fallback:
                            emit_pipeline_log(pipeline_id, "KEY_FALLBACK", f"Key fallback triggered to {key_id}", level="INFO", key_id=key_id, model=model_name)
                        
                        is_fallback = model_fallback or key_fallback
                        meta = {
                            "provider": "Google Gemini",
                            "model": model_name,
                            "key_id": key_id,
                            "project_number": PROJECT_METADATA_MAP.get(key_id, {}).get("project_number", ""),
                            "is_fallback": is_fallback,
                            "model_fallback": model_fallback,
                            "key_fallback": key_fallback,
                            "attempt_count": attempt_count,
                            "previous_model": last_attempt_model,
                            "previous_key_id": last_attempt_key_id,
                            "generation_id": f"gen_{int(time.time() * 1000)}",
                            "attempts_breakdown": attempts_breakdown,
                            "health_matrix": KEY_MODEL_HEALTH_REGISTRY
                        }
                        return response.text, meta
                except Exception as e:
                    latency = int((time.time() - model_start) * 1000)
                    last_attempt_key_id = key_id
                    last_attempt_model = model_name
                    err_str = str(e)
                    short_err = err_str.split("\n")[0] if "\n" in err_str else err_str
                    code, status_cls = classify_error_code_and_status(e)
                    print(f"[GEMINI] API request returned: {code} {status_cls} ({latency}ms)")
                    print(f"[GEMINI] attempt completed ({attempt_count})")
                    emit_pipeline_log(pipeline_id, "API_RESPONSE", f"{model_name} returned {code} {status_cls} ({latency}ms)", level="ERROR", key_id=key_id, model=model_name, http_code=code, error_code=status_cls, elapsed_ms=latency)
                    
                    if latency > 15000:
                        emit_pipeline_log(pipeline_id, "STAGE_TIMEOUT_WARNING", f"API request for {model_name} took {latency}ms (>15s)", level="WARNING", key_id=key_id, model=model_name, elapsed_ms=latency)
                    
                    update_key_model_health(key_id, model_name, status_cls, code, latency, short_err)
                    
                    attempts_breakdown.append({
                        "attempt_id": att_id,
                        "key_id": key_id,
                        "model": model_name,
                        "status_code": code,
                        "classification": status_cls,
                        "success": False
                    })
                    print(f"[!] Gemini Key ID [{key_id}] ({model_name}) failed [{status_cls}]: {short_err}")
                    errors.append(f"Key [{key_id}] [{model_name}] [{status_cls}]: {short_err}")
                    
                    # 503 High Demand Spikes: Retry up to max_retries before moving to next model
                    if status_cls == "SERVICE_UNAVAILABLE":
                        if retry_idx < max_retries:
                            wait_sec = 1.5 * (retry_idx + 1)
                            print(f"[!] 503 High Demand spike for Key ID [{key_id}] ({model_name}). Retrying in {wait_sec}s...")
                            emit_pipeline_log(pipeline_id, "503_RETRY_BACKOFF", f"503 High Demand spike. Retrying in {wait_sec}s...", level="WARNING", key_id=key_id, model=model_name)
                            time.sleep(wait_sec)
                            continue

                    # Key-level errors: 400 INVALID_ARGUMENT or 403 UNAUTHORIZED invalidates the entire key
                    if status_cls in ("INVALID_ARGUMENT", "UNAUTHORIZED"):
                        print(f"[!] Key ID [{key_id}] returned key-level error [{status_cls}]. Skipping key...")
                        emit_pipeline_log(pipeline_id, "KEY_SKIPPED", f"Skipping key {key_id} due to key-level error {status_cls}", level="WARNING", key_id=key_id, error_code=status_cls)
                        for m_rem in models_to_query:
                            update_key_model_health(key_id, m_rem, status_cls, code, latency, short_err)
                        break

                    # Model-level errors: 404 MODEL_UNAVAILABLE or 429 QUOTA_EXHAUSTED moves to next model
                    if status_cls in ("MODEL_UNAVAILABLE", "QUOTA_EXHAUSTED"):
                        print(f"[!] Key ID [{key_id}] [{model_name}] returned [{status_cls}]. Trying next model/key...")
                        break

    print("[GEMINI] all attempts exhausted")
    emit_pipeline_log(pipeline_id, "ALL_ATTEMPTS_EXHAUSTED", "No available Gemini key/model combination could be used", level="ERROR", error_code="NO_AVAILABLE_MODEL")

    # 2. Graceful Fallback to OpenAI gpt-4o-mini if configured
    if base64_image_url:
        attempt_count += 1
        prompt_str = contents[0] if isinstance(contents, list) and len(contents) > 0 else str(contents)
        emit_pipeline_log(pipeline_id, "OPENAI_FALLBACK_START", "Attempting OpenAI gpt-4o-mini fallback...", level="RUNNING")
        openai_result = generate_content_openai_fallback(prompt_str, base64_image_url)
        if openai_result:
            print("[+] Success using OpenAI (gpt-4o-mini) fallback!")
            emit_pipeline_log(pipeline_id, "OPENAI_FALLBACK_SUCCESS", "OpenAI (gpt-4o-mini) fallback succeeded!", level="SUCCESS")
            meta = {
                "provider": "OpenAI",
                "model": "gpt-4o-mini",
                "key_id": "OPENAI",
                "is_fallback": True,
                "model_fallback": True,
                "key_fallback": True,
                "attempt_count": attempt_count,
                "previous_model": last_attempt_model,
                "previous_key_id": last_attempt_key_id,
                "generation_id": f"gen_{int(time.time() * 1000)}",
                "attempts_breakdown": attempts_breakdown,
                "health_matrix": KEY_MODEL_HEALTH_REGISTRY
            }
            return openai_result, meta

    # Construct smart, model-specific error summary
    key_classifications = {}
    for att in attempts_breakdown:
        k = att["key_id"]
        if k not in key_classifications:
            key_classifications[k] = []
        key_classifications[k].append(att["classification"])

    all_keys_quota = len(key_classifications) > 0 and all(
        all(cls == "QUOTA_EXHAUSTED" for cls in cls_list)
        for cls_list in key_classifications.values()
    )

    if all_keys_quota:
        summary_msg = "No Gemini model is currently available.\nAll configured Gemini API keys have reached daily quota limits (QUOTA_EXHAUSTED)."
    else:
        lines = ["No Gemini model is currently available.\n"]
        key_groups = {}
        for att in attempts_breakdown:
            k = att["key_id"]
            if k not in key_groups:
                key_groups[k] = []
            key_groups[k].append(f"• {att['model']} -> {att['classification']}")
        
        for k, att_strings in key_groups.items():
            lines.append(f"Key {k}:")
            for s in att_strings:
                lines.append(f"  {s}")
            lines.append("")
        
        lines.append("No usable Gemini key/model combination was available.")
        summary_msg = "\n".join(lines)

    raise NoAvailableModelError(f"AI Generation Error:\n{summary_msg}", error_code="NO_AVAILABLE_MODEL")
