from app import app, db, User

# Run inside Flask's application context
with app.app_context():
    users = User.query.all()
    if not users:
        print("No users found in the database.")
    else:
        for user in users:
            print(f"ID: {user.id}, Email: {user.email}, Password: {user.password}")
