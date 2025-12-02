#!/usr/bin/env python3
"""
Test script to verify image upload and display functionality
"""
import os
import sys
from datetime import datetime
import uuid
from io import BytesIO
from PIL import Image

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Service, save_service_image, SERVICE_IMG_FOLDER

def create_test_user():
    """Create a test user"""
    # Create test user (assumes caller has app.app_context())
    # Remove any previous test user with the same email to avoid UNIQUE conflicts
    existing = User.query.filter_by(email="test@example.com").first()
    if existing:
        try:
            db.session.delete(existing)
            db.session.commit()
        except Exception:
            db.session.rollback()
    user = User(
        username="testuser",
        email="test@example.com",
        password="password123",
        role="seller",
        is_verified=True
    )
    db.session.add(user)
    db.session.commit()
    return user

def create_test_image():
    """Create a simple test image"""
    # Create a simple 100x100 red image
    img = Image.new('RGB', (100, 100), color='red')
    img_buffer = BytesIO()
    img.save(img_buffer, format='JPEG')
    img_buffer.seek(0)
    return img_buffer

def test_image_upload():
    """Test the image upload functionality"""
    print("🧪 Testing Image Upload Functionality...")
    
    with app.app_context():
        # Create test user
        user = create_test_user()
        print(f"✅ Created test user: {user.username} (ID: {user.id})")
        
        # Test image creation
        img_buffer = create_test_image()
        print("✅ Created test image")
        
        # Simulate file upload object
        class MockFileUpload:
            def __init__(self, buffer, filename):
                self.stream = buffer
                self.filename = filename
            
            def save(self, path):
                with open(path, 'wb') as f:
                    f.write(self.stream.getvalue())
                # Reset buffer position
                self.stream.seek(0)
        
        # Test image upload
        test_file = MockFileUpload(img_buffer, "test_image.jpg")
        
        try:
            saved_filename = save_service_image(test_file, user.id)
            print(f"✅ Image saved successfully: {saved_filename}")
            
            # Check if file exists
            file_path = os.path.join(SERVICE_IMG_FOLDER, saved_filename)
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"✅ File exists at: {file_path}")
                print(f"📁 File size: {file_size} bytes")
                
                # Check Flask static URL
                with app.test_client() as client:
                    static_url = f"/static/uploads/services/{saved_filename}"
                    response = client.get(static_url)
                    print(f"🌐 Static URL test: {static_url}")
                    print(f"📊 Response status: {response.status_code}")
                    if response.status_code == 200:
                        print("✅ Static file serving works!")
                    else:
                        print("❌ Static file serving failed!")
            else:
                print(f"❌ File not found at: {file_path}")
                
        except Exception as e:
            print(f"❌ Image upload failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_image_upload()