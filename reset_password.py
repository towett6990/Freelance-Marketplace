# reset_password.py
from app import app, db, User
from werkzeug.security import generate_password_hash, check_password_hash

NEW_PW = "123456"

with app.app_context():
    user = User.query.first()
    if not user:
        print("No user found.")
    else:
        print("User:", user.email)
        print("Before reset, password matches NEW_PW?:", check_password_hash(user.password, NEW_PW))
        user.password = generate_password_hash(NEW_PW)
        db.session.commit()
        print("Password reset to:", NEW_PW)
        print("After reset, password matches NEW_PW?:", check_password_hash(user.password, NEW_PW))
