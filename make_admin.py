# make_admin.py
from app import app, db, User

with app.app_context():
    # Change 'your_username' to your actual username
    username = input("Enter username to make admin: ")
    
    user = User.query.filter_by(username=username).first()
    
    if user:
        user.role = "admin"
        user.is_verified = True  # Also verify them
        db.session.commit()
        print(f"✅ SUCCESS! {username} is now an admin!")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Role: {user.role}")
        print("\n🔄 Please logout and login again for changes to take effect.")
    else:
        print(f"❌ User '{username}' not found!")
        print("\nAvailable users:")
        for u in User.query.all():
            print(f"  - {u.username} (role: {u.role})")