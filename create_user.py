from app import app, db, User
from werkzeug.security import generate_password_hash

# --- Customize these values ---
email = "seller@example.com"
username = "seller"
password = "123456"
role = "seller"  # change to "buyer" if you want a buyer account
# ------------------------------

with app.app_context():
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        db.session.delete(existing_user)
        db.session.commit()
        print("Old user deleted.")

    hashed_password = generate_password_hash(password)
    new_user = User(
        username=username,
        email=email,
        password=hashed_password,
        role=role,
        must_reset_password=False
    )

    db.session.add(new_user)
    db.session.commit()
    print(f"New {role} created successfully!")
    print(f"Email: {email}")
    print(f"Password: {password}")
