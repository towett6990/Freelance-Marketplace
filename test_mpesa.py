#!/usr/bin/env python3
"""
Test script for M-Pesa integration
"""
import os
import sys
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import the M-Pesa functions
from mpesa import stk_push, get_access_token, generate_password

def test_mpesa_integration():
    """Test the M-Pesa integration functions"""

    print("🔍 Testing M-Pesa Integration")
    print("=" * 50)

    # Test 1: Get access token
    try:
        print("1. Testing access token retrieval...")
        access_token = get_access_token()
        print(f"✅ Access token obtained: {access_token[:20]}...")
    except Exception as e:
        print(f"❌ Failed to get access token: {e}")
        return False

    # Test 2: Generate password
    try:
        print("\n2. Testing password generation...")
        password, timestamp = generate_password()
        print(f"✅ Password generated: {password[:10]}...")
        print(f"✅ Timestamp: {timestamp}")
    except Exception as e:
        print(f"❌ Failed to generate password: {e}")
        return False

    # Test 3: STK Push (using test phone number)
    try:
        print("\n3. Testing STK Push...")
        # Use official M-Pesa sandbox test phone numbers
        test_phone = "254708374149"  # Official M-Pesa sandbox test number
        test_amount = 1  # Small amount for testing
        test_account_ref = "TestService123"
        test_desc = "Test payment for M-Pesa integration"

        # Use a dummy callback URL for testing
        callback_url = "https://webhook.site/your-unique-url"  # Replace with actual test URL

        print(f"📱 Initiating STK Push to: {test_phone}")
        print(f"💰 Amount: KES {test_amount}")
        print(f"📝 Account Reference: {test_account_ref}")

        response = stk_push(
            phone_number=test_phone,
            amount=test_amount,
            account_reference=test_account_ref,
            transaction_desc=test_desc,
            callback_url=callback_url
        )

        print("✅ STK Push Response:")
        print(f"   Response Code: {response.get('ResponseCode', 'N/A')}")
        print(f"   Response Description: {response.get('ResponseDescription', 'N/A')}")
        print(f"   Merchant Request ID: {response.get('MerchantRequestID', 'N/A')}")
        print(f"   Checkout Request ID: {response.get('CheckoutRequestID', 'N/A')}")

        if response.get('ResponseCode') == '0':
            print("🎉 STK Push initiated successfully!")
            print("📱 Check your phone for the M-Pesa prompt.")
            return True
        else:
            print("⚠️ STK Push failed or returned unexpected response.")
            return False

    except Exception as e:
        print(f"❌ STK Push failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting M-Pesa Integration Test")
    print(f"🌐 Environment: {os.getenv('MPESA_ENV', 'sandbox')}")
    print(f"🏪 Shortcode: {os.getenv('MPESA_SHORTCODE', 'N/A')}")
    print()

    success = test_mpesa_integration()

    print("\n" + "=" * 50)
    if success:
        print("✅ M-Pesa integration test completed successfully!")
        print("📝 Note: Check your test phone for M-Pesa prompt.")
    else:
        print("❌ M-Pesa integration test failed.")
        print("🔧 Check your credentials and network connection.")

    return success

if __name__ == "__main__":
    main()