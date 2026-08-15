"""
Timing and ID generation utilities for Textline.
"""

import time

def generate_pipeline_id():
    """Generates a unique timestamp-based pipeline execution ID."""
    t_str = time.strftime("%Y%m%d-%H%M%S")
    rand_suffix = f"{int(time.time() * 1000) % 0x10000:04X}"
    return f"{t_str}-{rand_suffix}"
