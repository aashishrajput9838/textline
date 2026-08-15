"""
Clipboard writer wrapper for Textline processing outputs.
"""

import time
import pyperclip

def copy_to_clipboard(text: str):
    """Copies output text string to Windows clipboard."""
    t0 = time.time()
    pyperclip.copy(text)
    elapsed_ms = int((time.time() - t0) * 1000)
    return elapsed_ms
