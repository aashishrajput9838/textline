"""
Image type and format validator for Textline.
"""

from PIL import Image

def validate_image(clipboard_content):
    """Validates if clipboard content is a valid PIL Image object."""
    if isinstance(clipboard_content, Image.Image):
        width, height = clipboard_content.size
        return True, width, height
    return False, 0, 0
