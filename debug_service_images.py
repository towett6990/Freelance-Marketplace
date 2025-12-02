#!/usr/bin/env python3
"""
Debug script to check what's happening with service image uploads
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

from app import app, db, User, Service, save_service_image, save_service_video, SERVICE_IMG_FOLDER

def check_service_records():
    """Check existing service records and their image data"""
    print("🔍 Checking Service Records...")
    
    with app.app_context():
        services = Service.query.all()
        
        if not services:
            print("❌ No services found in database")
            return
        
        for service in services:
            print(f"\n📋 Service ID: {service.id}")
            print(f"📝 Title: {service.title}")
            print(f"💰 Price: {service.price}")
            print(f"📁 Image filenames: {service.image_filenames}")
            print(f"🎬 Video filenames: {service.video_filenames}")
            
            # Parse JSON if it exists
            if service.image_filenames:
                try:
                    images = json.loads(service.image_filenames)
                    print(f"🖼️  Parsed images: {images}")
                    
                    for img in images:
                        img_path = os.path.join(SERVICE_IMG_FOLDER, img)
                        if os.path.exists(img_path):
                            size = os.path.getsize(img_path)
                            print(f"   ✅ {img} exists ({size} bytes)")
                        else:
                            print(f"   ❌ {img} missing from {img_path}")
                except json.JSONDecodeError as e:
                    print(f"   ⚠️  JSON parse error: {e}")
            
            if service.video_filenames:
                try:
                    videos = json.loads(service.video_filenames)
                    print(f"🎥 Parsed videos: {videos}")
                except json.JSONDecodeError as e:
                    print(f"   ⚠️  JSON parse error: {e}")

def test_file_upload():
    """Test the file upload functions directly"""
    print("\n🧪 Testing File Upload Functions...")
    
    with app.app_context():
        # Create a test image
        img = Image.new('RGB', (100, 100), color='blue')
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        
        class MockFileUpload:
            def __init__(self, buffer, filename):
                self.stream = buffer
                self.filename = filename
            
            def save(self, path):
                with open(path, 'wb') as f:
                    f.write(self.stream.getvalue())
                self.stream.seek(0)
        
        # Test image upload
        test_file = MockFileUpload(img_buffer, "debug_test.jpg")
        user_id = 1  # Assume first user
        
        try:
            saved_filename = save_service_image(test_file, user_id)
            print(f"✅ Image saved: {saved_filename}")
            
            # Check if file exists
            file_path = os.path.join(SERVICE_IMG_FOLDER, saved_filename)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"✅ File exists: {file_path} ({size} bytes)")
                
                # Test Flask static URL
                with app.test_client() as client:
                    static_url = f"/static/uploads/services/{saved_filename}"
                    response = client.get(static_url)
                    print(f"🌐 Static URL: {static_url}")
                    print(f"📊 Response: {response.status_code}")
                    
                    if response.status_code == 200:
                        print("✅ Static serving works!")
                    else:
                        print(f"❌ Static serving failed: {response.status_code}")
                        
            else:
                print(f"❌ File not found: {file_path}")
                
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    check_service_records()
    test_file_upload()