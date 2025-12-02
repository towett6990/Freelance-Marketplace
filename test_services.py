#!/usr/bin/env python3
"""Test script to check if services are being retrieved properly"""

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Service, User

def test_services():
    """Test service retrieval and display"""
    with app.app_context():
        try:
            # Check if tables exist
            print("Checking database tables...")
            print(f"Total services in database: {Service.query.count()}")
            
            # Get all services
            services = Service.query.all()
            print(f"Retrieved {len(services)} services:")
            
            for service in services:
                print(f"- ID: {service.id}")
                print(f"  Title: {service.title}")
                print(f"  User: {service.user_id}")
                print(f"  Images: {service.image_list}")
                print(f"  Videos: {service.video_list}")
                print(f"  All Media: {len(service.all_media)} items")
                print("---")
            
            # Check if there are any users
            print(f"Total users in database: {User.query.count()}")
            
            return True
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    test_services()