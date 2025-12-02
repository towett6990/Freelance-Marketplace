"""
Debug script to test OCR preprocessing and identify issues
"""

import sys
import os
sys.path.append('.')  # Add current directory to path

from ocr_preprocessing import enhanced_ocr_extract
import cv2
import pytesseract
from PIL import Image

def test_basic_ocr():
    """Test basic OCR without preprocessing to see if Tesseract works"""
    print("🔍 Testing Basic OCR...")
    print("=" * 50)
    
    # Check if we have sample ID images to test with
    test_images = []
    
    # Look for any ID images in the current directory
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                if 'id' in file.lower() or 'front' in file.lower() or 'back' in file.lower():
                    test_images.append(os.path.join(root, file))
    
    if not test_images:
        print("ℹ️  No ID images found for testing.")
        # Try to create a simple test image
        print("💡 Creating a simple test image...")
        
        # Create a simple test image with text
        import numpy as np
        img = np.ones((200, 400, 3), dtype=np.uint8) * 255
        cv2.putText(img, "TEST OCR", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
        cv2.putText(img, "KENYA ID", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)
        
        test_image_path = "test_ocr_image.jpg"
        cv2.imwrite(test_image_path, img)
        test_images = [test_image_path]
        print(f"✅ Created test image: {test_image_path}")
    
    for image_path in test_images[:1]:  # Test only first image
        print(f"\n🖼️  Testing image: {image_path}")
        print("-" * 30)
        
        try:
            # Test 1: Basic OCR without preprocessing
            print("1️⃣  Basic OCR (no preprocessing):")
            try:
                from PIL import Image
                pil_image = Image.open(image_path)
                basic_text = pytesseract.image_to_string(pil_image)
                print(f"   📝 Text: '{basic_text.strip()}'")
            except Exception as e:
                print(f"   ❌ Basic OCR failed: {str(e)}")
            
            # Test 2: Enhanced OCR with preprocessing
            print("\n2️⃣  Enhanced OCR (with preprocessing):")
            try:
                result = enhanced_ocr_extract(image_path)
                print(f"   📊 Success: {result['success']}")
                if result['success']:
                    print(f"   📝 Text: '{result['text']}'")
                    print(f"   🎯 Confidence: {result['confidence']:.1f}%")
                    print(f"   📊 Word count: {result['word_count']}")
                    print(f"   🔄 Rotation applied: {result['processing_details']['rotation_applied']}")
                    print(f"   🎨 Enhancements: {result['processing_details']['enhancements']}")
                else:
                    print(f"   ❌ Failed: {result['error']}")
            except Exception as e:
                print(f"   ❌ Enhanced OCR failed: {str(e)}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"❌ Error testing {image_path}: {str(e)}")
            import traceback
            traceback.print_exc()

def test_image_properties():
    """Test image properties to understand what we're working with"""
    print("\n🔍 Testing Image Properties...")
    print("=" * 50)
    
    # Look for any images
    image_files = [f for f in os.listdir('.') if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if not image_files:
        print("ℹ️  No images found in current directory")
        return
    
    for img_file in image_files[:2]:  # Test first 2 images
        print(f"\n📷 Image: {img_file}")
        try:
            img = cv2.imread(img_file)
            if img is not None:
                print(f"   📐 Dimensions: {img.shape[1]}x{img.shape[0]} (width x height)")
                print(f"   🎨 Channels: {img.shape[2] if len(img.shape) == 3 else 1}")
                print(f"   📊 Data type: {img.dtype}")
                
                # Calculate basic statistics
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                print(f"   💡 Mean brightness: {gray.mean():.1f}")
                print(f"   📈 Brightness range: {gray.min()}-{gray.max()}")
                
                # Edge detection test
                edges = cv2.Canny(gray, 50, 150)
                edge_count = np.sum(edges > 0)
                print(f"   🔍 Edge pixels: {edge_count} ({100*edge_count/edges.size:.1f}% of image)")
                
            else:
                print(f"   ❌ Could not load image")
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🔍 OCR Debugging Tool")
    print("=" * 50)
    
    test_image_properties()
    test_basic_ocr()
    
    print("\n" + "=" * 50)
    print("🔍 Debug complete!")
    print("=" * 50)