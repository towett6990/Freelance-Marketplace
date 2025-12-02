#!/usr/bin/env python3
"""
Final comprehensive fix for service image upload issues
"""
import os
import sys
from datetime import datetime
import uuid
from io import BytesIO
from PIL import Image
import json

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_and_fix_upload():
    """Test and fix the image upload system"""
    from app import app, db, User, Service, save_service_image, save_service_video, SERVICE_IMG_FOLDER, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_VIDEO_EXTENSIONS
    
    print("🔧 Comprehensive Upload System Test & Fix")
    print("=" * 50)
    
    # Test 1: Check directory permissions
    print("\n1️⃣ Checking directory structure...")
    os.makedirs(SERVICE_IMG_FOLDER, exist_ok=True)
    print(f"📁 Service image folder: {SERVICE_IMG_FOLDER}")
    print(f"✅ Directory exists: {os.path.exists(SERVICE_IMG_FOLDER)}")
    
    # Test 2: Test direct file save
    print("\n2️⃣ Testing direct file upload...")
    
    with app.app_context():
        # Create or get test user
        test_user = User.query.filter_by(email="uploadtest@example.com").first()
        if not test_user:
            test_user = User(
                username="uploadtest",
                email="uploadtest@example.com", 
                password="password123",
                role="seller",
                is_verified=True
            )
            db.session.add(test_user)
            db.session.commit()
            print("✅ Created test user")
        
        # Create test image
        img = Image.new('RGB', (300, 200), color='red')
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG', quality=85)
        img_buffer.seek(0)
        
        # Create mock file upload object
        class MockFileUpload:
            def __init__(self, buffer, filename):
                self.stream = buffer
                self.filename = filename
            
            def save(self, path):
                print(f"💾 Saving to: {path}")
                with open(path, 'wb') as f:
                    f.write(self.stream.getvalue())
                self.stream.seek(0)
                print(f"✅ File saved successfully")
        
        # Test image upload
        test_file = MockFileUpload(img_buffer, "test_upload.jpg")
        user_id = test_user.id
        
        try:
            saved_filename = save_service_image(test_file, user_id)
            print(f"🎉 Image upload function worked! Saved as: {saved_filename}")
            
            # Verify file exists
            file_path = os.path.join(SERVICE_IMG_FOLDER, saved_filename)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"✅ File verified: {file_path} ({size} bytes)")
                
                # Test Flask static URL
                with app.test_client() as client:
                    static_url = f"/static/uploads/services/{saved_filename}"
                    response = client.get(static_url)
                    print(f"🌐 Static URL test: {static_url}")
                    print(f"📊 Response: {response.status_code}")
                    
                    if response.status_code == 200:
                        print("🎉 Static file serving works!")
                    else:
                        print(f"❌ Static serving failed: {response.status_code}")
                        
                # Create test service
                test_service = Service(
                    user_id=test_user.id,
                    title="Test Upload Service",
                    description="Testing image upload functionality",
                    price=100.00,
                    currency="KES",
                    category="Test",
                    image_filenames=json.dumps([saved_filename])
                )
                
                db.session.add(test_service)
                db.session.commit()
                print(f"✅ Test service created: {test_service.id}")
                
            else:
                print(f"❌ File not found: {file_path}")
                
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            import traceback
            traceback.print_exc()

    # Test 3: Check Flask configuration
    print(f"\n3️⃣ Flask configuration check...")
    print(f"🔧 Max content length: {app.config.get('MAX_CONTENT_LENGTH')} bytes")
    print(f"🔧 Allowed image extensions: {ALLOWED_IMAGE_EXTENSIONS}")
    print(f"🔧 Allowed video extensions: {ALLOWED_VIDEO_EXTENSIONS}")

if __name__ == "__main__":
    test_and_fix_upload()