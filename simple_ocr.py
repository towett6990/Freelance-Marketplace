"""
Simple, reliable OCR preprocessing for ID documents
This is a fallback that should work immediately
"""

import cv2
import pytesseract
from PIL import Image
import numpy as np
from typing import Dict

def simple_ocr_extract(image_path: str) -> Dict:
    """
    Simple, reliable OCR extraction for ID documents
    Uses proven preprocessing techniques
    """
    try:
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            return {"success": False, "error": "Could not load image", "text": "", "confidence": 0.0}
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive thresholding (better than fixed threshold for varying lighting)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Convert to PIL Image for Tesseract
        pil_image = Image.fromarray(thresh)
        
        # Extract text
        text = pytesseract.image_to_string(pil_image)
        
        # Get confidence data
        data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
        
        # Calculate average confidence (excluding -1 values)
        confidences = [int(conf) for conf in data["conf"] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Count words
        words = [word for word in text.split() if word.strip()]
        word_count = len(words)
        
        return {
            "success": True,
            "text": text.strip(),
            "confidence": round(avg_confidence, 2),
            "word_count": word_count,
            "processing_details": {
                "rotation_applied": False,
                "enhancements": ["gaussian_blur", "adaptive_threshold"],
                "processing_steps": ["Noise reduction", "Adaptive thresholding"]
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"OCR extraction failed: {str(e)}",
            "text": "",
            "confidence": 0.0,
            "processing_details": {}
        }

def enhanced_ocr_extract(image_path: str, **options) -> Dict:
    """
    Wrapper that tries enhanced OCR first, falls back to simple OCR
    """
    try:
        # Try the enhanced OCR first
        from ocr_preprocessing import enhanced_ocr_extract as enhanced_func
        
        result = enhanced_func(image_path, **options)
        
        # If enhanced OCR fails or returns empty text, use simple OCR
        if not result["success"] or len(result["text"].strip()) < 3:
            print(f"⚠️  Enhanced OCR failed or returned little text, using simple OCR fallback")
            result = simple_ocr_extract(image_path)
            
        return result
        
    except Exception:
        # If enhanced OCR is not available, use simple OCR
        print("⚠️  Enhanced OCR not available, using simple OCR fallback")
        return simple_ocr_extract(image_path)