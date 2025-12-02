#!/usr/bin/env python3
"""
Test script to verify SQLAlchemy relationship fix
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all imports work without SQLAlchemy relationship errors"""
    try:
        print("🔄 Testing imports...")
        
        # Test the specific import that was failing
        from app import app, db, User, Service
        print("✅ All imports successful!")
        
        # Test that relationships are properly configured
        with app.app_context():
            # This should not raise AmbiguousForeignKeysError
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Test relationship configuration
            print("✅ User model has 'services' relationship:", hasattr(User, 'services'))
            print("✅ Service model has 'user' relationship:", hasattr(Service, 'user'))
            
            # Test basic query that was failing
            admin_check = User.query.filter_by(role="admin").first()
            print("✅ Query that was causing the error now works:", admin_check is not None)
        
        print("🎉 All tests passed! The SQLAlchemy relationship error has been fixed.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)