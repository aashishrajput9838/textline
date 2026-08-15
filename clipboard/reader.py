"""
Windows clipboard image reader for Textline.
Provides ImageGrab.grabclipboard() wrapping.
"""

from PIL import ImageGrab
from typing import Optional

def read_clipboard_image() -> Optional[object]:
    """Retrieves current content from Windows clipboard via ImageGrab."""
    try:
        return ImageGrab.grabclipboard()
    except Exception as e:
        print(f"[!] Failed to read Windows clipboard: {e}")
        return None
