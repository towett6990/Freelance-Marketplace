#!/usr/bin/env python3
"""
Test Working STK Push with Official Sandbox Numbers
This will prove your M-Pesa integration works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mpesa import stk_push

def test_working_stk():
    """Test STK push with a guaranteed working sandbox number"""
    
    print("🧪 Testing M-Pesa Integration with Working Sandbox Number")
    print("=" * 60)
    
    # This is the most reliable sandbox test number
    test_phone = "254708374149"
    amount = 10
    
    print(f"📱 Using test phone: {test_phone}")
    print(f"💰 Test amount: KES {amount}")
    print(f"🌍 Environment: Sandbox (MPESA_ENV=sandbox)")
    print()
    
    print("⚡ This test proves your M-Pesa integration works!")
    print("   If successful, you'll get STK push on this number.")
    print()
    
    try:
        response = stk_push(
            phone_number=test_phone,
            amount=amount,
            account_reference="SystemTest001",
            transaction_desc="System integration test",
            callback_url="https://webhook.site/12345678-abcd-1234-5678-123456789012"
        )
        
        print("📡 API Response:")
        print(f"   Response Code: {response.get('ResponseCode')}")
        print(f"   Description: {response.get('ResponseDescription')}")
        
        if response.get('ResponseCode') == '0':
            print()
            print("🎉 SUCCESS! Your M-Pesa integration works perfectly!")
            print(f"   ✅ STK push sent to {test_phone}")
            print(f"   📝 Checkout ID: {response.get('CheckoutRequestID', 'N/A')}")
            print()
            print("💡 THIS PROVES:")
            print("   • Your API credentials are correct")
            print("   • Your M-Pesa integration code works")
            print("   • The STK push functionality is operational")
            print()
            print("🔧 TO USE REAL PHONE NUMBERS:")
            print("   1. Get production M-Pesa credentials from Safaricom")
            print("   2. Change MPESA_ENV to 'production' in .env file")
            print("   3. Update all credentials with production values")
            
        else:
            print(f"❌ Error: {response.get('ErrorMessage', response.get('ResponseDescription', 'Unknown'))}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        print("This might indicate a configuration issue")

if __name__ == "__main__":
    test_working_stk()