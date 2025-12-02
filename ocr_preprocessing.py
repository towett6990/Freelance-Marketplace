"""
Enhanced OCR Preprocessing System
Handles rotation correction, lighting improvement, and noise reduction for ID document OCR
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance
import os
from typing import Dict, Tuple, Optional, List
import math

class OCRPreprocessor:
    """Advanced OCR preprocessing for ID document text extraction"""
    
    def __init__(self):
        # Tesseract configuration for better ID document recognition
        self.tesseract_config = '--oem 3 --psm 6'
    
    def detect_image_orientation(self, image: np.ndarray) -> Tuple[float, float]:
        """
        Detect image orientation using edge detection and Hough lines
        Returns (rotation_angle, confidence)
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect edges
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Detect lines using Hough transform
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is None:
                # Try Tesseract's orientation detection
                return self._detect_orientation_tesseract(image)
            
            # Calculate angle histogram
            angles = []
            for rho, theta in lines[:50]:  # Use first 50 lines
                angle = (theta * 180 / np.pi) - 90  # Convert to degrees
                angles.append(angle)
            
            # Find most common angle
            if angles:
                # Group similar angles
                angle_clusters = self._cluster_angles(angles)
                main_angle = max(angle_clusters, key=angle_clusters.get)
                confidence = min(1.0, len(angle_clusters[main_angle]) / len(angles))
                return main_angle, confidence
            
            return 0.0, 0.0
            
        except Exception:
            return self._detect_orientation_tesseract(image)
    
    def _detect_orientation_tesseract(self, image: np.ndarray) -> Tuple[float, float]:
        """Fallback orientation detection using Tesseract"""
        try:
            # Save temporary image for Tesseract analysis
            temp_path = "temp_orientation.jpg"
            cv2.imwrite(temp_path, image)
            
            # Use Tesseract to detect orientation
            osd = pytesseract.image_to_osd(Image.open(temp_path))
            osd_clean = [line for line in osd.split('\n') if 'Rotate:' in line]
            
            if osd_clean:
                angle = float(osd_clean[0].split(':')[1].strip())
                return angle, 0.8
            
            # Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        except Exception:
            pass
        
        return 0.0, 0.0
    
    def _cluster_angles(self, angles: List[float], tolerance: float = 5.0) -> Dict[float, List[float]]:
        """Group similar angles together"""
        clusters = {}
        for angle in angles:
            # Normalize angle to -90 to 90 range
            while angle > 90:
                angle -= 180
            while angle < -90:
                angle += 180
            
            # Find existing cluster or create new one
            found_cluster = False
            for cluster_angle in clusters:
                if abs(angle - cluster_angle) <= tolerance:
                    clusters[cluster_angle].append(angle)
                    found_cluster = True
                    break
            
            if not found_cluster:
                clusters[angle] = [angle]
        
        return clusters
    
    def correct_rotation(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Correct image rotation by specified angle"""
        if abs(angle) < 1.0:  # Small angles don't need correction
            return image
        
        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        
        # Get rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Calculate new image dimensions
        cos_val = np.abs(rotation_matrix[0, 0])
        sin_val = np.abs(rotation_matrix[0, 1])
        new_width = int((height * sin_val) + (width * cos_val))
        new_height = int((height * cos_val) + (width * sin_val))
        
        # Adjust rotation matrix to new center
        rotation_matrix[0, 2] += (new_width / 2) - center[0]
        rotation_matrix[1, 2] += (new_height / 2) - center[1]
        
        # Apply rotation
        corrected = cv2.warpAffine(image, rotation_matrix, (new_width, new_height), 
                                  flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, 
                                  borderValue=(255, 255, 255))
        
        return corrected
    
    def enhance_contrast_and_brightness(self, image: np.ndarray, alpha: float = 1.3, beta: int = 20) -> np.ndarray:
        """Enhance contrast and brightness using alpha-beta correction"""
        return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    
    def apply_clahe(self, image: np.ndarray, clip_limit: float = 3.0, tile_grid_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
        """Apply Contrast Limited Adaptive Histogram Equalization"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Create CLAHE object
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        
        # Apply CLAHE
        enhanced = clahe.apply(gray)
        
        # Convert back to BGR if original was color
        if len(image.shape) == 3:
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        
        return enhanced
    
    def denoise_image(self, image: np.ndarray, h: float = 10.0, template_window_size: int = 7,
                     search_window_size: int = 21) -> np.ndarray:
        """Apply Non-local Means Denoising"""
        if len(image.shape) == 3:
            return cv2.fastNlMeansDenoisingColored(image, None, h, h, template_window_size, search_window_size)
        else:
            return cv2.fastNlMeansDenoising(image, None, h, template_window_size, search_window_size)
    
    def preprocess_for_ocr(self, image_path: str, auto_rotate: bool = True, enhance_lighting: bool = True, 
                          denoise: bool = True) -> Dict:
        """
        Complete OCR preprocessing pipeline
        
        Args:
            image_path: Path to input image
            auto_rotate: Whether to automatically detect and correct rotation
            enhance_lighting: Whether to apply lighting enhancement
            denoise: Whether to apply denoising
            
        Returns:
            Dict with processed image and metadata
        """
        try:
            # Load image
            original = cv2.imread(image_path)
            if original is None:
                return {"success": False, "error": "Could not load image"}
            
            processed = original.copy()
            metadata = {
                "original_dimensions": (original.shape[1], original.shape[0]),
                "rotation_corrected": False,
                "enhancements_applied": [],
                "processing_steps": []
            }
            
            # Step 1: Auto-rotation detection and correction
            if auto_rotate:
                angle, confidence = self.detect_image_orientation(processed)
                if abs(angle) > 2.0 and confidence > 0.5:  # Significant rotation detected
                    processed = self.correct_rotation(processed, -angle)  # Negative for clockwise correction
                    metadata["rotation_corrected"] = True
                    metadata["rotation_angle"] = round(angle, 2)
                    metadata["rotation_confidence"] = round(confidence, 2)
                    metadata["processing_steps"].append(f"Rotation corrected: {angle:.1f}°")
            
            # Step 2: Denoising
            if denoise:
                processed = self.denoise_image(processed)
                metadata["enhancements_applied"].append("denoising")
                metadata["processing_steps"].append("Noise reduction applied")
            
            # Step 3: Lighting enhancement
            if enhance_lighting:
                # Convert to grayscale for analysis
                gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
                mean_brightness = gray.mean()
                
                # Apply CLAHE for contrast enhancement
                processed = self.apply_clahe(processed)
                metadata["enhancements_applied"].append("clahe_contrast")
                metadata["processing_steps"].append("Contrast enhancement (CLAHE) applied")
                
                # Apply alpha-beta correction for brightness
                if mean_brightness < 120:  # Dark image
                    processed = self.enhance_contrast_and_brightness(processed, alpha=1.2, beta=15)
                    metadata["enhancements_applied"].append("brightness_boost")
                    metadata["processing_steps"].append("Brightness increased")
                elif mean_brightness > 180:  # Bright image
                    processed = self.enhance_contrast_and_brightness(processed, alpha=1.1, beta=-10)
                    metadata["enhancements_applied"].append("brightness_reduction")
                    metadata["processing_steps"].append("Brightness decreased")
            
            # Step 4: Final sharpening (optional)
            if enhance_lighting:
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                processed = cv2.filter2D(processed, -1, kernel)
                metadata["enhancements_applied"].append("sharpening")
                metadata["processing_steps"].append("Image sharpening applied")
            
            metadata["final_dimensions"] = (processed.shape[1], processed.shape[0])
            metadata["success"] = True
            
            return {
                "success": True,
                "processed_image": processed,
                "metadata": metadata
            }
            
        except Exception as e:
            return {"success": False, "error": f"Preprocessing failed: {str(e)}"}
    
    def extract_text_with_ocr(self, image_path: str, preprocessing_options: Dict = None) -> Dict:
        """
        Extract text using enhanced OCR preprocessing
        
        Args:
            image_path: Path to input image
            preprocessing_options: Dict with preprocessing options
            
        Returns:
            Dict with extracted text and confidence scores
        """
        if preprocessing_options is None:
            preprocessing_options = {
                "auto_rotate": True,
                "enhance_lighting": True,
                "denoise": True
            }
        
        try:
            # Preprocess image
            preprocess_result = self.preprocess_for_ocr(image_path, **preprocessing_options)
            
            if not preprocess_result["success"]:
                return {
                    "success": False,
                    "error": preprocess_result["error"],
                    "text": "",
                    "confidence": 0.0,
                    "metadata": {}
                }
            
            processed_image = preprocess_result["processed_image"]
            metadata = preprocess_result["metadata"]
            
            # Convert to PIL Image for Tesseract
            processed_rgb = cv2.cvtColor(processed_image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(processed_rgb)
            
            # Extract text with confidence data
            data = pytesseract.image_to_data(pil_image, config=self.tesseract_config, output_type=pytesseract.Output.DICT)
            
            # Filter high confidence text (lowered threshold for ID documents)
            text_lines = []
            confidences = []
            
            for i in range(len(data["text"])):
                conf = data["conf"][i]
                if conf != -1:  # Include all non-ignored text
                    text = data["text"][i].strip()
                    if text:
                        text_lines.append(text)
                        confidences.append(int(conf))
            
            extracted_text = " ".join(text_lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                "success": True,
                "text": extracted_text,
                "confidence": round(avg_confidence, 2),
                "word_count": len(text_lines),
                "metadata": metadata,
                "processing_details": {
                    "rotation_applied": metadata.get("rotation_corrected", False),
                    "enhancements": metadata.get("enhancements_applied", []),
                    "processing_steps": metadata.get("processing_steps", [])
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"OCR extraction failed: {str(e)}",
                "text": "",
                "confidence": 0.0,
                "metadata": {}
            }

# Global preprocessor instance
ocr_preprocessor = OCRPreprocessor()

def enhanced_ocr_extract(image_path: str, **options) -> Dict:
    """
    Convenience function for enhanced OCR extraction
    """
    return ocr_preprocessor.extract_text_with_ocr(image_path, options or None)

# Predefined optimization profiles for different document types
OCR_PROFILES = {
    "id_document": {
        "auto_rotate": True,
        "enhance_lighting": True,
        "denoise": True
    },
    "low_quality": {
        "auto_rotate": True,
        "enhance_lighting": True,
        "denoise": True,
        "alpha": 1.4,
        "beta": 25
    },
    "dark_document": {
        "auto_rotate": True,
        "enhance_lighting": True,
        "denoise": True
    }
}