"""
Simple OCR test to verify Tesseract is working
"""

import sys
import os
sys.path.append('.')

import cv2
import numpy as np
import pytesseract
from PIL import Image

def create_test_image():
    """Create a simple test image with text"""
    # Create white background
    img = np.ones((100, 300, 3), dtype=np.uint8) * 255
    
    # Add black text
    cv2.putText(img, "TEST", (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(img, "OCR", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    # Save test image
    test_path = "simple_test.jpg"
    cv2.imwrite(test_path, img)
    return test_path

def test_basic_tesseract():
    """Test basic Tesseract functionality"""
    print("🔍 Testing Basic Tesseract OCR...")
    
    # Create test image
    test_image = create_test_image()
    print(f"✅ Created test image: {test_image}")
    
    try:
        # Test with PIL
        print("\n1️⃣  Testing with PIL Image:")
        pil_img = Image.open(test_image)
        text = pytesseract.image_to_string(pil_img)
        print(f"   📝 Extracted text: '{text.strip()}'")
        
        # Test with OpenCV
        print("\n2️⃣  Testing with OpenCV:")
        cv_img = cv2.imread(test_image)
        if cv_img is not None:
            pil_from_cv = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
            text_cv = pytesseract.image_to_string(pil_from_cv)
            print(f"   📝 Extracted text: '{text_cv.strip()}'")
        else:
            print("   ❌ Could not load image with OpenCV")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Clean up
    if os.path.exists(test_image):
        os.remove(test_image)
        print(f"\n🗑️  Cleaned up test image")

def test_enhanced_ocr():
    """Test the enhanced OCR function"""
    print("\n🔍 Testing Enhanced OCR...")
    
    try:
        from ocr_preprocessing import enhanced_ocr_extract
        
        # Create test image
        test_image = create_test_image()
        
        # Test enhanced OCR
        result = enhanced_ocr_extract(test_image)
        print(f"📊 Success: {result['success']}")
        
        if result['success']:
            print(f"📝 Text: '{result['text']}'")
            print(f"🎯 Confidence: {result['confidence']:.1f}%")
            print(f"📊 Word count: {result['word_count']}")
        else:
            print(f"❌ Error: {result['error']}")
            
        # Clean up
        if os.path.exists(test_image):
            os.remove(test_image)
            
    except Exception as e:
        print(f"❌ Error testing enhanced OCR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_basic_tesseract()
    test_enhanced_ocr()
    print("\n✅ Test complete!")