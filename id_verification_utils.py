# id_verification_utils.py
import re
import io
import os
from PIL import Image, ImageFilter, ImageStat
import pytesseract
import face_recognition
import imagehash
import cv2
import numpy as np
import face_recognition


def ocr_text_from_image(path):
    """Extract clean text from image using Tesseract."""
    try:
        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        # Normalize and clean the text a bit
        cleaned = (
            text.replace("\n", " ")
                .replace("\x0c", "")
                .strip()
        )
        return cleaned
    except Exception as e:
        return f"[OCR ERROR] {e}"


def extract_id_fields(text):
    """
    Very simple parsing: returns a dict with candidate name, id_number, dob.
    You should adapt regex to the ID formats you expect.
    """
    text = text.replace('\n', ' ')
    # candidate ID number (7-12 digits, tweak per country)
    id_match = re.search(r'\b(\d{6,12})\b', text)
    dob_match = re.search(r'(\b\d{2}[\/\-]\d{2}[\/\-]\d{2,4}\b)', text)  # naive
    # candidate name heuristic: look for "name" or uppercase words — crude
    name_match = re.search(r'(?:name[:\s]*)([A-Z][A-Za-z ,.\'-]{2,60})', text, re.IGNORECASE)
    return {
        "raw_text": text,
        "id_number": id_match.group(1) if id_match else None,
        "dob": dob_match.group(1) if dob_match else None,
        "name": name_match.group(1).strip() if name_match else None
    }

def face_match_score(id_image_path, selfie_path):
    """
    Returns a float 0.0-1.0 representing face similarity.
    Uses face_recognition library (dlib). If faces not found, returns None.
    """
    try:
        id_img = face_recognition.load_image_file(id_image_path)
        selfie_img = face_recognition.load_image_file(selfie_path)

        # Try to detect faces
        id_faces = face_recognition.face_encodings(id_img)
        selfie_faces = face_recognition.face_encodings(selfie_img)

        if not id_faces or not selfie_faces:
            return None  # can't compare

        # Compare first face found in each
        id_enc = id_faces[0]
        selfie_enc = selfie_faces[0]
        dist = np.linalg.norm(id_enc - selfie_enc)
        # Convert distance to score: typical threshold ~0.6 for same person
        # Map distance 0.3 -> 1.0, 0.6 -> 0.7, 0.9 -> 0.0 roughly
        score = max(0.0, min(1.0, 1.5 - dist*1.5))  # crude mapping
        return float(score)
    except Exception:
        return None

def image_tamper_score(path):
    """
    Simple heuristics:
      - Check EXIF presence (scanned/edited images may lack EXIF)
      - Check JPEG noise / high-frequency content variance
      - Compute imagehash and compare to a blurred version (if very different, suspicious)
    Returns 0.0-1.0 where higher = more likely genuine (not tampered).
    """
    try:
        img = Image.open(path)
        # EXIF presence helps but is not decisive
        exif = getattr(img, "_getexif", None)
        has_exif = bool(exif and exif())

        # Edge/noise analysis: variance of Laplacian in OpenCV
        arr = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2GRAY)
        lap = cv2.Laplacian(arr, cv2.CV_64F)
        var = lap.var()

        # Imagehash comparison to blurred version
        h1 = imagehash.phash(img)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=2))
        h2 = imagehash.phash(blurred)
        hash_diff = abs(h1 - h2)

        # Heuristic scoring
        score = 0.5
        if has_exif:
            score += 0.15
        # high variance suggests a photograph rather than a flat edit (tweak thresholds)
        if var > 100.0:
            score += 0.2
        # small hash diff means image consistent (good)
        if hash_diff < 6:
            score += 0.15

        return max(0.0, min(1.0, score))
    except Exception:
        return 0.4

def validate_id_number_format(id_number):
    """
    Basic numeric length check — replace with country-specific checks if available.
    Returns True/False.
    """
    if not id_number:
        return False
    return bool(re.match(r'^\d{6,12}$', id_number))


def is_valid_national_id_content(text):
    """
    Enhanced validation specifically for Kenyan National ID content
    Returns a tuple (is_valid, score, reasons)
    """
    if not text or len(text.strip()) < 10:
        return False, 0.0, ["Insufficient text content detected"]
    
    text_lower = text.lower()
    text_upper = text.upper()
    
    # Strong positive indicators for Kenyan National ID
    strong_indicators = [
        "republic of kenya",
        "national id",
        "national identification",
        "identity card",
        "republickenya",  # Sometimes printed as one word
        "identity card",
        "id no", "id no.", "id number",
        "national id no"
    ]
    
    # Weaker indicators that could appear on any document
    weak_indicators = [
        "name", "date of birth", "gender", "sex", "male", "female",
        "nationality", "country", "document", "card"
    ]
    
    # Check for strong indicators
    strong_matches = sum(1 for indicator in strong_indicators if indicator in text_lower)
    weak_matches = sum(1 for indicator in weak_indicators if indicator in text_lower)
    
    # Check for ID number patterns (Kenyan IDs are 8-9 digits)
    id_number_matches = len(re.findall(r'\b\d{8,9}\b', text))
    
    # Check for name patterns (usually in uppercase on real IDs)
    uppercase_name_pattern = len(re.findall(r'\b[A-Z]{3,30}\b', text))
    
    # Score calculation
    score = 0.0
    reasons = []
    
    if strong_matches >= 2:
        score += 0.4
        reasons.append(f"Found {strong_matches} strong ID indicators")
    elif strong_matches == 1:
        score += 0.2
        reasons.append(f"Found 1 strong ID indicator")
    
    if id_number_matches >= 1:
        score += 0.3
        reasons.append(f"Found {id_number_matches} valid ID number(s)")
    
    if uppercase_name_pattern >= 2:
        score += 0.2
        reasons.append(f"Found {uppercase_name_pattern} name-like patterns")
    
    # Penalty for too many weak indicators without strong ones
    if weak_matches > strong_matches * 2:
        score -= 0.2
        reasons.append("Too many generic terms without strong ID indicators")
    
    # Check for common non-ID content that should be rejected
    rejection_patterns = [
        "shopping", "restaurant", "food", "menu", "price", "contact us",
        "website", "email", "phone", "address", "thank you", "welcome",
        "login", "password", "username", "www.", ".com", "https://"
    ]
    
    rejection_matches = sum(1 for pattern in rejection_patterns if pattern in text_lower)
    if rejection_matches >= 2:
        score -= 0.5
        reasons.append("Contains typical non-document content")
    
    return score >= 0.5, max(0.0, min(1.0, score)), reasons


def check_document_dimensions_and_quality(image_path):
    """
    Check if image has dimensions and quality typical of ID documents
    Returns a score from 0.0 to 1.0
    """
    try:
        img = Image.open(image_path)
        width, height = img.size
        
        # Typical ID document dimensions ratio (similar to credit card)
        id_ratio = 1.586  # 85.6mm x 53.98mm (ISO/IEC 7810 ID-1)
        actual_ratio = width / height if height > 0 else 0
        
        # Score based on aspect ratio closeness to ID document
        ratio_score = max(0.0, 1.0 - abs(actual_ratio - id_ratio) / id_ratio)
        
        # Check if dimensions are reasonable for an ID document
        if width < 300 or height < 200:
            dimensions_score = 0.2  # Too small
        elif width > 2000 or height > 1500:
            dimensions_score = 0.3  # Too large (likely not an ID)
        else:
            dimensions_score = 0.8  # Reasonable size
        
        # Check image format and quality
        format_score = 0.0
        if img.format in ['JPEG', 'PNG']:
            if img.format == 'JPEG':
                # Check JPEG quality by analyzing compression artifacts
                format_score = 0.7
            else:
                format_score = 0.9
        
        # Combine scores
        final_score = (ratio_score * 0.3 + dimensions_score * 0.4 + format_score * 0.3)
        
        return min(1.0, final_score)
        
    except Exception as e:
        return 0.3  # Default low score if analysis fails


def validate_id_document_integrity(image_path):
    """
    Comprehensive document integrity check
    Returns detailed integrity analysis
    """
    try:
        img = Image.open(image_path)
        
        # Basic image validation
        if img.format not in ['JPEG', 'PNG']:
            return {
                'is_valid': False,
                'score': 0.0,
                'issues': ['Invalid image format']
            }
        
        # Check image dimensions
        width, height = img.size
        if width < 200 or height < 150:
            return {
                'is_valid': False,
                'score': 0.0,
                'issues': ['Image too small to be a valid document']
            }
        
        if width > 3000 or height > 2000:
            return {
                'is_valid': False,
                'score': 0.0,
                'issues': ['Image too large, likely not a document scan']
            }
        
        # Check for signs of tampering or editing
        issues = []
        base_score = 0.8
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Check for excessive noise (could indicate photo of screen or poor scan)
        img_array = np.array(img)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var < 50:
            issues.append("Image too blurry for reliable text recognition")
            base_score -= 0.3
        elif laplacian_var > 500:
            issues.append("Image appears artificially enhanced")
            base_score -= 0.2
        
        # Check for screen reflection patterns (common in photos of screens)
        # This is a simplified check for regular patterns that might indicate screen capture
        
        # Simple edge detection
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
        
        if edge_density < 0.05:
            issues.append("Image has very few edges, may be a flat image")
            base_score -= 0.2
        elif edge_density > 0.3:
            issues.append("Image has excessive edges, may be digitally created")
            base_score -= 0.1
        
        final_score = max(0.0, min(1.0, base_score))
        
        return {
            'is_valid': len(issues) == 0 or final_score > 0.5,
            'score': final_score,
            'issues': issues,
            'laplacian_variance': laplacian_var,
            'edge_density': edge_density
        }
        
    except Exception as e:
        return {
            'is_valid': False,
            'score': 0.0,
            'issues': [f'Image analysis failed: {str(e)}']
        }
