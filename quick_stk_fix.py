#!/usr/bin/env python3
"""
Quick STK Push Fix - Identify the Issue
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("🔍 STK Push Issue Diagnosis")
print("=" * 40)

# Check current configuration
env = os.getenv("MPESA_ENV", "sandbox")
consumer_key = os.getenv("MPESA_CONSUMER_KEY", "")
shortcode = os.getenv("MPESA_SHORTCODE", "")

print(f"Current Environment: {env}")
print(f"Consumer Key: {consumer_key[:8]}...")
print(f"Shortcode: {shortcode}")

print("\n📱 ISSUE ANALYSIS:")
if env == "sandbox" and consumer_key.startswith("DFZV"):
    print("❌ PROBLEM FOUND: You're using SANDBOX credentials")
    print("   • Sandbox = test environment")
    print("   • Real phone numbers = production environment") 
    print("   • These two don't mix!")
    print("\n🔧 SOLUTIONS:")
    print("1. EASY: Use sandbox test numbers instead:")
    print("   • 254708374149")
    print("   • 254700000000") 
    print("   • 254711234567")
    print("\n2. CORRECT: Get production credentials:")
    print("   • Contact Safaricom for production M-Pesa")
    print("   • Set MPESA_ENV=production")
    print("   • Update all credentials")

else:
    print("✅ Configuration looks correct for production")
    print("   Check your phone number format and network")