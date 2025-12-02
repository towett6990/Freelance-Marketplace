"""
Quick test of the simple OCR system
"""

import sys
import os
sys.path.append('.')

from simple_ocr import enhanced_ocr_extract, simple_ocr_extract
import cv2
import numpy as np

def test_simple_ocr():
    """Test the simple OCR system"""
    print("🔍 Testing Simple OCR System...")
    
    # Create a test image
    img = np.ones((120, 300, 3), dtype=np.uint8) * 255
    cv2.putText(img, "KENYA ID", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
    cv2.putText(img, "123456789", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    test_path = "ocr_test.jpg"
    cv2.imwrite(test_path, img)
    
    try:
        # Test simple OCR directly
        print("\n1️⃣  Testing Simple OCR:")
        result = simple_ocr_extract(test_path)
        print(f"   📊 Success: {result['success']}")
        if result['success']:
            print(f"   📝 Text: '{result['text']}'")
            print(f"   🎯 Confidence: {result['confidence']:.1f}%")
            print(f"   📊 Word count: {result['word_count']}")
            print(f"   🎨 Enhancements: {result['processing_details']['enhancements']}")
        else:
            print(f"   ❌ Error: {result['error']}")
        
        # Test wrapper function
        print("\n2️⃣  Testing Wrapper Function:")
        wrapper_result = enhanced_ocr_extract(test_path)
        print(f"   📊 Success: {wrapper_result['success']}")
        if wrapper_result['success']:
            print(f"   📝 Text: '{wrapper_result['text']}'")
            print(f"   🎯 Confidence: {wrapper_result['confidence']:.1f}%")
        else:
            print(f"   ❌ Error: {wrapper_result['error']}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    if os.path.exists(test_path):
        os.remove(test_path)
        print(f"\n🗑️  Cleaned up test image")
    
    print("\n✅ Simple OCR test complete!")

if __name__ == "__main__":
    test_simple_ocr()