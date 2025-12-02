#!/usr/bin/env python3
"""
Simple test to check the image upload directories and basic functionality
"""
import os
from app import app, SERVICE_IMG_FOLDER, MAX_IMAGE_SIZE_MB

def test_directories():
    """Test the upload directories"""
    print("🧪 Testing Directory Structure...")
    print(f"📁 Service image folder: {SERVICE_IMG_FOLDER}")
    print(f"📁 Folder exists: {os.path.exists(SERVICE_IMG_FOLDER)}")
    print(f"📁 Folder permissions: {oct(os.stat(SERVICE_IMG_FOLDER).st_mode)[-3:]}")
    
    # List contents
    try:
        contents = os.listdir(SERVICE_IMG_FOLDER)
        print(f"📁 Contents: {contents}")
        if contents:
            for item in contents:
                item_path = os.path.join(SERVICE_IMG_FOLDER, item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    print(f"  📄 {item} ({size} bytes)")
    except Exception as e:
        print(f"❌ Error reading directory: {e}")

def test_flask_config():
    """Test Flask configuration"""
    print("\n🧪 Testing Flask Configuration...")
    print(f"🌐 Static folder: {app.static_folder}")
    print(f"🌐 Static URL path: {app.static_url_path}")
    print(f"🌐 Max content length: {app.config.get('MAX_CONTENT_LENGTH')} bytes")
    print(f"🌐 Max image size: {MAX_IMAGE_SIZE_MB}MB")

if __name__ == "__main__":
    test_directories()
    test_flask_config()