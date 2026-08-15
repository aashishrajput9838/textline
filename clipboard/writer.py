"""
Windows clipboard text writer for Textline.
Provides pyperclip.copy() wrapping.
"""

import time
import pyperclip

def write_to_clipboard(text: str) -> int:
    """Copies output string to Windows clipboard and returns latency in milliseconds."""
    t0 = time.time()
    pyperclip.copy(text)
    return int((time.time() - t0) * 1000)
