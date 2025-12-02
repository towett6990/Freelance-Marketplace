#!/usr/bin/env python3
"""
Comprehensive fix for service image display issues
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

def create_test_image_and_service():
    """Create a test service with a test image to verify the system works"""
    from app import app, db, User, Service, save_service_image, SERVICE_IMG_FOLDER
    
    print("🧪 Creating Test Service with Image...")
    
    with app.app_context():
        # Ensure database is created
        db.create_all()
        
        # Create or get test user
        test_user = User.query.filter_by(email="test@example.com").first()
        if not test_user:
            test_user = User(
                username="testuser",
                email="test@example.com", 
                password="password123",
                role="seller",
                is_verified=True
            )
            db.session.add(test_user)
            db.session.commit()
            print(f"✅ Created test user: {test_user.username}")
        
        # Create test image
        img = Image.new('RGB', (200, 150), color='red')
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG', quality=85)
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
        test_file = MockFileUpload(img_buffer, "test_service_image.jpg")
        
        try:
            # Save the image
            saved_filename = save_service_image(test_file, test_user.id)
            print(f"✅ Image saved: {saved_filename}")
            
            # Create test service
            test_service = Service(
                user_id=test_user.id,
                title="Test Service with Image",
                description="This is a test service to verify image display functionality",
                price=100.00,
                currency="KES",
                category="Test",
                quality="New",
                image_filenames=json.dumps([saved_filename])
            )
            
            db.session.add(test_service)
            db.session.commit()
            print(f"✅ Test service created: {test_service.id}")
            
            # Verify file exists
            file_path = os.path.join(SERVICE_IMG_FOLDER, saved_filename)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"✅ File verified: {file_path} ({size} bytes)")
                
                # Test static URL
                with app.test_client() as client:
                    static_url = f"/static/uploads/services/{saved_filename}"
                    response = client.get(static_url)
                    print(f"🌐 Static URL test: {static_url}")
                    print(f"📊 Response: {response.status_code}")
                    
                    if response.status_code == 200:
                        print("✅ Static file serving works!")
                    else:
                        print(f"❌ Static serving failed: {response.status_code}")
            else:
                print(f"❌ File not found: {file_path}")
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

def check_directory_permissions():
    """Check and fix directory permissions"""
    from app import SERVICE_IMG_FOLDER
    
    print("🔧 Checking Directory Permissions...")
    
    # Ensure the directory exists
    os.makedirs(SERVICE_IMG_FOLDER, exist_ok=True)
    print(f"📁 Service image folder: {SERVICE_IMG_FOLDER}")
    print(f"📁 Directory exists: {os.path.exists(SERVICE_IMG_FOLDER)}")
    
    # Check permissions
    try:
        perms = oct(os.stat(SERVICE_IMG_FOLDER).st_mode)[-3:]
        print(f"🔒 Current permissions: {perms}")
        
        # Make directory writable
        os.chmod(SERVICE_IMG_FOLDER, 0o755)
        print("✅ Permissions updated to 755")
        
    except Exception as e:
        print(f"⚠️  Permission check failed: {e}")

def list_existing_files():
    """List any existing files in the services directory"""
    from app import SERVICE_IMG_FOLDER
    
    print("📋 Checking Existing Files...")
    
    try:
        if os.path.exists(SERVICE_IMG_FOLDER):
            files = os.listdir(SERVICE_IMG_FOLDER)
            if files:
                print(f"📁 Found {len(files)} files:")
                for f in files:
                    fpath = os.path.join(SERVICE_IMG_FOLDER, f)
                    if os.path.isfile(fpath):
                        size = os.path.getsize(fpath)
                        print(f"  📄 {f} ({size} bytes)")
            else:
                print("📁 Directory is empty")
        else:
            print("❌ Service image directory doesn't exist")
            
    except Exception as e:
        print(f"❌ Error listing files: {e}")

if __name__ == "__main__":
    print("🔍 Service Image Display Debug Tool")
    print("=" * 50)
    
    check_directory_permissions()
    print()
    list_existing_files()
    print()
    create_test_image_and_service()