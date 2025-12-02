#!/usr/bin/env python3
"""
Initialize the database using Flask SQLAlchemy
"""

from app import app, db, User, Payment, Order, Service, Message, Payout
from werkzeug.security import generate_password_hash

def create_database():
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            
            # Verify the payment table has the correct structure
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('payment')]
            print(f"Payment table columns: {columns}")
            
            if 'order_id' not in columns:
                print("ERROR: order_id column missing from payment table")
                return False
            
            # Create a test admin user if none exists
            admin_email = "admin@example.com"
            if not User.query.filter_by(email=admin_email).first():
                admin = User(
                    username="admin",
                    email=admin_email,
                    password=generate_password_hash("admin123"),
                    role="admin"
                )
                db.session.add(admin)
                db.session.commit()
                print("Created default admin user")
            
            print("Database created successfully with all required tables")
            return True
            
    except Exception as e:
        print(f"Error creating database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    create_database()