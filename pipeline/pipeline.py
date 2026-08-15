"""
ScreenshotPipeline Orchestrator for Textline.
Manages full screenshot processing lifecycle with explicit stages, dual-channel logging,
and guaranteed terminal state transitions.
"""

import time
import sys

from models.pipeline_context import PipelineContext
from pipeline.stages import PipelineStage
from pipeline.logger import emit_pipeline_log
from pipeline.errors import NoAvailableModelError
from ai.gemini import generate_content_with_fallback
from image.validator import validate_image
from image.converter import convert_to_rgb, image_to_png_bytes, image_to_base64_url
from image.preview import build_image_preview_payload
from processing.formatter import format_clipboard_output
from processing.clipboard_output import copy_to_clipboard
from clipboard.hasher import compute_image_hash
from utils.timing import generate_pipeline_id
from utils.logging import safe_print

_socketio_instance = None

def set_pipeline_socketio(sio):
    """Sets socketio reference for pipeline status updates."""
    global _socketio_instance
    _socketio_instance = sio

class ScreenshotPipeline:
    """
    Orchestrates execution of a single screenshot processing request.
    Enforces explicit stage transitions and guaranteed terminal states.
    """

    def __init__(self, socketio=None):
        self.socketio = socketio or _socketio_instance

    def process(self, clipboard_content, pipeline_id=None) -> PipelineContext:
        """
        Executes full screenshot processing pipeline:
        DETECT -> READ -> VALIDATE -> PREPARE -> NOTIFY -> GENERATE -> PARSE -> WRITE -> COMPLETE
        """
        if not pipeline_id:
            pipeline_id = generate_pipeline_id()

        ctx = PipelineContext(
            pipeline_id=pipeline_id,
            image=clipboard_content,
            started_at=time.time()
        )

        p_start = ctx.started_at
        sio = self.socketio or _socketio_instance
        if not sio:
            # Fallback to app.socketio if available at runtime
            app_mod = sys.modules.get("app")
            sio = getattr(app_mod, "socketio", None)

        is_valid, width, height = validate_image(clipboard_content)
        if not is_valid:
            raise ValueError("Provided clipboard content is not a valid PIL Image")

        # 1. READ & VALIDATE
        rgb_img = convert_to_rgb(clipboard_content)
        img_bytes, t_clip = image_to_png_bytes(rgb_img)
        current_hash = compute_image_hash(img_bytes)
        ctx.image_hash = current_hash

        emit_pipeline_log(pipeline_id, PipelineStage.SCREENSHOT_DETECTED, "New screenshot detected in clipboard", level="INFO", socketio=sio)
        emit_pipeline_log(pipeline_id, PipelineStage.CLIPBOARD_READ_SUCCESS, f"Clipboard image retrieved ({t_clip}ms)", level="SUCCESS", elapsed_ms=t_clip, socketio=sio)
        emit_pipeline_log(pipeline_id, PipelineStage.IMAGE_VALIDATION_SUCCESS, f"Image validated: {width} × {height} (hash: {current_hash[:8]})", level="SUCCESS", socketio=sio)

        # 2. PREPARE
        emit_pipeline_log(pipeline_id, PipelineStage.IMAGE_PREPARATION_START, "Converting image to Base64 data URL...", level="RUNNING", socketio=sio)
        image_data_url, t_prep = image_to_base64_url(img_bytes)
        ctx.image_b64_url = image_data_url
        emit_pipeline_log(pipeline_id, PipelineStage.IMAGE_PREPARATION_SUCCESS, f"Image prepared as Base64 data URL ({t_prep}ms)", level="SUCCESS", elapsed_ms=t_prep, socketio=sio)

        # 3. NOTIFY SOCKETS (Status = processing)
        if sio:
            sio.emit('status_update', {
                'status': 'processing',
                'message': 'New screenshot detected! Processing...',
                'timestamp': time.strftime("%H:%M:%S"),
                'pipeline_id': pipeline_id
            })
            sio.emit('image_preview', build_image_preview_payload(image_data_url, pipeline_id))

        prompt = "give me complete code in the given language,\nmake sure -\n1. my code should be very fast in terms of speed.\n2. remove any spaces from the starting of each line in the code.\n\nMost important -- I don't need any explanation or any other content, not even a single irrelevant word. The output should be only the code."

        ctx.status = "processing"
        emit_pipeline_log(pipeline_id, PipelineStage.GENERATION_START, "Starting multi-provider AI generation pipeline...", level="RUNNING", socketio=sio)

        try:
            raw_answer, meta = generate_content_with_fallback([prompt, clipboard_content], base64_image_url=image_data_url, pipeline_id=pipeline_id)
            emit_pipeline_log(pipeline_id, PipelineStage.GENERATION_SUCCESS, f"Generation succeeded via {meta.get('provider')} ({meta.get('model')})", level="SUCCESS", socketio=sio)
            
            final_clipboard_text = format_clipboard_output(raw_answer)
            ctx.answer = final_clipboard_text
            ctx.metadata = meta

            emit_pipeline_log(pipeline_id, PipelineStage.CLIPBOARD_COPY_START, "Copying output to Windows clipboard...", level="RUNNING", socketio=sio)
            t_copy = copy_to_clipboard(final_clipboard_text)
            emit_pipeline_log(pipeline_id, PipelineStage.CLIPBOARD_COPY_SUCCESS, f"Output copied to Windows clipboard ({t_copy}ms)", level="SUCCESS", elapsed_ms=t_copy, socketio=sio)

            if sio:
                sio.emit('status_update', {
                    'status': 'success',
                    'message': 'Done! Answer copied to clipboard.',
                    'answer': final_clipboard_text,
                    'timestamp': time.strftime("%H:%M:%S"),
                    'metadata': meta,
                    'pipeline_id': pipeline_id
                })

            total_elapsed = int((time.time() - p_start) * 1000)
            emit_pipeline_log(pipeline_id, PipelineStage.PIPELINE_COMPLETE, f"Pipeline completed successfully in {total_elapsed} ms", level="SUCCESS", elapsed_ms=total_elapsed, socketio=sio)
            ctx.status = "success"
            return ctx

        except Exception as api_err:
            ctx.status = "error"
            err_str = str(api_err)
            error_code = getattr(api_err, "error_code", "NO_AVAILABLE_MODEL")
            error_msg = err_str if err_str.startswith("AI Generation Error") else f"AI Generation Error: {err_str}"
            ctx.error_code = error_code
            ctx.error_message = error_msg
            total_elapsed = int((time.time() - p_start) * 1000)

            emit_pipeline_log(pipeline_id, PipelineStage.GENERATION_ERROR, f"Error: {error_code} - {error_msg}", level="ERROR", error_code=error_code, elapsed_ms=total_elapsed, socketio=sio)
            if sio:
                sio.emit('status_update', {
                    'status': 'error',
                    'message': error_msg,
                    'error_code': error_code,
                    'timestamp': time.strftime("%H:%M:%S"),
                    'pipeline_id': pipeline_id
                })
            emit_pipeline_log(pipeline_id, PipelineStage.PIPELINE_ERROR, f"Final status: ERROR ({error_code})", level="ERROR", error_code=error_code, socketio=sio)
            emit_pipeline_log(pipeline_id, PipelineStage.PIPELINE_COMPLETE, f"Pipeline terminated with ERROR in {total_elapsed} ms", level="ERROR", error_code=error_code, elapsed_ms=total_elapsed, socketio=sio)
            raise api_err
