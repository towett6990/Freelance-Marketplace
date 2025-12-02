# mpesa.py
from dotenv import load_dotenv
import os
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import base64

load_dotenv()

CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
SHORTCODE = os.getenv("MPESA_SHORTCODE")
PASSKEY = os.getenv("MPESA_PASSKEY")
ENV = os.getenv("MPESA_ENV", "sandbox")

# B2C API configuration
INITIATOR_NAME = os.getenv("MPESA_INITIATOR_NAME")
SECURITY_CREDENTIAL = os.getenv("MPESA_SECURITY_CREDENTIAL")
QUEUE_TIMEOUT_URL = os.getenv("MPESA_QUEUE_TIMEOUT_URL", "https://webhook.site/timeout")
RESULT_URL = os.getenv("MPESA_RESULT_URL", "https://webhook.site/result")


def get_access_token():
    """Fetch access token from Safaricom Daraja API."""
    try:
        url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials" \
            if ENV == "sandbox" else "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        response = requests.get(url, auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET), timeout=30)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to get access token: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")


def generate_password():
    """Generate the base64-encoded password for STK push."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data_to_encode = SHORTCODE + PASSKEY + timestamp
    encoded_string = base64.b64encode(data_to_encode.encode("utf-8")).decode("utf-8")
    return encoded_string, timestamp


def stk_push(phone_number, amount, account_reference, transaction_desc, callback_url):
    """Initiate an STK push to a buyer's phone."""
    try:
        print("DEBUG: Getting access token...")
        access_token = get_access_token()
        print(f"DEBUG: Access token obtained: {access_token[:20]}...")

        password, timestamp = generate_password()
        print(f"DEBUG: Password generated: {password[:10]}...")

        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest" \
            if ENV == "sandbox" else "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Ensure amount is integer
        try:
            amount = int(float(amount))
        except (ValueError, TypeError):
            raise Exception("Invalid amount format")

        # Validate phone number format
        if not phone_number.startswith('254') or len(phone_number) != 12:
            raise Exception("Phone number must be in format 254XXXXXXXXX")

        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }

        print(f"DEBUG: STK Push URL: {url}")
        print(f"DEBUG: STK Push Payload: {payload}")

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response headers: {dict(response.headers)}")
        print(f"DEBUG: Response text: {response.text}")

        response.raise_for_status()
        result = response.json()

        print(f"DEBUG: STK Push Response: {result}")
        return result

    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Request exception: {str(e)}")
        raise Exception(f"STK Push request failed: {str(e)}")
    except ValueError as e:
        print(f"DEBUG: JSON parsing error: {str(e)}")
        raise Exception(f"Invalid response format: {str(e)}")
    except Exception as e:
        print(f"DEBUG: Unexpected error: {str(e)}")
        raise


def b2c_payout(phone_number, amount, remarks="Seller payout"):
    """Initiate B2C payout to seller (Business to Customer)"""
    try:
        access_token = get_access_token()

        url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest" \
            if ENV == "sandbox" else "https://api.safaricom.co.ke/mpesa/b2c/v1/paymentrequest"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Ensure amount is integer
        try:
            amount = int(float(amount))
        except (ValueError, TypeError):
            raise Exception("Invalid amount format")

        # Validate phone number format
        if not phone_number.startswith('254') or len(phone_number) != 12:
            raise Exception("Phone number must be in format 254XXXXXXXXX")

        payload = {
            "InitiatorName": os.getenv("MPESA_INITIATOR_NAME", "testapi"),
            "SecurityCredential": os.getenv("MPESA_SECURITY_CREDENTIAL", ""),
            "CommandID": "BusinessPayment",
            "Amount": amount,
            "PartyA": SHORTCODE,
            "PartyB": phone_number,
            "Remarks": remarks,
            "QueueTimeOutURL": os.getenv("MPESA_QUEUE_TIMEOUT_URL", "https://webhook.site/timeout"),
            "ResultURL": os.getenv("MPESA_RESULT_URL", "https://webhook.site/result"),
            "Occasion": "SellerPayout"
        }

        print(f"DEBUG: B2C Payout Payload: {payload}")

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()

        print(f"DEBUG: B2C Payout Response: {result}")
        return result

    except requests.exceptions.RequestException as e:
        raise Exception(f"B2C payout request failed: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid response format: {str(e)}")
