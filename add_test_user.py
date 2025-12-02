from app import app, db, User

with app.app_context():
    test_user = User(email="test@example.com", role="seller")
    db.session.add(test_user)
    db.session.commit()
    print("Test user added:", test_user.id, test_user.email, test_user.role)
