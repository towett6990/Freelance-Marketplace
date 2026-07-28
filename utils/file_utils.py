"""
File handling utilities for Freelance Marketplace
"""

import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import cv2
import numpy as np
from config import (
    ALLOWED_IMAGE_EXTENSIONS, ALLOWED_VIDEO_EXTENSIONS,
    MAX_IMAGE_SIZE_MB, MAX_VIDEO_SIZE_MB, SERVICE_IMG_FOLDER
)


def allowed_file(filename, allowed=None):
    """Check if file extension is allowed"""
    if allowed is None:
        allowed = ALLOWED_IMAGE_EXTENSIONS
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def allowed_id_file(filename):
    """Check if ID file extension is allowed"""
    from config import ALLOWED_ID_EXT
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_ID_EXT


def allowed_avatar_file(filename):
    """Check if avatar file extension is allowed"""
    from config import ALLOWED_AVATAR_EXT
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXT


def save_service_image(file_storage, user_id, max_width=1600):
    """
    Validates and saves an uploaded image.
    Returns filename (relative to static/uploads/services).
    Converts and resizes large images to JPEG (keeps png/webp if originally png/webp).
    """
    try:
        filename = secure_filename(file_storage.filename)
        ext = filename.rsplit(".", 1)[-1].lower()

        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image file type: {ext}")

        # size check
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)

        if size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Image file too large (max {MAX_IMAGE_SIZE_MB}MB)")

        # create unique name
        base = f"{user_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex}"
        out_ext = ext if ext in ("png","webp","gif") else "jpg"
        out_name = f"{base}.{out_ext}"
        out_path = os.path.join(SERVICE_IMG_FOLDER, out_name)

        # Process image
        try:
            file_storage.stream.seek(0)
            img = Image.open(file_storage.stream).convert("RGB")
        except Exception as e:
            raise ValueError(f"Invalid image: {e}")

        # resize if large
        w,h = img.size
        if w > max_width:
            new_h = int(max_width * h / w)
            img = img.resize((max_width, new_h), Image.LANCZOS)

        # save with reasonable quality
        if out_ext == "jpg":
            img.save(out_path, "JPEG", quality=82, optimize=True)
        else:
            img.save(out_path, out_ext.upper())

        return out_name

    except Exception as e:
        raise


def save_service_video(file_storage, user_id):
    """
    Validates and saves an uploaded video.
    Returns filename (relative to static/uploads/services).
    """
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Unsupported video file type")

    # size check
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Video file too large (max {MAX_VIDEO_SIZE_MB}MB)")

    # create unique name
    base = f"{user_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex}"
    ext = filename.rsplit(".",1)[-1].lower()
    out_name = f"{base}.{ext}"
    out_path = os.path.join(SERVICE_IMG_FOLDER, out_name)
    # save video file
    file_storage.save(out_path)
    return out_name


def preprocess_image(image_path):
    """Preprocess image for OCR"""
    img = Image.open(image_path)
    img = img.convert("L")  # grayscale
    from PIL import ImageFilter, ImageOps
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    return img