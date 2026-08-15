"""
Response parsing utilities for Textline model outputs.
"""

def parse_response_text(raw_answer: str) -> str:
    """Strips leading whitespace from model response text."""
    if not raw_answer:
        return ""
    return raw_answer.lstrip()
