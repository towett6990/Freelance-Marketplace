#!/usr/bin/env python3
"""
Script to fix the payment table by adding the missing order_id column
"""

import sqlite3
import os
from sqlalchemy import text

def fix_payment_table():
    # Get the database path
    db_path = os.path.join('instance', 'database.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if order_id column already exists
        cursor.execute("PRAGMA table_info(payment)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"Current payment table columns: {columns}")
        
        if 'order_id' in columns:
            print("order_id column already exists in payment table")
            return True
        
        # Add the order_id column
        print("Adding order_id column to payment table...")
        cursor.execute("""
            ALTER TABLE payment 
            ADD COLUMN order_id INTEGER 
            REFERENCES \"order\" (id)
        """)
        
        # Create the foreign key constraint
        print("Creating foreign key constraint...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_order_id 
            ON payment (order_id)
        """)
        
        # Commit changes
        conn.commit()
        print("Successfully added order_id column to payment table")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(payment)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Updated payment table columns: {columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error fixing payment table: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    fix_payment_table()