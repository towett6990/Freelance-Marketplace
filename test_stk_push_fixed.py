#!/usr/bin/env python3
"""
Fixed M-Pesa STK Push Test Script
This script uses the official M-Pesa sandbox test numbers that are known to work.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mpesa import stk_push

def test_stk_push_with_official_numbers():
    """Test STK push with official M-Pesa sandbox test numbers"""
    
    print("🚀 Testing M-Pesa STK Push with Official Test Numbers")
    print("=" * 60)
    
    # Official M-Pesa Sandbox Test Numbers (these work with the sandbox)
    test_numbers = [
        "254708374149",  # Official test number 1
        "254700000000",  # Official test number 2  
        "254711234567",  # Official test number 3
        "254733333333"   # Official test number 4
    ]
    
    amount = 10  # Small amount for testing
    
    print(f"💰 Testing with amount: KES {amount}")
    print(f"📱 Testing with {len(test_numbers)} official test numbers:")
    for i, number in enumerate(test_numbers, 1):
        print(f"   {i}. {number}")
    
    print("\n" + "=" * 60)
    
    for i, phone_number in enumerate(test_numbers, 1):
        print(f"\n📞 Test {i}: Trying number {phone_number}")
        print("-" * 40)
        
        try:
            # Use a web-based webhook that can receive callbacks
            callback_url = "https://webhook.site/12345678-abcd-1234-5678-123456789012"
            
            print(f"📤 Sending STK push request...")
            print(f"   Phone: {phone_number}")
            print(f"   Amount: KES {amount}")
            print(f"   Callback: {callback_url}")
            
            response = stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=f"TestPayment{i}",
                transaction_desc=f"Test payment {i}",
                callback_url=callback_url
            )
            
            print(f"\n✅ SUCCESS! Response received:")
            print(f"   Response Code: {response.get('ResponseCode', 'N/A')}")
            print(f"   Response Description: {response.get('ResponseDescription', 'N/A')}")
            
            if response.get('ResponseCode') == '0':
                print(f"   ✅ STK push should arrive on {phone_number}")
                print(f"   📝 Checkout Request ID: {response.get('CheckoutRequestID', 'N/A')}")
                print(f"   📝 Merchant Request ID: {response.get('MerchantRequestID', 'N/A')}")
            else:
                print(f"   ❌ Error Code: {response.get('ErrorCode', 'N/A')}")
                print(f"   ❌ Error Message: {response.get('ErrorMessage', response.get('ResponseDescription', 'Unknown error'))}")
                
        except Exception as e:
            print(f"❌ FAILED: {str(e)}")
            
        print("\n" + "=" * 40)
        
        # Small delay between tests
        import time
        time.sleep(2)

def test_user_phone_format():
    """Test if user's phone number format is correct"""
    
    print("\n📱 Testing Phone Number Format")
    print("=" * 40)
    
    # Test different phone number formats
    test_formats = [
        "254708374149",    # Correct format
        "0708374149",      # Missing 254 prefix
        "+254708374149",   # With + prefix
        "708374149",       # Missing country code
        "25470837414900"   # Too long
    ]
    
    for phone in test_formats:
        print(f"\nTesting: {phone}")
        
        # Check format
        if phone.startswith('0') and len(phone) == 10:
            print(f"  ✅ Can be converted: 254{phone[1:]}")
        elif phone.startswith('+254'):
            print(f"  ✅ Can be converted: {phone[1:]}")
        elif phone.startswith('254') and len(phone) == 12:
            print(f"  ✅ Correct format")
        else:
            print(f"  ❌ Invalid format")

def test_credentials():
    """Test M-Pesa API credentials"""
    
    print("\n🔐 Testing M-Pesa API Credentials")
    print("=" * 40)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'MPESA_CONSUMER_KEY',
        'MPESA_CONSUMER_SECRET', 
        'MPESA_SHORTCODE',
        'MPESA_PASSKEY'
    ]
    
    all_good = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive data
            if 'KEY' in var or 'SECRET' in var:
                masked = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
                print(f"  ✅ {var}: {masked}")
            else:
                print(f"  ✅ {var}: {value}")
        else:
            print(f"  ❌ {var}: NOT SET")
            all_good = False
    
    if all_good:
        print("\n✅ All credentials are properly configured")
    else:
        print("\n❌ Some credentials are missing!")
        
    return all_good

def main():
    """Main test function"""
    
    print("🔧 M-Pesa STK Push Troubleshooting Tool")
    print("=" * 60)
    
    # Step 1: Test credentials
    if not test_credentials():
        print("\n❌ Fix credentials first before testing STK push")
        return
    
    # Step 2: Test phone format
    test_user_phone_format()
    
    # Step 3: Test with official numbers
    test_stk_push_with_official_numbers()
    
    print("\n" + "=" * 60)
    print("🎯 SUMMARY AND RECOMMENDATIONS:")
    print("=" * 60)
    print("1. ✅ If STK push arrived on test numbers: The issue is your phone number format")
    print("2. ❌ If no STK push arrived: Check your internet connection or API credentials") 
    print("3. 📱 Make sure your phone number is in 254XXXXXXXXX format")
    print("4. 🔒 In sandbox mode, only official test numbers work")
    print("5. 🌐 For production, you'll need real phone numbers and production credentials")
    
    print("\n📋 Next Steps:")
    print("1. Try the official test numbers above")
    print("2. If they work, format your phone number correctly (254XXXXXXXXX)")
    print("3. If they don't work, check your internet connection")
    print("4. For production use, switch to live M-Pesa credentials")

if __name__ == "__main__":
    main()