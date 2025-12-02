#!/usr/bin/env python3
"""
Test script for STK Push with multiple test phone numbers
"""
import os
from dotenv import load_dotenv
from mpesa import stk_push

load_dotenv()

def test_multiple_phones():
    """Test STK push with different official M-Pesa sandbox numbers"""
    
    print("🔍 Testing STK Push with Multiple Test Numbers")
    print("=" * 60)
    
    # Official M-Pesa sandbox test numbers
    test_numbers = [
        "254708374149",  # Primary test number
        "254700000000",  # Secondary test number  
        "254711231236",  # Alternative test number
    ]
    
    for phone in test_numbers:
        print(f"\n📱 Testing with phone: {phone}")
        print("-" * 40)
        
        try:
            response = stk_push(
                phone_number=phone,
                amount=1,
                account_reference=f"Test{phone[-4:]}",
                transaction_desc="Test payment for STK push",
                callback_url="https://webhook.site/test"
            )
            
            print(f"✅ Success with {phone}")
            print(f"   Response Code: {response.get('ResponseCode', 'N/A')}")
            print(f"   Description: {response.get('ResponseDescription', 'N/A')}")
            print(f"   Merchant Request ID: {response.get('MerchantRequestID', 'N/A')}")
            print(f"   Checkout Request ID: {response.get('CheckoutRequestID', 'N/A')}")
            
            if response.get('ResponseCode') == '0':
                print(f"🎉 STK push initiated successfully to {phone}")
                print(f"📲 Check your phone for the M-Pesa prompt!")
                return True
            else:
                print(f"❌ Failed with {phone}: {response}")
                
        except Exception as e:
            print(f"❌ Error with {phone}: {str(e)}")
    
    print("\n⚠️ All test numbers failed. Checking environment...")
    
    # Check environment settings
    print(f"Environment: {os.getenv('MPESA_ENV', 'sandbox')}")
    print(f"Shortcode: {os.getenv('MPESA_SHORTCODE', 'Not set')}")
    print(f"Consumer Key: {'Set' if os.getenv('MPESA_CONSUMER_KEY') else 'Not set'}")
    print(f"Consumer Secret: {'Set' if os.getenv('MPESA_CONSUMER_SECRET') else 'Not set'}")
    print(f"Passkey: {'Set' if os.getenv('MPESA_PASSKEY') else 'Not set'}")
    
    return False

if __name__ == "__main__":
    print("🚀 Starting STK Push Test")
    print("This will test multiple phone numbers to ensure STK push works")
    print()
    
    success = test_multiple_phones()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ STK Push test completed successfully!")
        print("📝 Note: The test number that worked should receive an M-Pesa prompt")
    else:
        print("❌ STK Push test failed with all numbers")
        print("🔧 Check your M-Pesa credentials and environment settings")
    
    print("\n💡 Tips:")
    print("   • Make sure you're using the correct sandbox test numbers")
    print("   • Ensure your M-Pesa sandbox credentials are valid")
    print("   • Check that the callback URL is accessible")
    print("   • Verify the phone number format (254XXXXXXXXX)")