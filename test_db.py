from app import app, db, Payment
from sqlalchemy import inspect

with app.app_context():
    # Check if order_id column exists
    inspector = inspect(db.engine)
    columns = inspector.get_columns('payment')
    print("Payment table columns:")
    for col in columns:
        print(f"- {col['name']}: {col['type']} (nullable: {col['nullable']})")

    # Check if there are any payments
    payments = Payment.query.all()
    print(f"\nTotal payments: {len(payments)}")
    if payments:
        print("First payment:", payments[0].__dict__)