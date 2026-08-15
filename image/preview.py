"""
Image preview payload builder for Textline dashboard UI.
"""

def build_image_preview_payload(image_data_url: str, pipeline_id: str) -> dict:
    """Builds image preview Socket.IO payload."""
    return {
        "image_url": image_data_url,
        "pipeline_id": pipeline_id
    }
