"""
Output response formatting and padding for Textline.
"""

def format_clipboard_output(raw_answer: str) -> str:
    """Enforces Python Post-Processing Padding (50 single-spaced lines + terminating dot)."""
    clean_code = raw_answer.lstrip() if raw_answer else "No text returned from model."
    return clean_code + "\n" + "\n".join([" "] * 50) + "\n."
