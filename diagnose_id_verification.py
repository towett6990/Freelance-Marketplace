#!/usr/bin/env python3
"""
ID Verification Diagnostic Script
Helps diagnose why ID verification is taking too long or failing
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db, User, IDVerificationAudit
from enhanced_id_verification import verify_national_id_enhanced
from ocr_preprocessing import enhanced_ocr_extract

def diagnose_user_verification(user_id):
    """Diagnose verification status for a specific user"""
    print(f"\n🔍 Diagnosing ID verification for User ID: {user_id}")

    user = User.query.get(user_id)
    if not user:
        print("❌ User not found!")
        return

    print(f"👤 User: {user.username or user.email}")
    print(f"✅ Verified: {user.is_verified}")
    print(f"📋 Manual Review Status: {user.manual_review_status}")
    print(f"🎯 Verification Score: {user.id_verification_score}")
    print(f"📅 Last Upload: {user.last_id_upload_at}")

    # Check ID files
    id_folder = os.path.join(os.path.dirname(__file__), "static", "uploads", "ids")

    front_path = None
    back_path = None

    if user.id_front_document:
        front_path = os.path.join(id_folder, user.id_front_document)
        print(f"📄 Front ID: {user.id_front_document} (exists: {os.path.exists(front_path)})")

    if user.id_back_document:
        back_path = os.path.join(id_folder, user.id_back_document)
        print(f"📄 Back ID: {user.id_back_document} (exists: {os.path.exists(back_path)})")

    # Test verification on existing files
    if front_path and os.path.exists(front_path):
        print(f"\n🧪 Testing front ID verification...")
        try:
            front_result = verify_national_id_enhanced(front_path)
            print(f"   Status: {front_result['status']}")
            print(f"   Score: {front_result['score']}")
            print(f"   Message: {front_result['message']}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    if back_path and os.path.exists(back_path):
        print(f"\n🧪 Testing back ID verification...")
        try:
            back_result = verify_national_id_enhanced(back_path)
            print(f"   Status: {back_result['status']}")
            print(f"   Score: {back_result['score']}")
            print(f"   Message: {back_result['message']}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Check audit trail
    audits = IDVerificationAudit.query.filter_by(user_id=user.id).order_by(IDVerificationAudit.created_at.desc()).all()
    if audits:
        print(f"\n📊 Audit Trail ({len(audits)} entries):")
        for audit in audits[:3]:  # Show last 3
            print(f"   {audit.created_at}: {audit.verification_type} -> {audit.decision}")
            print(f"      Score: {audit.confidence_score}, Reason: {audit.decision_reason[:100]}...")
    else:
        print("\n📊 No audit trail found")

def find_pending_users():
    """Find users with pending verification"""
    print("\n👥 Users with pending ID verification:")

    pending_users = User.query.filter(
        User.manual_review_required == True,
        User.manual_review_status == "pending"
    ).order_by(User.last_id_upload_at.desc()).all()

    if not pending_users:
        print("✅ No users pending manual review")
        return

    for user in pending_users:
        print(f"ID {user.id}: {user.username or user.email} - Uploaded: {user.last_id_upload_at}")

    return pending_users

def test_ocr_on_sample():
    """Test OCR on a sample ID image"""
    print("\n🧪 Testing OCR on sample ID...")

    id_folder = os.path.join(os.path.dirname(__file__), "static", "uploads", "ids")

    # Find a recent ID file
    id_files = []
    if os.path.exists(id_folder):
        for file in os.listdir(id_folder):
            if file.startswith("id_") and (file.endswith(".jpg") or file.endswith(".png")):
                filepath = os.path.join(id_folder, file)
                mtime = os.path.getmtime(filepath)
                id_files.append((filepath, mtime))

    if not id_files:
        print("❌ No ID files found to test")
        return

    # Test most recent file
    id_files.sort(key=lambda x: x[1], reverse=True)
    test_file = id_files[0][0]

    print(f"Testing file: {os.path.basename(test_file)}")

    try:
        ocr_result = enhanced_ocr_extract(test_file)
        print(f"OCR Success: {ocr_result['success']}")
        print(f"Confidence: {ocr_result['confidence']}%")
        print(f"Word Count: {ocr_result['word_count']}")
        print(f"Text Preview: {ocr_result['text'][:200]}...")
    except Exception as e:
        print(f"❌ OCR Error: {e}")

def manual_approve_user(user_id, admin_user_id=1):
    """Manually approve a user's ID verification"""
    print(f"\n✅ Manually approving User ID: {user_id}")

    user = User.query.get(user_id)
    if not user:
        print("❌ User not found!")
        return False

    # Update user status
    user.is_verified = True
    user.manual_review_required = False
    user.manual_review_status = "approved"
    user.manual_reviewed_by = admin_user_id
    user.manual_reviewed_at = datetime.now(timezone.utc)

    # Create audit entry
    audit = IDVerificationAudit(
        user_id=user.id,
        verification_type="manual",
        confidence_score=user.id_confidence_score or 0.8,
        content_score=user.id_content_score or 0.8,
        integrity_score=user.id_integrity_score or 0.8,
        quality_score=user.id_quality_score or 0.8,
        decision="verified",
        decision_reason="Manual approval by admin - expedited verification",
        reviewed_by=admin_user_id,
        reviewed_at=datetime.now(timezone.utc),
        notes="Manual approval to resolve verification delay"
    )

    db.session.add(audit)
    db.session.commit()

    print(f"✅ User {user.username or user.email} has been manually approved!")
    return True

def main():
    print("🔧 ID Verification Diagnostic Tool")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python diagnose_id_verification.py diagnose <user_id>")
        print("  python diagnose_id_verification.py pending")
        print("  python diagnose_id_verification.py test_ocr")
        print("  python diagnose_id_verification.py approve <user_id>")
        return

    command = sys.argv[1]

    if command == "diagnose" and len(sys.argv) > 2:
        user_id = int(sys.argv[2])
        diagnose_user_verification(user_id)
    elif command == "pending":
        find_pending_users()
    elif command == "test_ocr":
        test_ocr_on_sample()
    elif command == "approve" and len(sys.argv) > 2:
        user_id = int(sys.argv[2])
        manual_approve_user(user_id)
    else:
        print("❌ Invalid command")

if __name__ == "__main__":
    # Set up Flask app context
    from app import app
    with app.app_context():
        main()