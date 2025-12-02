from app import db, User

with db.engine.connect() as conn:
    result = conn.execute(db.text("SELECT id, email, password FROM user"))
    for row in result:
        print(row)
