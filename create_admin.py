from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Check if admin already exists
    existing_admin = User.query.filter_by(username="admin").first()
    
    if existing_admin:
        print("❌ Admin user already exists!")
        print(f"   Username: {existing_admin.username}")
        print(f"   Email: {existing_admin.email}")
        print(f"   Role: {existing_admin.role}")
        print("\n💡 To reset password, delete the admin and run again, or use a different username.")
    else:
        # Create new admin
        admin = User(
            username="admin",
            email="admin@example.com",
            password=generate_password_hash("12345678"),
            role="admin",
            is_verified=True  # Auto-verify the admin
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created successfully!")
        print(f"   Username: admin")
        print(f"   Password: 12345678")
        print(f"   Email: admin@example.com")
        print("\n🔐 Please login at: http://localhost:5000/login")