"""
Image format converter and Base64 encoder for Textline.
"""

import io
import base64
import time
from PIL import Image

def convert_to_rgb(image: Image.Image) -> Image.Image:
    """Converts RGBA or Palette images to RGB format."""
    if image.mode in ("RGBA", "P"):
        return image.convert("RGB")
    return image

def image_to_png_bytes(image: Image.Image):
    """Converts a PIL Image object to raw PNG bytes."""
    t0 = time.time()
    img_byte_arr = io.BytesIO()
    rgb_image = convert_to_rgb(image)
    rgb_image.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    elapsed_ms = int((time.time() - t0) * 1000)
    return img_bytes, elapsed_ms

def image_to_base64_url(img_bytes: bytes):
    """Encodes raw PNG bytes into a Base64 data URL string."""
    t0 = time.time()
    base64_img = base64.b64encode(img_bytes).decode('utf-8')
    image_data_url = f"data:image/png;base64,{base64_img}"
    elapsed_ms = int((time.time() - t0) * 1000)
    return image_data_url, elapsed_ms
