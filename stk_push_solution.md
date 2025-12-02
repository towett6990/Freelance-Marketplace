# 🚀 STK Push Solution for Real Phone Numbers

## 🎯 Quick Diagnosis
You have **sandbox credentials** but want to use **real phone numbers**. Here's how to fix it:

## 🔧 Option 1: Get Production Credentials (Recommended)

### Step 1: Apply for M-Pesa Production with Safaricom
1. Contact Safaricom Business team
2. Request M-Pesa Daraja API production access
3. Get your production credentials:
   - Production Consumer Key
   - Production Consumer Secret
   - Production Shortcode
   - Production Passkey

### Step 2: Update Your .env File
Replace your current `.env` with production values:

```env
# PRODUCTION M-Pesa Configuration
MPESA_ENV=production

# Your Production Credentials from Safaricom
MPESA_CONSUMER_KEY=your_production_key_here
MPESA_CONSUMER_SECRET=your_production_secret_here
MPESA_SHORTCODE=your_production_shortcode_here
MPESA_PASSKEY=your_production_passkey_here

# Production callback URLs
MPESA_CALLBACK_URL=https://yourdomain.com/mpesa/callback
MPESA_INITIATOR_NAME=your_initiator_name
MPESA_SECURITY_CREDENTIAL=your_security_credential
MPESA_QUEUE_TIMEOUT_URL=https://yourdomain.com/mpesa/timeout
MPESA_RESULT_URL=https://yourdomain.com/mpesa/result
```

### Step 3: Test with Real Phone
Once production is configured, you can use any real phone number in `254XXXXXXXXX` format.

## 🔧 Option 2: Test with Sandbox Numbers (Quick Fix)

If you want to test STK push immediately, use these official sandbox test numbers:

- **254708374149** ✅ (Most reliable)
- **254700000000** 
- **254711234567**
- **254733333333**

Your phone number format should be:
- ✅ `254708374149`
- ✅ `0708374149` (automatically converted)
- ✅ `+254708374149` (automatically converted)
- ❌ `708374149` (missing country code)

## 🚀 Quick Test Script

Create and run this to test your setup:

```python
from mpesa import stk_push

# Test with sandbox test number
phone = "254708374149"  # Official test number
amount = 10

response = stk_push(
    phone_number=phone,
    amount=amount,
    account_reference="Test123",
    transaction_desc="STK Test",
    callback_url="https://webhook.site/test"
)

print(f"Response: {response}")
if response.get('ResponseCode') == '0':
    print("✅ STK push should arrive on your test device!")
```

## 🔍 Troubleshooting Checklist

### If STK Push Still Doesn't Work:

1. **Check Phone Format**
   - Must be `254XXXXXXXXX`
   - 12 characters total
   - No spaces or special characters

2. **Check Account Balance**
   - Test with small amounts (KSH 1-10)
   - Ensure sufficient balance

3. **Check Network**
   - Ensure internet connection
   - Try on mobile data vs WiFi

4. **Check M-Pesa Service**
   - Ensure M-Pesa is active on the phone
   - Check if you can receive normal M-Pesa prompts

5. **Check Configuration**
   - Verify all environment variables
   - Ensure callback URL is accessible
   - Check if timestamps are correct

## 🎯 Next Steps

1. **For Immediate Testing**: Use sandbox test numbers
2. **For Production**: Get production credentials from Safaricom
3. **Monitor Logs**: Check for error messages in the application logs
4. **Test Incrementally**: Start with small amounts

## 📱 Phone Number Validation

Your phone number must be in one of these formats:
- `254XXXXXXXXX` (direct format)
- `0XXXXXXXXX` (will be auto-converted to 254 format)
- `+254XXXXXXXXX` (will be auto-converted to 254 format)

Common mistakes:
- ❌ `XXXXXXXXX` (missing 254)
- ❌ `+254XXXXXXXXX00` (too long)
- ❌ `254-XXX-XXX-XXX` (has special characters)

## 💡 Pro Tips

1. **Start Small**: Test with KSH 1-5 first
2. **Use Test Numbers**: For initial testing, use official sandbox numbers
3. **Monitor Logs**: Always check the debug output for error messages
4. **Phone Ready**: Have your phone ready to accept the M-Pesa prompt
5. **Timing**: STK push usually arrives within 10-30 seconds

---
**Need help?** Check the debug output in your application logs for specific error messages.