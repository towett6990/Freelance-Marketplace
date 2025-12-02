#!/usr/bin/env python3
"""Initialize the marketplace with sample data"""

import sys
import os
import json
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Service, User
from werkzeug.security import generate_password_hash

def init_marketplace():
    """Initialize the marketplace with test data"""
    with app.app_context():
        try:
            print("🗃️ Creating database tables...")
            db.create_all()
            
            # Create a test user
            test_user = User.query.filter_by(email="demo@example.com").first()
            if not test_user:
                test_user = User(
                    username="demo_freelancer",
                    email="demo@example.com", 
                    password=generate_password_hash("demo123"),
                    role="user"
                )
                db.session.add(test_user)
                db.session.commit()
                print("👤 Created demo user")
            
            # Check if we already have services
            if Service.query.count() == 0:
                print("📝 Creating sample services...")
                
                # Create sample services that showcase the new features
                services = [
                    {
                        "title": "Professional Logo Design",
                        "description": "I will design a unique, professional logo for your business. Includes 3 concepts, unlimited revisions, and all file formats (AI, EPS, PNG, JPG). Perfect for branding and marketing.",
                        "price": 150.00,
                        "currency": "USD",
                        "quality": "New",
                        "category": "Graphic Design",
                        "images": ["logo_portfolio_1.png", "logo_portfolio_2.png", "logo_portfolio_3.png"]
                    },
                    {
                        "title": "Custom Web Development",
                        "description": "I will build a modern, responsive website for your business. Includes 5 pages, contact form, SEO optimization, and mobile-friendly design. Built with latest technologies.",
                        "price": 800.00,
                        "currency": "USD", 
                        "quality": "New",
                        "category": "Web Development",
                        "images": ["web_portfolio_1.jpg", "web_portfolio_2.jpg", "web_portfolio_3.jpg"]
                    },
                    {
                        "title": "Social Media Video Content",
                        "description": "I will create engaging video content for your social media platforms. Includes editing, motion graphics, and optimized formats for Instagram, TikTok, and YouTube.",
                        "price": 300.00,
                        "currency": "USD",
                        "quality": "New", 
                        "category": "Video Editing",
                        "images": ["video_thumbnail_1.jpg"],
                        "videos": ["social_demo_1.mp4", "promo_video_2.mp4"]
                    },
                    {
                        "title": "Content Writing & SEO",
                        "description": "I will write SEO-optimized blog posts and web content that ranks well on Google. Each article is researched, unique, and designed to engage your target audience.",
                        "price": 75.00,
                        "currency": "USD",
                        "quality": "New",
                        "category": "Writing",
                        "images": ["writing_samples_1.jpg", "writing_samples_2.jpg"]
                    },
                    {
                        "title": "Mobile App UI/UX Design", 
                        "description": "I will design beautiful and user-friendly mobile app interfaces. Includes wireframes, prototypes, and complete design systems. Available for iOS and Android.",
                        "price": 500.00,
                        "currency": "USD",
                        "quality": "New",
                        "category": "UI/UX Design",
                        "images": ["app_design_1.png", "app_design_2.png", "app_design_3.png", "app_design_4.png"]
                    }
                ]
                
                for service_data in services:
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
                print(f"✅ Created {len(services)} sample services")
            
            # Display current services
            all_services = Service.query.all()
            print(f"\n📊 Current marketplace status:")
            print(f"   Total Services: {len(all_services)}")
            print(f"   Total Users: {User.query.count()}")
            
            print(f"\n🎯 Services in database:")
            for service in all_services:
                media_count = len(service.image_list) + len(service.video_list)
                print(f"   • {service.title} - {service.currency} {service.price} ({media_count} media items)")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = init_marketplace()
    if success:
        print("\n🎉 Marketplace initialized successfully!")
        print("\n🚀 To start the application:")
        print("   python app.py")
        print("\n🔗 Then visit:")
        print("   http://localhost:5000/services - Browse all services")
        print("   http://localhost:5000/post_service - Post a new service")
    else:
        print("\n❌ Failed to initialize marketplace")