"""
M-Pesa Daraja API Integration
Save this as: mpesa.py in your project root directory
"""

import os
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# M-Pesa Configuration
MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE', '174379')
MPESA_CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL', 'https://yourdomain.com/mpesa/callback')

# Use sandbox URLs for testing
IS_PRODUCTION = os.getenv('MPESA_PRODUCTION', 'False').lower() == 'true'
BASE_URL = "https://api.safaricom.co.ke" if IS_PRODUCTION else "https://sandbox.safaricom.co.ke"

# Token cache
_token_cache = {'token': None, 'expiry': 0}


def get_mpesa_token():
    """
    Get M-Pesa access token from Daraja API
    Returns: access_token string or None
    """
    import time
    current_time = time.time()
    
    # Return cached token if still valid
    if _token_cache['token'] and _token_cache['expiry'] > current_time:
        print("✅ Using cached M-Pesa token")
        return _token_cache['token']
    
    if not MPESA_CONSUMER_KEY or not MPESA_CONSUMER_SECRET:
        print("❌ M-Pesa credentials missing in .env")
        print(f"   MPESA_CONSUMER_KEY: {'SET' if MPESA_CONSUMER_KEY else 'MISSING'}")
        print(f"   MPESA_CONSUMER_SECRET: {'SET' if MPESA_CONSUMER_SECRET else 'MISSING'}")
        return None
    
    # Use sandbox URL for development
    auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    
    try:
        print(f"🔐 Requesting M-Pesa token from: {auth_url}")
        print(f"   Using Consumer Key: {MPESA_CONSUMER_KEY[:10]}...")
        
        auth_string = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"
        base64_string = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {base64_string}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(auth_url, headers=headers, timeout=15, verify=True)
        
        print(f"📡 Token Response Status: {response.status_code}")
        print(f"📡 Response Text: {response.text[:200]}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            
            if not token:
                print(f"❌ No access_token in response: {data}")
                return None
            
            # Convert expires_in to int (M-Pesa returns it as string)
            try:
                expires_in = int(expires_in)
            except (ValueError, TypeError):
                expires_in = 3600
            
            # Cache token
            _token_cache['token'] = token
            _token_cache['expiry'] = current_time + (expires_in - 60)
            
            print(f"✅ M-Pesa token obtained successfully")
            print(f"   Token: {token[:20]}...")
            print(f"   Expires in: {expires_in} seconds")
            return token
        else:
            print(f"❌ Token request failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"❌ Token request timed out (15 seconds)")
        print(f"   Check your internet connection and firewall")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error getting token: {str(e)}")
        print(f"   Make sure sandbox.safaricom.co.ke is accessible")
        return None
    except Exception as e:
        print(f"❌ Unexpected error getting token: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def stk_push(phone_number, amount, account_reference, transaction_desc, callback_url=None):
    """
    Initiate M-Pesa STK Push (Lipa Na M-Pesa Online)
    
    Args:
        phone_number: Buyer's phone in format 254712345678
        amount: Amount in KES (integer)
        account_reference: Payment reference (e.g., SERVICE123)
        transaction_desc: Description of transaction
        callback_url: Your callback endpoint URL
    
    Returns:
        dict with response from M-Pesa API
    """
    
    print("\n" + "="*80)
    print("📱 INITIATING STK PUSH")
    print("="*80)
    
    # Validate inputs
    if not phone_number or not amount:
        error = "Phone number and amount are required"
        print(f"❌ {error}")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    
    if not isinstance(amount, int) or amount <= 0:
        error = "Amount must be a positive integer"
        print(f"❌ {error}")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    
    if not phone_number.startswith('254') or len(phone_number) != 12:
        error = f"Invalid phone format: {phone_number}. Use 254712345678"
        print(f"❌ {error}")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    
    # Use provided callback URL or default
    final_callback_url = callback_url or MPESA_CALLBACK_URL
    if not final_callback_url or final_callback_url == 'https://yourdomain.com/mpesa/callback':
        error = "MPESA_CALLBACK_URL not configured in .env"
        print(f"❌ {error}")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    
    print(f"📊 Phone: {phone_number}")
    print(f"📊 Amount: KES {amount}")
    print(f"📊 Reference: {account_reference}")
    print(f"📊 Shortcode: {MPESA_SHORTCODE}")
    print(f"📊 Callback: {final_callback_url}")
    
    # Get token
    token = get_mpesa_token()
    if not token:
        error = "Failed to obtain M-Pesa access token"
        print(f"❌ {error}")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    
    # Generate timestamp and password
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_string = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(data_string.encode()).decode()
    
    print(f"\n🔑 Timestamp: {timestamp}")
    print(f"🔑 Password generated: {password[:20]}...")
    
    # Prepare STK push request
    stk_url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": final_callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc
    }
    
    print(f"\n📤 Sending STK push to M-Pesa...")
    print(f"   URL: {stk_url}")
    print(f"   Payload keys: {list(payload.keys())}")
    
    try:
        response = requests.post(stk_url, json=payload, headers=headers, timeout=30)
        
        print(f"\n📡 Response Status: {response.status_code}")
        print(f"📡 Response Body: {response.text[:500]}")
        
        result = response.json() if response.text else {}
        
        response_code = result.get('ResponseCode')
        response_desc = result.get('ResponseDescription', 'No description')
        
        print(f"\n✅ Response Code: {response_code}")
        print(f"✅ Response Desc: {response_desc}")
        
        if response_code == '0':
            checkout_id = result.get('CheckoutRequestID')
            merchant_id = result.get('MerchantRequestID')
            print(f"🆔 Checkout Request ID: {checkout_id}")
            print(f"🆔 Merchant Request ID: {merchant_id}")
        
        print("="*80 + "\n")
        
        return result
        
    except requests.exceptions.Timeout:
        error = "M-Pesa request timed out (10 seconds)"
        print(f"❌ {error}")
        print("="*80 + "\n")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    except requests.exceptions.RequestException as e:
        error = f"Network error: {str(e)}"
        print(f"❌ {error}")
        print("="*80 + "\n")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    except Exception as e:
        error = f"Unexpected error: {str(e)}"
        print(f"❌ {error}")
        print("="*80 + "\n")
        return {'ResponseCode': '1', 'ResponseDescription': error}


def b2c_payout(phone_number, amount, remarks="Payout"):
    """
    Initiate B2C (Business to Consumer) payout for sellers
    
    Args:
        phone_number: Seller's phone in format 254712345678
        amount: Amount in KES (integer)
        remarks: Payout description
    
    Returns:
        dict with response from M-Pesa API
    """
    
    print("\n" + "="*80)
    print("💳 INITIATING B2C PAYOUT")
    print("="*80)
    
    if not phone_number or not amount:
        error = "Phone number and amount are required"
        print(f"❌ {error}")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    
    print(f"📊 Phone: {phone_number}")
    print(f"📊 Amount: KES {amount}")
    print(f"📊 Remarks: {remarks}")
    
    # Get token
    token = get_mpesa_token()
    if not token:
        error = "Failed to obtain M-Pesa access token"
        print(f"❌ {error}")
        return {'ResponseCode': '1', 'ResponseDescription': error}
    
    # Prepare B2C request
    b2c_url = f"{BASE_URL}/mpesa/b2c/v1/paymentrequest"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "InitiatorName": "testapi",
        "SecurityCredential": os.getenv('MPESA_SECURITY_CREDENTIAL', ''),
        "CommandID": "SalaryPayment",
        "Amount": amount,
        "PartyA": MPESA_SHORTCODE,
        "PartyB": phone_number,
        "Remarks": remarks,
        "QueueTimeOutURL": MPESA_CALLBACK_URL,
        "ResultURL": MPESA_CALLBACK_URL
    }
    
    print(f"\n📤 Sending B2C request to M-Pesa...")
    print(f"   URL: {b2c_url}")
    
    try:
        response = requests.post(b2c_url, json=payload, headers=headers, timeout=30)
        
        print(f"\n📡 Response Status: {response.status_code}")
        print(f"📡 Response Body: {response.text[:500]}")
        
        result = response.json() if response.text else {}
        
        print(f"\n✅ Response received")
        print("="*80 + "\n")
        
        return result
        
    except Exception as e:
        error = f"B2C error: {str(e)}"
        print(f"❌ {error}")
        print("="*80 + "\n")
        return {'ResponseCode': '1', 'ResponseDescription': error}