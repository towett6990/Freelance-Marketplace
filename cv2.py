"""Lightweight cv2 shim for tests: implements basic image I/O and text drawing
using Pillow and numpy. This is NOT a full replacement for OpenCV; it only
implements the small subset used by the test suite (imread, imwrite, putText,
cvtColor, resize and a couple of constants).
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os

# Constants used in tests
FONT_HERSHEY_SIMPLEX = 0
COLOR_BGR2RGB = 1

def imwrite(path, arr):
    try:
        # arr is expected as a NumPy array (H,W,3) in BGR order
        if isinstance(arr, np.ndarray):
            # Convert BGR -> RGB for Pillow
            rgb = arr[..., ::-1]
            img = Image.fromarray(rgb.astype('uint8'), 'RGB')
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            img.save(path)
            return True
        return False
    except Exception:
        return False

def imread(path):
    try:
        img = Image.open(path).convert('RGB')
        arr = np.array(img)
        # Convert RGB -> BGR for cv2 compatibility
        bgr = arr[..., ::-1]
        return bgr
    except Exception:
        return None

def cvtColor(arr, code):
    if arr is None:
        return None
    if code == COLOR_BGR2RGB:
        return arr[..., ::-1]
    # no-op for unknown codes
    return arr

def resize(arr, size):
    try:
        img = Image.fromarray(arr[..., ::-1])
        img = img.resize((size[0], size[1]))
        out = np.array(img)[..., ::-1]
        return out
    except Exception:
        return arr

def putText(img, text, org, fontFace, fontScale, color, thickness=1):
    # img is a NumPy array in BGR order
    try:
        rgb = img[..., ::-1]
        pil = Image.fromarray(rgb.astype('uint8'), 'RGB')
        draw = ImageDraw.Draw(pil)
        try:
            font = ImageFont.truetype("arial.ttf", int(16 * fontScale))
        except Exception:
            font = ImageFont.load_default()
        # PIL uses (x,y) - org is (x,y)
        draw.text(org, text, fill=tuple(int(c) for c in color[::-1]), font=font)
        out = np.array(pil)[..., ::-1]
        img[...] = out
        return img
    except Exception:
        raise

__all__ = [
    'imread', 'imwrite', 'resize', 'putText', 'cvtColor',
    'FONT_HERSHEY_SIMPLEX', 'COLOR_BGR2RGB'
]
