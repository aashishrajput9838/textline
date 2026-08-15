"""
SHA-256 Image hashing utility for Textline screenshot deduplication.
"""

import hashlib

def compute_image_hash(img_bytes: bytes) -> str:
    """Computes SHA-256 hex digest of raw PNG bytes."""
    return hashlib.sha256(img_bytes).hexdigest()
