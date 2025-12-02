#!/usr/bin/env python3
"""
Test STK Push with Real Phone Numbers
This script helps diagnose STK push issues with real phone numbers
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mpesa import stk_push
from dotenv import load_dotenv

load_dotenv()

def test_real_phone_stk_push():
    """Test STK push with real phone number"""
    
    print("📱 Testing STK Push with Real Phone Number")
    print("=" * 50)
    
    # Check environment configuration
    env = os.getenv("MPESA_ENV", "sandbox")
    consumer_key = os.getenv("MPESA_CONSUMER_KEY", "")
    shortcode = os.getenv("MPESA_SHORTCODE", "")
    
    print(f"🔧 Environment: {env}")
    print(f"🔑 Consumer Key: {consumer_key[:8]}...")
    print(f"📞 Shortcode: {shortcode}")
    
    # Check if using sandbox with real numbers (this won't work)
    if env == "sandbox" and consumer_key.startswith("DFZV"):
        print("\n❌ CRITICAL ISSUE DETECTED!")
        print("You're using SANDBOX credentials but trying to send to real phone numbers.")
        print("This will NOT work. Here's why:")
        print("  • Sandbox can only send STK push to official test numbers")
        print("  • Real phone numbers require PRODUCTION credentials")
        print("  • Your current shortcode (174379) is a sandbox shortcode")
        print("\n🔧 SOLUTION OPTIONS:")
        print("1. Switch to production M-Pesa credentials")
        print("2. OR use only official sandbox test numbers:")
        print("   • 254708374149")
        print("   • 254700000000")
        print("   • 254711234567")
        return False
    
    return True

def ask_user_for_phone():
    """Ask user for their real phone number"""
    
    print("\n📞 Phone Number Test")
    print("=" * 30)
    
    # Get phone number from user
    phone = input("Enter your real phone number (e.g., 2547XXXXXXXX): ").strip()
    
    if not phone:
        print("❌ No phone number provided")
        return None
    
    # Format phone number
    if phone.startswith('0') and len(phone) == 10:
        phone = '254' + phone[1:]
        print(f"✅ Formatted to: {phone}")
    elif phone.startswith('+254'):
        phone = phone[1:]
        print(f"✅ Formatted to: {phone}")
    elif phone.startswith('254') and len(phone) == 12:
        print(f"✅ Already in correct format: {phone}")
    else:
        print(f"❌ Invalid format. Should be 254XXXXXXXXX")
        return None
    
    return phone

def test_production_credentials():
    """Check if production credentials are set up"""
    
    print("\n🔐 Production Credentials Check")
    print("=" * 35)
    
    env = os.getenv("MPESA_ENV", "sandbox")
    
    if env == "sandbox":
        print("❌ Currently using SANDBOX environment")
        print("   • Cannot send STK push to real phone numbers")
        print("   • Need to switch to production environment")
        return False
    
    # Check production credentials
    prod_consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    prod_consumer_secret = os.getenv("MPESA_CONSUMER_SECRET") 
    prod_shortcode = os.getenv("MPESA_SHORTCODE")
    prod_passkey = os.getenv("MPESA_PASSKEY")
    
    required_creds = [
        ("Consumer Key", prod_consumer_key),
        ("Consumer Secret", prod_consumer_secret),
        ("Shortcode", prod_shortcode),
        ("Passkey", prod_passkey)
    ]
    
    all_good = True
    for name, value in required_creds:
        if value:
            print(f"✅ {name}: {value[:8]}..." if 'KEY' in name or 'SECRET' in name else f"✅ {name}: {value}")
        else:
            print(f"❌ {name}: NOT SET")
            all_good = False
    
    return all_good

def create_production_env_template():
    """Create a template for production .env file"""
    
    template = """# PRODUCTION M-Pesa Configuration
# Replace with your actual production credentials

# Set environment to production
MPESA_ENV=production

# Your Production Consumer Key (from Safaricom)
MPESA_CONSUMER_KEY=your_production_consumer_key_here

# Your Production Consumer Secret  
MPESA_CONSUMER_SECRET=your_production_consumer_secret_here

# Your Production Shortcode (from Safaricom)
MPESA_SHORTCODE=your_production_shortcode_here

# Your Production Passkey
MPESA_PASSKEY=your_production_passkey_here

# Callback URL (use your domain)
MPESA_CALLBACK_URL=https://yourdomain.com/mpesa/callback

# B2C Payout credentials
MPESA_INITIATOR_NAME=your_initiator_name
MPESA_SECURITY_CREDENTIAL=your_security_credential
MPESA_QUEUE_TIMEOUT_URL=https://yourdomain.com/mpesa/timeout
MPESA_RESULT_URL=https://yourdomain.com/mpesa/result
"""
    
    with open("production_env_template.env", "w") as f:
        f.write(template)
    
    print("\n📄 Created 'production_env_template.env' file")
    print("   Update it with your production credentials")

def main():
    """Main diagnostic function"""
    
    print("🔧 STK Push Real Number Diagnostic Tool")
    print("=" * 45)
    
    # Step 1: Check current configuration
    if not test_real_phone_stk_push():
        print("\n💡 RECOMMENDATIONS:")
        print("1. Get production M-Pesa credentials from Safaricom")
        print("2. Switch MPESA_ENV to 'production' in your .env file")
        print("3. Update all M-Pesa credentials with production values")
        return
    
    # Step 2: Check production setup
    if not test_production_credentials():
        print("\n💡 To use real phone numbers, you need:")
        print("1. Production M-Pesa credentials from Safaricom")
        print("2. Set MPESA_ENV=production")
        print("3. Valid production shortcode and passkey")
        create_production_env_template()
        return
    
    # Step 3: Test with real phone number
    phone = ask_user_for_phone()
    if not phone:
        return
    
    # Test STK push
    print(f"\n🧪 Testing STK push to {phone}")
    print("-" * 30)
    
    try:
        amount = 10
        response = stk_push(
            phone_number=phone,
            amount=amount,
            account_reference="TestRealPayment",
            transaction_desc="Test payment with real number",
            callback_url=os.getenv("MPESA_CALLBACK_URL", "https://webhook.site/test")
        )
        
        print(f"✅ Response: {response}")
        
        if response.get('ResponseCode') == '0':
            print("🎉 SUCCESS! STK push sent successfully")
            print(f"   📱 Check your phone ({phone}) for the STK push prompt")
            print(f"   💰 Amount: KES {amount}")
        else:
            print(f"❌ Error: {response.get('ResponseDescription', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        print("\n💡 Common issues:")
        print("   • Production credentials not properly configured")
        print("   • Network connectivity issues") 
        print("   • Invalid phone number format")
        print("   • Insufficient account balance")

if __name__ == "__main__":
    main()