#!/usr/bin/env python3
"""Create test data for services"""

import sys
import os
import json
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Service, User
from werkzeug.security import generate_password_hash

def create_test_data():
    """Create test users and services"""
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            print("Database tables created.")
            
            # Create test user if doesn't exist
            test_user = User.query.filter_by(email="test@example.com").first()
            if not test_user:
                test_user = User(
                    username="testuser",
                    email="test@example.com",
                    password=generate_password_hash("password123"),
                    role="user"
                )
                db.session.add(test_user)
                db.session.commit()
                print("Test user created.")
            
            # Check if services exist
            if Service.query.count() == 0:
                print("Creating sample services...")
                
                # Create sample services with media
                services_data = [
                    {
                        "title": "Professional Web Design",
                        "description": "I will create a modern, responsive website for your business. Includes 5 pages, contact form, and mobile optimization.",
                        "price": 500.00,
                        "currency": "USD",
                        "quality": "New",
                        "category": "Web Development",
                        "images": ["sample_web_1.jpg", "sample_web_2.jpg", "sample_web_3.jpg"]
                    },
                    {
                        "title": "Logo Design Service",
                        "description": "Professional logo design with 3 concepts and unlimited revisions. High-resolution files included.",
                        "price": 150.00,
                        "currency": "USD",
                        "quality": "New",
                        "category": "Graphic Design",
                        "images": ["logo_sample_1.jpg", "logo_sample_2.jpg"]
                    },
                    {
                        "title": "Video Editing Services",
                        "description": "Professional video editing for social media, commercials, and promotional content. Fast delivery guaranteed.",
                        "price": 300.00,
                        "currency": "USD",
                        "quality": "New",
                        "category": "Video Editing",
                        "images": ["video_sample_1.jpg"],
                        "videos": ["demo_video_1.mp4"]
                    }
                ]
                
                for service_data in services_data:
                    service = Service(
                        user_id=test_user.id,
                        title=service_data["title"],
                        description=service_data["description"],
                        price=service_data["price"],
                        currency=service_data["currency"],
                        quality=service_data["quality"],
                        category=service_data["category"],
                        image_filenames=json.dumps(service_data.get("images", [])),
                        video_filenames=json.dumps(service_data.get("videos", []))
                    )
                    db.session.add(service)
                
                db.session.commit()
                print(f"Created {len(services_data)} sample services.")
            
            # Test service retrieval
            services = Service.query.all()
            print(f"Total services in database: {len(services)}")
            
            for service in services:
                print(f"Service ID: {service.id}")
                print(f"  Title: {service.title}")
                print(f"  Images: {service.image_list}")
                print(f"  Videos: {service.video_list}")
                print(f"  All Media: {len(service.all_media)} items")
                print("---")
            
            return True
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    create_test_data()