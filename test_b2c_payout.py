#!/usr/bin/env python3
"""
Test script for M-Pesa B2C payout functionality
Run this to validate your B2C implementation
"""

import os
import sys
import json
from datetime import datetime, timezone

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Order, Payout, User, Service
from mpesa import get_access_token, b2c_payout

def test_database_setup():
    """Test that database models are properly created"""
    print("🔍 Testing database setup...")

    with app.app_context():
        try:
            # Check if tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            required_tables = ['order', 'payout', 'user', 'service']
            missing_tables = [table for table in required_tables if table not in tables]

            if missing_tables:
                print(f"❌ Missing tables: {missing_tables}")
                return False

            print("✅ All required tables exist")
            return True

        except Exception as e:
            print(f"❌ Database setup test failed: {e}")
            return False

def test_mpesa_connection():
    """Test M-Pesa API connection"""
    print("🔍 Testing M-Pesa API connection...")

    try:
        access_token = get_access_token()
        if access_token:
            print("✅ M-Pesa API connection successful")
            return True
        else:
            print("❌ Failed to get access token")
            return False
    except Exception as e:
        print(f"❌ M-Pesa connection test failed: {e}")
        return False

def test_b2c_payout_function():
    """Test B2C payout function with minimal amount"""
    print("🔍 Testing B2C payout function...")

    try:
        # Use a test phone number (sandbox test number)
        test_phone = "254708374149"  # Sandbox test number
        test_amount = 1  # Minimal amount for testing

        response = b2c_payout(
            phone_number=test_phone,
            amount=test_amount,
            remarks="Test B2C Payout"
        )

        print(f"B2C Response: {json.dumps(response, indent=2)}")

        if response.get("ResponseCode") == "0":
            print("✅ B2C payout initiated successfully")
            return True, response
        else:
            print(f"❌ B2C payout failed: {response.get('ResponseDescription')}")
            return False, response

    except Exception as e:
        print(f"❌ B2C payout test failed: {e}")
        return False, None

def test_payout_creation():
    """Test creating a payout record in database"""
    print("🔍 Testing payout record creation...")

    with app.app_context():
        try:
            # Create a test order first
            test_order = Order(
                service_id=1,  # Assuming service exists
                buyer_id=1,    # Assuming user exists
                seller_id=2,   # Assuming seller exists
                amount=100.00,
                status='paid'
            )
            db.session.add(test_order)
            db.session.commit()

            # Create payout record
            payout = Payout(
                order_id=test_order.id,
                seller_id=2,
                amount=95.00,  # 5% fee deducted
                phone_number="254708374149",
                status='processing',
                initiator_response=json.dumps({"test": "response"})
            )
            db.session.add(payout)
            db.session.commit()

            # Verify payout was created
            created_payout = Payout.query.get(payout.id)
            if created_payout:
                print("✅ Payout record created successfully")
                print(f"   Order ID: {created_payout.order_id}")
                print(f"   Amount: {created_payout.amount}")
                print(f"   Status: {created_payout.status}")
                return True
            else:
                print("❌ Payout record creation failed")
                return False

        except Exception as e:
            print(f"❌ Payout creation test failed: {e}")
            db.session.rollback()
            return False

def test_callback_endpoints():
    """Test that callback endpoints are accessible"""
    print("🔍 Testing callback endpoints...")

    with app.test_client() as client:
        try:
            # Test result callback
            result_data = {
                "Result": {
                    "ResultCode": 0,
                    "ResultDesc": "Test success",
                    "OriginatorConversationID": "test-123",
                    "ConversationID": "test-conv-123"
                }
            }

            response = client.post('/b2c/result',
                                 data=json.dumps(result_data),
                                 content_type='application/json')

            if response.status_code == 200:
                print("✅ B2C result callback endpoint accessible")
            else:
                print(f"❌ B2C result callback failed: {response.status_code}")

            # Test timeout callback
            timeout_data = {
                "Result": {
                    "ResultCode": 2,
                    "ResultDesc": "Test timeout",
                    "OriginatorConversationID": "test-123",
                    "ConversationID": "test-conv-123"
                }
            }

            response = client.post('/b2c/timeout',
                                 data=json.dumps(timeout_data),
                                 content_type='application/json')

            if response.status_code == 200:
                print("✅ B2C timeout callback endpoint accessible")
                return True
            else:
                print(f"❌ B2C timeout callback failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Callback endpoint test failed: {e}")
            return False

def main():
    """Run all tests"""
    print("🚀 Starting M-Pesa B2C Payout System Tests")
    print("=" * 50)

    tests = [
        ("Database Setup", test_database_setup),
        ("M-Pesa Connection", test_mpesa_connection),
        ("B2C Payout Function", test_b2c_payout_function),
        ("Payout Record Creation", test_payout_creation),
        ("Callback Endpoints", test_callback_endpoints),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            if isinstance(result, tuple):
                success, data = result
                results.append((test_name, success, data))
            else:
                results.append((test_name, result, None))
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False, str(e)))

    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, success, data in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if data and not success:
            print(f"   Error: {data}")

    passed = sum(1 for _, success, _ in results if success)
    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Your B2C payout system is working correctly.")
        print("\n📝 Next steps:")
        print("1. Start your Flask app: python app.py")
        print("2. Test the /trigger_payout/<order_id> endpoint with Postman")
        print("3. Monitor the mpesa_b2c.log file for transaction logs")
        print("4. Check your sandbox M-Pesa app for received payments")
    else:
        print("⚠️  Some tests failed. Please check the errors above and fix them before proceeding.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)