#!/usr/bin/env python3
"""
Script to initialize the database with all required tables including payment with order_id column
"""

import os
import sqlite3

def init_database():
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    
    try:
        # Create connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create user table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(120),
                email VARCHAR(150) UNIQUE NOT NULL,
                password VARCHAR(256) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                created_at DATETIME,
                avatar VARCHAR(256),
                bio TEXT,
                is_verified BOOLEAN DEFAULT 0,
                id_image VARCHAR(255),
                id_verification_score FLOAT DEFAULT 0.0,
                id_verification_status VARCHAR(20) DEFAULT 'pending',
                id_verified BOOLEAN DEFAULT 0,
                vision_message VARCHAR(500),
                id_front_document VARCHAR(255),
                id_back_document VARCHAR(255),
                id_confidence_score FLOAT DEFAULT 0.0,
                id_content_score FLOAT DEFAULT 0.0,
                id_integrity_score FLOAT DEFAULT 0.0,
                id_quality_score FLOAT DEFAULT 0.0,
                id_face_score FLOAT,
                manual_review_required BOOLEAN DEFAULT 0,
                manual_review_status VARCHAR(20) DEFAULT 'pending',
                id_retry_count INTEGER DEFAULT 0,
                last_id_upload_at DATETIME,
                auto_rejection_reasons TEXT,
                mpesa_phone VARCHAR(15)
            )
        ''')
        
        # Create order table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                amount NUMERIC(10,2) NOT NULL,
                currency VARCHAR(8) NOT NULL DEFAULT 'KES',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (service_id) REFERENCES service (id),
                FOREIGN KEY (buyer_id) REFERENCES user (id),
                FOREIGN KEY (seller_id) REFERENCES user (id)
            )
        ''')
        
        # Create service table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                price NUMERIC(10,2) NOT NULL DEFAULT 0.00,
                currency VARCHAR(8) NOT NULL DEFAULT 'KES',
                quality VARCHAR(32),
                category VARCHAR(120),
                contact_info TEXT,
                image_filenames TEXT,
                video_filenames TEXT,
                contact VARCHAR(200),
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (seller_id) REFERENCES user (id)
            )
        ''')
        
        # Create payment table with order_id column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                amount NUMERIC(10,2) NOT NULL,
                currency VARCHAR(8) NOT NULL DEFAULT 'KES',
                mpesa_receipt_number VARCHAR(50),
                checkout_request_id VARCHAR(50),
                merchant_request_id VARCHAR(50),
                phone_number VARCHAR(15) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                payment_date DATETIME,
                payout_status VARCHAR(20) DEFAULT 'pending',
                payout_transaction_id VARCHAR(50),
                payout_date DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (order_id) REFERENCES order (id),
                FOREIGN KEY (service_id) REFERENCES service (id),
                FOREIGN KEY (buyer_id) REFERENCES user (id),
                FOREIGN KEY (seller_id) REFERENCES user (id)
            )
        ''')
        
        # Create message table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT,
                file_path VARCHAR(256),
                timestamp DATETIME,
                is_read BOOLEAN DEFAULT 0,
                FOREIGN KEY (sender_id) REFERENCES user (id),
                FOREIGN KEY (receiver_id) REFERENCES user (id)
            )
        ''')
        
        # Create payout table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payout (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                seller_id INTEGER NOT NULL,
                amount NUMERIC(10,2) NOT NULL,
                currency VARCHAR(8) NOT NULL DEFAULT 'KES',
                originator_conversation_id VARCHAR(50),
                conversation_id VARCHAR(50),
                transaction_id VARCHAR(50),
                phone_number VARCHAR(15) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'processing',
                initiator_response TEXT,
                result_response TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (order_id) REFERENCES order (id),
                FOREIGN KEY (seller_id) REFERENCES user (id)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_order_id ON payment (order_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_buyer_id ON payment (buyer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_seller_id ON payment (seller_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_sender_receiver ON message (sender_id, receiver_id)')
        
        # Commit changes
        conn.commit()
        
        # Verify the payment table structure
        cursor.execute('PRAGMA table_info(payment)')
        columns = cursor.fetchall()
        print('Payment table created successfully with columns:')
        for col in columns:
            print(f'  {col[1]} ({col[2]})')
        
        print(f'Database initialized at: {db_path}')
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    init_database()