import os
import io
import json
import logging
from datetime import datetime, timezone
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_from_directory, session, jsonify, current_app
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, PasswordField, SubmitField,
    TextAreaField, DecimalField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename, safe_join
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Mail, Message as MailMessage
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv
from decimal import Decimal
import pytesseract
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
import cv2
import face_recognition
import numpy as np
import uuid
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

import os
from dotenv import load_dotenv

db = SQLAlchemy()
load_dotenv()

USE_MOCK_VISION = os.environ.get("USE_MOCK_VISION", "False").lower() == "true"
KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CLOUD_VISION_API_KEY = os.getenv("GOOGLE_CLOUD_VISION_API_KEY")


if USE_MOCK_VISION:
    
    from mock_vision import MockImageAnnotatorClient as ImageAnnotatorClient
    from mock_vision import MockCredentials as service_account
    import mock_vision as vision
else:
  
    from google.oauth2 import service_account
    from google.cloud import vision

if USE_MOCK_VISION:
    client = ImageAnnotatorClient()
else:
    if not GOOGLE_CLOUD_VISION_API_KEY or not KEY_PATH:
        raise EnvironmentError("Missing Vision API key or credentials path in .env")
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    client = vision.ImageAnnotatorClient(credentials=credentials)


client = vision.ImageAnnotatorClient()

def verify_id_document(file_path, side="front"):
    """
    Enhanced ID Document Verification
    Prioritizes automatic verification when OCR detects sufficient ID keywords
    """
    try:
        
        from enhanced_id_verification import verify_national_id_enhanced
        
        result = verify_national_id_enhanced(file_path)
        
        if result["status"] == "verified":
            if side == "front":
                result["message"] = f"✅ Front side verified - {result['message']}"
            else:
                result["message"] = f"✅ Back side verified - {result['message']}"
        elif result["status"] == "rejected":
            if side == "front":
                result["message"] = f"❌ Front side rejected - {result['message']}"
            else:
                result["message"] = f"❌ Back side rejected - {result['message']}"
        
        return result
        
    except Exception as e:
        return {"status": "rejected", "score": 0, "message": f"Verification failed: {str(e)}"}

def preprocess_image(image_path):
    img = Image.open(image_path)
    img = img.convert("L")  # grayscale
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    return img

def analyze_id_image(image_path, selfie_path=None, user=None):
    """
    Enhanced ID verification that prioritizes automatic verification
    when OCR detects sufficient ID keywords
    """
    try:

        from enhanced_id_verification import analyze_id_image_enhanced
        result = analyze_id_image_enhanced(image_path, selfie_path, user)
        return result
        
    except Exception as e:
        return {
            "status": "rejected",
            "score": 0.0,
            "message": f"ID analysis failed: {str(e)}",
            "fields": {},
            "face_score": None,
            "integrity_score": 0.0,
            "validation_reasons": [f"Analysis error: {str(e)}"]
        }

# --------------------
# Config & folders
# --------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_FOLDER = os.path.join(STATIC_DIR, "uploads")
ID_FOLDER = os.path.join(UPLOAD_FOLDER, "ids")
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
CHAT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "chat")
SERVICE_IMG_FOLDER = os.path.join(STATIC_DIR, "uploads", "services")
SERVICE_VIDEO_FOLDER = os.path.join(STATIC_DIR, "uploads", "services", "videos")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ID_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(CHAT_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SERVICE_IMG_FOLDER, exist_ok=True)
os.makedirs(SERVICE_VIDEO_FOLDER, exist_ok=True)
# Set directory permissions for uploads
try:
    os.chmod(SERVICE_IMG_FOLDER, 0o755)
except Exception as e:
    logging.warning("Could not set permissions on %s: %s", SERVICE_IMG_FOLDER, e)
try:
    os.chmod(SERVICE_VIDEO_FOLDER, 0o755)
except Exception as e:
    logging.warning("Could not set permissions on %s: %s", SERVICE_VIDEO_FOLDER, e)
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_ID_EXT = ALLOWED_IMAGE_EXT | {"pdf"}
ALLOWED_AVATAR_EXT = ALLOWED_IMAGE_EXT

# Service media constants
ALLOWED_IMAGE_EXTENSIONS = {"jpg","jpeg","png","gif","webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4","mov","avi","quicktime"}
ALLOWED_EXT = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS
MAX_IMAGE_COUNT = 50  # Increased limit significantly
MAX_VIDEO_COUNT = 20  # Increased limit significantly
MAX_IMAGE_SIZE_MB = 10  # Increased file size limit
MAX_VIDEO_SIZE_MB = 100  # Increased file size limit


def save_service_image(file_storage, user_id, max_width=1600):
    """
    Validates and saves an uploaded image.
    Returns filename (relative to static/uploads/services).
    Converts and resizes large images to JPEG (keeps png/webp if originally png/webp).
    """
    try:
        filename = secure_filename(file_storage.filename)
        ext = filename.rsplit(".", 1)[-1].lower()
        
        current_app.logger.debug("save_service_image: Processing %s (ext: %s)", filename, ext)
        current_app.logger.debug("save_service_image: Target directory: %s", SERVICE_IMG_FOLDER)
        
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image file type: {ext}")
        
        # size check
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        current_app.logger.debug("save_service_image: File size: %d bytes (%.2fMB)", size, size/1024/1024)
        
        if size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Image file too large (max {MAX_IMAGE_SIZE_MB}MB)")
        
        # create unique name
        base = f"{user_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex}"
        out_ext = ext if ext in ("png","webp","gif") else "jpg"
        out_name = f"{base}.{out_ext}"
        out_path = os.path.join(SERVICE_IMG_FOLDER, out_name)
        
        current_app.logger.debug("save_service_image: Will save to: %s", out_path)
        current_app.logger.debug("save_service_image: Directory exists: %s", os.path.exists(SERVICE_IMG_FOLDER))
        current_app.logger.debug("save_service_image: Directory writable: %s", os.access(SERVICE_IMG_FOLDER, os.W_OK))
        
        # Process image
        try:
            file_storage.stream.seek(0)
            img = Image.open(file_storage.stream).convert("RGB")
            current_app.logger.debug("save_service_image: Image opened successfully: %s", img.size)
        except Exception as e:
            current_app.logger.error("save_service_image: Failed to open image: %s", e)
            raise ValueError(f"Invalid image: {e}")
        
        # resize if large
        w,h = img.size
        if w > max_width:
            new_h = int(max_width * h / w)
            img = img.resize((max_width, new_h), Image.LANCZOS)
            current_app.logger.debug("save_service_image: Resized to: %s", img.size)
        
        # save with reasonable quality
        current_app.logger.debug("save_service_image: Saving image to disk...")
        if out_ext == "jpg":
            img.save(out_path, "JPEG", quality=82, optimize=True)
        else:
            img.save(out_path, out_ext.upper())
        
        current_app.logger.debug("save_service_image: Image saved successfully to %s", out_name)
        current_app.logger.debug("save_service_image: File exists after save: %s", os.path.exists(out_path))
        
        return out_name
        
    except Exception as e:
        current_app.logger.exception("save_service_image failed: %s", e)
        import traceback
        traceback.print_exc()
        raise

def save_service_video(file_storage, user_id):
    """
    Validates and saves an uploaded video.
    Returns filename (relative to static/uploads/services).
    """
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Unsupported video file type")
    # size check
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Video file too large (max {MAX_VIDEO_SIZE_MB}MB)")
    # create unique name
    base = f"{user_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex}"
    ext = filename.rsplit(".",1)[-1].lower()
    out_name = f"{base}.{ext}"
    out_path = os.path.join(SERVICE_IMG_FOLDER, out_name)
    # save video file
    file_storage.save(out_path)
    return out_name


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'database.db'))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ID_FOLDER"] = ID_FOLDER
app.config["AVATAR_FOLDER"] = AVATAR_FOLDER
app.config["CHAT_UPLOAD_FOLDER"] = CHAT_UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB to support larger videos

# optional mail
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT") or 0)
app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "False") == "True"
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@example.com")

# --------------------
# Extensions
# --------------------
db = SQLAlchemy(app)
migrate = Migrate(app, db)
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
limiter.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

mail = Mail(app)
ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])
socketio = SocketIO(app, cors_allowed_origins="*")

# --------------------
# Models
# --------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), nullable=True, unique=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    avatar = db.Column(db.String(256), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)

    # ID verification fields
    id_document = db.Column(db.String(256), nullable=True)
    id_image = db.Column(db.String(255))
    verification_status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    id_verification_score = db.Column(db.Float, default=0.0)
    id_verified = db.Column(db.Boolean, default=False)
    vision_message = db.Column(db.String(500))
    resubmission_notes = db.Column(db.Text, nullable=True)
    id_front_document = db.Column(db.String(255))
    id_back_document = db.Column(db.String(255))
    id_document_path = db.Column(db.String(500), nullable=True)
    id_confidence_score = db.Column(db.Float, default=0.0)
    id_content_score = db.Column(db.Float, default=0.0)
    id_integrity_score = db.Column(db.Float, default=0.0)
    id_quality_score = db.Column(db.Float, default=0.0)
    id_face_score = db.Column(db.Float, nullable=True)
    id_validation_reasons = db.Column(db.Text)
    id_integrity_issues = db.Column(db.Text)
    id_fields_extracted = db.Column(db.Text)
    manual_review_required = db.Column(db.Boolean, default=False)
    manual_review_status = db.Column(db.String(20), default="pending")
    manual_review_notes = db.Column(db.Text)
    manual_reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    manual_reviewed_at = db.Column(db.DateTime, nullable=True)
    id_retry_count = db.Column(db.Integer, default=0)
    last_id_upload_at = db.Column(db.DateTime, nullable=True)
    id_submission_ip = db.Column(db.String(45))
    auto_rejection_reasons = db.Column(db.Text)

    # M-Pesa payout info
    mpesa_phone = db.Column(db.String(15), nullable=True)

    # Relationships

    # Services created by this user
    services = db.relationship(
        "Service",
        back_populates="seller",
        cascade="all, delete-orphan"
    )

    # Orders where this user is the buyer
    orders = db.relationship(
        "Order",
        foreign_keys="Order.buyer_id",
        back_populates="buyer",
        cascade="all, delete-orphan"
    )

    # Orders where this user is the seller
    sales = db.relationship(
        "Order",
        foreign_keys="Order.seller_id",
        back_populates="seller"
    )

    # Payments where this user is the buyer
    buyer_payments = db.relationship(
        "Payment",
        foreign_keys="Payment.buyer_id",
        back_populates="buyer",
        cascade="all, delete-orphan"
    )

    # Payments where this user is the seller
    seller_payments = db.relationship(
        "Payment",
        foreign_keys="Payment.seller_id",
        back_populates="seller"
    )

    # ID verification audits
    verification_audits = db.relationship(
        "IDVerificationAudit",
        foreign_keys="IDVerificationAudit.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Messages sent/received
    sent_messages = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan"
    )

    received_messages = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan"
    )

    # Self-referencing relationship for manual review
    admin_reviewer = db.relationship("User", remote_side=[id])


    def display_name(self):
        return self.username or self.email.split("@", 1)[0]

    def check_password(self, password):
        return check_password_hash(self.password, password)


class IDVerificationAudit(db.Model):
    """Audit trail for all ID verification activities"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    verification_type = db.Column(db.String(50))  # 'auto', 'manual', 'retry'
    confidence_score = db.Column(db.Float)
    content_score = db.Column(db.Float)
    integrity_score = db.Column(db.Float)
    quality_score = db.Column(db.Float)
    face_score = db.Column(db.Float)
    extracted_fields = db.Column(db.Text)  # JSON
    validation_reasons = db.Column(db.Text)  # JSON
    integrity_issues = db.Column(db.Text)  # JSON
    decision = db.Column(db.String(20))  # 'verified', 'pending', 'rejected'
    decision_reason = db.Column(db.String(200))
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship("User", foreign_keys=[user_id], back_populates="verification_audits")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

class ServiceImage(db.Model):
    """Related table for service images"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship back to service
    service = db.relationship("Service", back_populates="images")


class ServiceVideo(db.Model):
    """Related table for service videos"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship back to service
    service = db.relationship("Service", back_populates="videos")

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # The user who created the service (seller)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    seller = db.relationship(
        "User",
        back_populates="services"
    )
    
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    currency = db.Column(db.String(8), nullable=False, default='KES')
    quality = db.Column(db.String(32), nullable=True)
    category = db.Column(db.String(120), nullable=True)
    contact_info = db.Column(db.Text, nullable=True)  # JSON string
    image_filenames = db.Column(db.Text, nullable=True)
    video_filenames = db.Column(db.Text, nullable=True)
    contact = db.Column(db.String(200), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships to media
    images = db.relationship(
        "ServiceImage",
        back_populates="service",
        cascade="all, delete-orphan"
    )
    videos = db.relationship(
        "ServiceVideo",
        back_populates="service",
        cascade="all, delete-orphan"
    )
    
    # Relationship to orders
    services_orders = db.relationship(
        "Order",
        back_populates="service",
        cascade="all, delete-orphan"
    )

    # Relationship to payments
    payments = db.relationship(
        "Payment",
        back_populates="service",
        cascade="all, delete-orphan"
    )

    @property
    def image_list(self):
        """Return list of image filenames from related table"""
        return [img.filename for img in self.images]

    @property
    def video_list(self):
        """Return list of video filenames from related table"""
        return [vid.filename for vid in self.videos]



class Order(db.Model):
    """Order model for tracking service purchases"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default='KES')

    # Order status
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, paid, completed, cancelled

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    service = db.relationship("Service", back_populates="services_orders")

    buyer = db.relationship(
        "User",
        foreign_keys=[buyer_id],
        back_populates="orders"
    )
    seller = db.relationship(
        "User",
        foreign_keys=[seller_id],
        back_populates="sales"
    )

    # Payments related to this order
    payments = db.relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    # Payouts related to this order
    payouts = db.relationship(
        "Payout",
        back_populates="order",
        cascade="all, delete-orphan"
    )


class Payment(db.Model):
    """Payment model for tracking M-Pesa transactions"""
    __tablename__ = "payment"

    id = db.Column(db.Integer, primary_key=True)
    
    order_id = db.Column(
        db.Integer, 
        db.ForeignKey('order.id', name="fk_payment_order_id"), 
        nullable=True
    )
    service_id = db.Column(
        db.Integer, 
        db.ForeignKey('service.id', name="fk_payment_service_id"), 
        nullable=False
    )
    buyer_id = db.Column(
        db.Integer, 
        db.ForeignKey('user.id', name="fk_payment_buyer_id"), 
        nullable=False
    )
    seller_id = db.Column(
        db.Integer, 
        db.ForeignKey('user.id', name="fk_payment_seller_id"), 
        nullable=False
    )

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default='KES')

    mpesa_receipt_number = db.Column(db.String(50), nullable=True)
    checkout_request_id = db.Column(db.String(50), nullable=True)
    merchant_request_id = db.Column(db.String(50), nullable=True)
    phone_number = db.Column(db.String(15), nullable=False)

    status = db.Column(db.String(20), nullable=False, default='pending')
    payment_date = db.Column(db.DateTime, nullable=True)

    payout_status = db.Column(db.String(20), nullable=True, default='pending')
    payout_transaction_id = db.Column(db.String(50), nullable=True)
    payout_date = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    order = db.relationship("Order", back_populates="payments")
    service = db.relationship("Service", back_populates="payments")
    buyer = db.relationship("User", foreign_keys=[buyer_id], back_populates="buyer_payments")
    seller = db.relationship("User", foreign_keys=[seller_id], back_populates="seller_payments")


class Payout(db.Model):
    """Payout model for tracking B2C disbursements to sellers"""
    __tablename__ = "payout"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, 
        db.ForeignKey('order.id', name="fk_payout_order_id"), 
        nullable=False
    )
    seller_id = db.Column(
        db.Integer, 
        db.ForeignKey('user.id', name="fk_payout_seller_id"), 
        nullable=False
    )

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default='KES')

    originator_conversation_id = db.Column(db.String(50), nullable=True)
    conversation_id = db.Column(db.String(50), nullable=True)
    transaction_id = db.Column(db.String(50), nullable=True)
    phone_number = db.Column(db.String(15), nullable=False)

    status = db.Column(db.String(20), nullable=False, default='processing')

    initiator_response = db.Column(db.Text, nullable=True)
    result_response = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    order = db.relationship("Order", back_populates="payouts")
    seller = db.relationship("User", foreign_keys=[seller_id])

    
    @property
    def image_list(self):
        """Return list of image filenames"""
        if self.image_filenames:
            try:
                return json.loads(self.image_filenames)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @property
    def video_list(self):
        """Return list of video filenames"""
        if self.video_filenames:
            try:
                return json.loads(self.video_filenames)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @property
    def contact_methods(self):
        """Return parsed contact methods dict"""
        if self.contact_info:
            try:
                return json.loads(self.contact_info)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    @property
    def all_media(self):
        """Return all media files with type information"""
        media = []
        for img in self.image_list:
            media.append({'type': 'image', 'file': img})
        for video in self.video_list:
            media.append({'type': 'video', 'file': video})
        return media


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)

    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(256), nullable=True)

    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")


# --------------------
# Logging configuration
# --------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mpesa_b2c.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --------------------


# Login loader
# --------------------
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None

# --------------------
# Forms
# --------------------
class RegistrationForm(FlaskForm):
    username = StringField("Display name", validators=[Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm", validators=[DataRequired(), EqualTo("password")])
    role = SelectField("Role", choices=[("buyer","Buyer"),("seller","Seller")], validators=[DataRequired()])
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("Login")


class ServiceForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=150)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10)])
    price = DecimalField("Price", validators=[DataRequired(), NumberRange(min=0)], places=2)
    submit = SubmitField("Post Service")


class ProfileForm(FlaskForm):
    username = StringField("Display name", validators=[Length(max=120)])
    bio = TextAreaField("Bio", validators=[Length(max=1000)])
    submit = SubmitField("Save")

# --------------------
# Helpers
# --------------------
def allowed_file(filename, allowed=ALLOWED_IMAGE_EXT):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def allowed_id_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_ID_EXT


def allowed_avatar_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXT


def require_role(role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if not current_user.is_authenticated or current_user.role != role:
                flash("Access denied.", "danger")
                return redirect(url_for("login"))
            return fn(*a, **k)
        return wrapper
    return decorator


def chat_room_name(a_id, b_id):
    a, b = sorted([int(a_id), int(b_id)])
    return f"chat_{a}_{b}"


def unread_count_for_user(user_id):
    return Message.query.filter_by(receiver_id=user_id, is_read=False).count()

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    user1 = db.relationship("User", foreign_keys=[user1_id])
    user2 = db.relationship("User", foreign_keys=[user2_id])


def get_or_create_conversation(user_a, user_b):
    convo = Conversation.query.filter(
        db.or_(
            db.and_(Conversation.user1_id == user_a, Conversation.user2_id == user_b),
            db.and_(Conversation.user1_id == user_b, Conversation.user2_id == user_a),
        )
    ).first()

    if not convo:
        convo = Conversation(user1_id=user_a, user2_id=user_b)
        db.session.add(convo)
        db.session.commit()

    return convo

@app.route("/chat/<int:conversation_id>")
@login_required
def chat(conversation_id):
    convo = Conversation.query.get_or_404(conversation_id)

    # User must belong to the conversation
    if current_user.id not in [convo.user1_id, convo.user2_id]:
        flash("You are not part of this conversation.", "danger")
        return redirect(url_for("dashboard"))

    # Identify the other user
    other = convo.user1 if convo.user2_id == current_user.id else convo.user2

    # Load messages
    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp.asc()).all()

    # Room name for Socket.IO
    room = f"convo_{conversation_id}"

    return render_template(
        "chat.html",
        conversation=convo,
        other=other,
        messages=messages,
        room=room
    )

@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now(timezone.utc).year,
        "unread_total": unread_count_for_user(current_user.id) if current_user.is_authenticated else 0
    }

# --------------------
# Routes (core)
# --------------------
@app.route('/')
def index():
    services = Service.query.all() if 'Service' in globals() else []

    if current_user.is_authenticated:
        return render_template('home.html', services=services, user=current_user)
    else:
        return render_template('index.html', services=services)


# Folder to save uploaded IDs
app.config["ID_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "ids")
os.makedirs(app.config["ID_FOLDER"], exist_ok=True)


@app.route("/verify_id", methods=["GET", "POST"])
@login_required
def verify_id():
    """Handles front and back ID upload and verification"""
    if request.method == "POST":
        front_file = request.files.get("front_id")
        back_file = request.files.get("back_id")

        # 🧩 Ensure both sides are uploaded
        if not front_file or not back_file:
            flash("Please upload both the front and back sides of your ID.", "danger")
            return redirect(url_for("verify_id"))

        # 🧩 Validate file extensions
        allowed_extensions = {"png", "jpg", "jpeg"}
        def valid_file(f):
            return "." in f.filename and f.filename.rsplit(".", 1)[1].lower() in allowed_extensions

        if not valid_file(front_file) or not valid_file(back_file):
            flash("Invalid file type. Only JPG or PNG images are accepted.", "danger")
            return redirect(url_for("verify_id"))

        # 🧩 Create secure filenames
        timestamp = int(datetime.now().timestamp())
        front_filename = secure_filename(f"front_{current_user.id}_{timestamp}_{front_file.filename}")
        back_filename = secure_filename(f"back_{current_user.id}_{timestamp}_{back_file.filename}")

        # 🧩 Ensure directory exists
        os.makedirs(app.config["ID_FOLDER"], exist_ok=True)

        front_path = os.path.join(app.config["ID_FOLDER"], front_filename)
        back_path = os.path.join(app.config["ID_FOLDER"], back_filename)

        # 🧩 Save uploaded files
        try:
            front_file.save(front_path)
            back_file.save(back_path)
        except Exception as e:
            flash(f"File save failed: {e}", "danger")
            return redirect(url_for("verify_id"))

        # 🧠 Run analysis for each side
        try:
            front_result = verify_id_document(front_path, side="front")
            back_result = verify_id_document(back_path, side="back")
        except Exception as e:
            flash(f"ID analysis failed: {str(e)}", "danger")
            return redirect(url_for("verify_id"))

        # 🧩 Combine the verification results
        verified = (
            front_result["status"] == "verified"
            and back_result["status"] == "verified"
        )

        # 🧩 Store verification results in database
        current_user.id_document_front = front_filename
        current_user.id_document_back = back_filename
        current_user.id_verification_status = "verified" if verified else "rejected"
        current_user.id_verification_score = (
            (front_result.get("score", 0) + back_result.get("score", 0)) / 2
        )
        current_user.vision_message = f"Front: {front_result['message']} | Back: {back_result['message']}"
        current_user.is_verified = verified
        current_user.id_verification_timestamp = datetime.now(timezone.utc)

        db.session.commit()

        # 🪪 Display result messages
        if verified:
            flash("✅ Both sides of your ID verified successfully.", "success")
            flash(f"Front: {front_result['message']}", "info")
            flash(f"Back: {back_result['message']}", "info")
        else:
            flash("❌ ID verification failed. Please re-upload clear and valid ID images.", "danger")
            flash(f"Front Result: {front_result['message']}", "warning")
            flash(f"Back Result: {back_result['message']}", "warning")

        return redirect(url_for("profile", username=current_user.username))

    return render_template("verify_id.html")

@app.route('/pay_service/<int:service_id>', methods=['POST'])
def pay_service(service_id):
    """Handle M-Pesa STK push payment initiation for a service."""
    try:
        # Get service and validate it exists
        service = Service.query.get_or_404(service_id)
        current_app.logger.debug("Processing payment for service %s: %s", service_id, service.title)

        # Get current user (buyer)
        if not current_user.is_authenticated:
            return jsonify({
                "ResponseCode": "1",
                "errorMessage": "User must be logged in to make payment"
            }), 401

        # Get form data
        phone = request.form.get("phone", "").strip()
        amount = request.form.get("amount", "").strip()

        # Validate required fields
        if not phone:
            current_app.logger.error("Phone number is required")
            return jsonify({
                "ResponseCode": "1",
                "errorMessage": "Phone number is required"
            }), 400

        if not amount:
            current_app.logger.error("Amount is required")
            return jsonify({
                "ResponseCode": "1",
                "errorMessage": "Amount is required"
            }), 400

        # Convert phone to format 254XXXXXXXXX
        if phone.startswith('0') and len(phone) == 10:
            phone = '254' + phone[1:]
        elif phone.startswith('+254'):
            phone = phone[1:]
        elif not phone.startswith('254') or len(phone) != 12:
            current_app.logger.error("Invalid phone format: %s", phone)
            return jsonify({
                "ResponseCode": "1",
                "errorMessage": "Phone number must be in format 07xxxxxxxx or 254xxxxxxxx"
            }), 400

        current_app.logger.debug("Converted phone number to: %s", phone)

        # Convert amount to integer
        try:
            amount = int(float(amount))
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError) as e:
            current_app.logger.error("Invalid amount format: %s", amount)
            return jsonify({
                "ResponseCode": "1",
                "errorMessage": "Invalid amount format"
            }), 400

        print(f"DEBUG: Payment amount: {amount}")

        # Get callback URL from environment or use default
        callback_url = os.getenv("MPESA_CALLBACK_URL", "https://webhook.site/12345678-abcd-1234-5678-123456789012")
        print(f"DEBUG: Using callback URL: {callback_url}")

        # Create payment record
        payment = Payment(
            service_id=service.id,
            buyer_id=current_user.id,
            seller_id=service.seller_id,
            amount=amount,
            phone_number=phone,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        print(f"DEBUG: Created payment record with ID: {payment.id}")

        # Import and call stk_push
        from mpesa import stk_push

        print("DEBUG: Calling stk_push function...")
        stk_response = stk_push(
            phone_number=phone,
            amount=amount,
            account_reference=f"Payment{payment.id}",
            transaction_desc=f"Payment for {service.title}",
            callback_url=callback_url
        )

        print(f"DEBUG: STK Push API Response: {stk_response}")

        # Update payment with STK push details
        if stk_response.get("ResponseCode") == "0":
            payment.checkout_request_id = stk_response.get("CheckoutRequestID")
            payment.merchant_request_id = stk_response.get("MerchantRequestID")
            db.session.commit()

        # Return the JSON response from stk_push() directly to frontend
        return jsonify(stk_response)

    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()

        return jsonify({
            "ResponseCode": "1",
            "errorMessage": f"Payment gateway error: {str(e)}"
        }), 500

@app.route('/payment_status/<int:service_id>')
def check_payment_status(service_id):
    # simulate checking payment
    return jsonify({"status": "paid"})

# Callback route to receive MPESA confirmation
@app.route("/mpesa/callback", methods=["POST"])
def mpesa_callback():
    """Handle M-Pesa payment callback and update payment status"""
    try:
        data = request.get_json()
        print(f"DEBUG: M-Pesa Callback received: {data}")

        if not data:
            print("ERROR: No callback data received")
            return jsonify({"ResultCode": 1, "ResultDesc": "No data received"}), 400

        # Extract callback metadata
        callback_data = data.get("Body", {}).get("stkCallback", {})
        result_code = callback_data.get("ResultCode")
        result_desc = callback_data.get("ResultDesc")
        checkout_request_id = callback_data.get("CheckoutRequestID")
        merchant_request_id = callback_data.get("MerchantRequestID")

        print(f"DEBUG: Result Code: {result_code}, Description: {result_desc}")

        # Find payment by CheckoutRequestID
        payment = None
        if checkout_request_id:
            payment = Payment.query.filter_by(checkout_request_id=checkout_request_id).first()

        if not payment:
            print(f"ERROR: Payment not found for CheckoutRequestID: {checkout_request_id}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Payment not found"}), 404

        # Update payment status based on callback
        if result_code == 0:
            # Payment successful
            callback_metadata = callback_data.get("CallbackMetadata", {}).get("Item", [])

            # Extract receipt number and other details
            receipt_number = None
            for item in callback_metadata:
                if item.get("Name") == "MpesaReceiptNumber":
                    receipt_number = item.get("Value")
                    break

            payment.status = 'completed'
            payment.mpesa_receipt_number = receipt_number
            payment.payment_date = datetime.now(timezone.utc)

            print(f"SUCCESS: Payment {payment.id} completed with receipt: {receipt_number}")

            # Trigger automatic payout to seller
            try:
                payout_result = initiate_seller_payout(payment)
                if payout_result:
                    print(f"SUCCESS: Payout initiated for seller {payment.seller_id}")
                else:
                    print(f"WARNING: Payout failed for payment {payment.id}")
            except Exception as payout_error:
                print(f"ERROR: Payout failed for payment {payment.id}: {payout_error}")

        else:
            # Payment failed
            payment.status = 'failed'
            print(f"FAILED: Payment {payment.id} failed: {result_desc}")

        payment.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})

    except Exception as e:
        print(f"EXCEPTION in callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ResultCode": 1, "ResultDesc": "Callback processing failed"}), 500


def initiate_b2c_payout(order_id):
    """Initiate B2C payout to seller for a completed order"""
    try:
        logger.info(f"Initiating B2C payout for order {order_id}")

        # Get order and validate it exists
        order = Order.query.get_or_404(order_id)
        if order.status != 'paid':
            logger.warning(f"Order {order_id} is not in paid status, cannot initiate payout")
            return False

        # Check if payout already exists
        existing_payout = Payout.query.filter_by(order_id=order_id).first()
        if existing_payout:
            logger.warning(f"Payout already exists for order {order_id}")
            return False

        # Calculate payout amount (service price minus platform fee if any)
        platform_fee = 0.05  # 5% platform fee
        payout_amount = int(order.amount * (1 - platform_fee))

        # Check if seller has M-Pesa number stored
        seller = order.seller
        if not seller.mpesa_phone:
            logger.error(f"Seller {seller.id} has no M-Pesa phone number for payout")
            return False

        # Convert seller phone to 254 format if needed
        seller_phone = seller.mpesa_phone
        if seller_phone.startswith('0') and len(seller_phone) == 10:
            seller_phone = '254' + seller_phone[1:]
        elif seller_phone.startswith('+254'):
            seller_phone = seller_phone[1:]

        if not seller_phone.startswith('254') or len(seller_phone) != 12:
            logger.error(f"Invalid seller phone format: {seller.mpesa_phone}")
            return False

        logger.info(f"Initiating B2C payout of {payout_amount} KES to {seller_phone} for order {order_id}")

        # Import and call B2C payout
        from mpesa import b2c_payout

        b2c_response = b2c_payout(
            phone_number=seller_phone,
            amount=payout_amount,
            remarks=f"Payout for order {order_id}"
        )

        # Store the initiator response
        initiator_response_json = json.dumps(b2c_response)

        # Create payout record
        payout = Payout(
            order_id=order_id,
            seller_id=seller.id,
            amount=payout_amount,
            phone_number=seller_phone,
            status='processing',
            initiator_response=initiator_response_json
        )

        # Extract conversation IDs if successful
        if b2c_response.get("ResponseCode") == "0":
            payout.originator_conversation_id = b2c_response.get("OriginatorConversationID")
            payout.conversation_id = b2c_response.get("ConversationID")
            logger.info(f"B2C payout initiated successfully for order {order_id}: {payout_amount} KES")
        else:
            error_msg = b2c_response.get("ResponseDescription", "B2C payout failed")
            logger.error(f"B2C payout failed for order {order_id}: {error_msg}")
            payout.status = 'failed'

        db.session.add(payout)
        db.session.commit()

        return b2c_response.get("ResponseCode") == "0"

    except Exception as e:
        logger.error(f"Payout initiation failed for order {order_id}: {str(e)}")
        db.session.rollback()
        return False


def initiate_seller_payout(payment):
    """Legacy function - kept for backward compatibility"""
    logger.warning("initiate_seller_payout is deprecated, use initiate_b2c_payout instead")
    return False


@app.route("/services")
def list_services():
    q = request.args.get("q", type=str)
    category = request.args.get("category", type=str)

    query = Service.query

    if q:
        query = query.filter(Service.title.ilike(f"%{q}%") | Service.description.ilike(f"%{q}%") | Service.category.ilike(f"%{q}%"))

    if category:
        query = query.filter(Service.category == category)

    services = query.order_by(Service.created_at.desc()).all()
    return render_template("services.html", services=services, q=q, category=category)

@app.route("/service/<int:service_id>")
def service_detail(service_id):
    # Load service with the seller relationship and media
    svc = Service.query.options(
        db.joinedload(Service.seller),
        db.joinedload(Service.images),
        db.joinedload(Service.videos)
    ).get_or_404(service_id)

    # Debug
    print(f"🔍 DEBUG service_detail: Service {service_id}")
    print(f"🔍 DEBUG service_detail: Images from related table: {svc.image_list}")
    print(f"🔍 DEBUG service_detail: Videos from related table: {svc.video_list}")

    # The service object now has image_list and video_list properties
    # that return lists of filenames from the related tables

    # Optional seller stats placeholder
    seller_stats = None
    if svc.seller:
        seller_stats = type("Stats", (), {
            "avg_rating": 4.5,
            "total_reviews": 10,
            "total_orders": 25
        })()

    # Related services
    related = Service.query.filter(
        Service.category == svc.category,
        Service.id != svc.id
    ).limit(4).all() if svc.category else []

    # Debug
    print(f"🔍 DEBUG service_detail: Service {service_id}")
    print(f"🔍 DEBUG service_detail: Seller: {svc.seller.username if svc.seller else 'None'}")
    print(f"🔍 DEBUG service_detail: Images from related table: {svc.image_list}")
    print(f"🔍 DEBUG service_detail: Videos from related table: {svc.video_list}")

    return render_template(
        "service_detail.html",
        service=svc,
        seller_stats=seller_stats,
        related=related
    )

# --------------------
# Register
# --------------------
@limiter.limit("6 per minute")
@app.route("/register", methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit() or request.method == "POST":
        email = (form.email.data.strip().lower() if form.email.data else request.form.get("email", "").strip().lower())
        username = (form.username.data.strip() if form.username.data else (request.form.get("username") or None))
        password = (form.password.data if form.password.data else request.form.get("password"))
        role = (form.role.data if form.role.data else request.form.get("role", "buyer"))

        if not email or not password:
            flash("Email and password required.", "danger")
            return render_template("register.html", form=form)

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("login"))

        if username and User.query.filter_by(username=username).first():
            flash("Username taken.", "warning")
            return render_template("register.html", form=form)

        u = User(username=username, email=email, password=generate_password_hash(password), role=role)
        db.session.add(u)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form=form)

# --------------------
# Login
# --------------------
@limiter.limit("10 per minute")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# --------------------
# Unified dashboard
# --------------------
@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        total_users = User.query.count()
        total_services = Service.query.count()
        total_messages = Message.query.count()
        recent = Service.query.order_by(Service.created_at.desc()).limit(8).all()
        return render_template("dashboard.html", user=current_user,
                               total_users=total_users,
                               total_services=total_services,
                               total_messages=total_messages,
                               recent=recent)

    # For sellers, show earnings and payments
    if current_user.role == "seller":
        my_services = Service.query.filter_by(user_id=current_user.id).order_by(Service.created_at.desc()).all()

        # Calculate earnings from completed payments
        earnings = db.session.query(db.func.sum(Payment.amount)).\
            join(Service, Payment.service_id == Service.id).\
            filter(Service.user_id == current_user.id, Payment.status == 'completed').scalar() or 0

        # Get recent payments
        recent_payments = Payment.query.\
            join(Service, Payment.service_id == Service.id).\
            filter(Service.user_id == current_user.id).\
            order_by(Payment.created_at.desc()).limit(10).all()

        return render_template("dashboard.html", user=current_user, services=my_services,
                             earnings=earnings, recent_payments=recent_payments)

    # For buyers, show their payment history
    else:
        payment_history = Payment.query.filter_by(buyer_id=current_user.id).\
            order_by(Payment.created_at.desc()).limit(10).all()

        return render_template("dashboard.html", user=current_user, payment_history=payment_history)

# --------------------
# Logout
# --------------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

# --------------------
# Password reset
# --------------------
def send_reset_email(user):
    token = ts.dumps(user.email, salt="password-reset-salt")
    reset_url = url_for("reset_with_token", token=token, _external=True)
    if app.config["MAIL_SERVER"]:
        msg = MailMessage("Password reset", recipients=[user.email], body=f"Reset link: {reset_url}")
        mail.send(msg)
        return True
    flash(f"Reset link (dev): {reset_url}", "info")
    return False


@app.route("/forgot_password", methods=["GET","POST"])
@limiter.limit("4 per minute")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
        flash("If that email exists we sent reset instructions.", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset/<token>", methods=["GET","POST"])
def reset_with_token(token):
    try:
        email = ts.loads(token, salt="password-reset-salt", max_age=1800)
    except SignatureExpired:
        flash("Token expired.", "danger")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Invalid token.", "danger")
        return redirect(url_for("forgot_password"))
    user = User.query.filter_by(email=email).first_or_404()
    if request.method == "POST":
        pw = request.form.get("new_password")
        pw2 = request.form.get("confirm_password")
        if not pw or pw != pw2:
            flash("Passwords mismatch.", "danger")
            return redirect(url_for("reset_with_token", token=token))
        user.password = generate_password_hash(pw)
        db.session.commit()
        flash("Password updated. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", token=token)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    filepath = safe_join(app.config["UPLOAD_FOLDER"], filename)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/profile/<string:username>")
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    # Correct - using new field name
    services = Service.query.filter_by(seller_id=user.id).order_by(Service.created_at.desc()).all()
    return render_template("profile.html", user=user, services=services)

@app.route("/upload_avatar", methods=["POST"])
@login_required
def upload_avatar():
    file = request.files.get("avatar")
    if not file:
        flash("No file selected.", "danger")
        return redirect(url_for("profile", username=current_user.username))

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        flash("Invalid file type.", "danger")
        return redirect(url_for("profile", username=current_user.username))

    filename = f"avatar_{current_user.id}_{int(datetime.now().timestamp())}.{ext}"
    path = os.path.join(app.config["AVATAR_FOLDER"], filename)
    file.save(path)

    current_user.avatar = filename
    db.session.commit()

    flash("Profile picture updated successfully!", "success")
    return redirect(url_for("profile", username=current_user.username))


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.username = request.form['username']
        current_user.bio = request.form['bio']

        file = request.files.get('avatar')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.root_path, 'static/uploads/avatars', filename)
            file.save(filepath)
            current_user.avatar = filename

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile', username=current_user.username))

    return render_template('edit_profile.html')

@app.route("/upload_id", methods=["GET", "POST"])
@login_required
def upload_id():
    """ID upload route with intelligent auto + manual verification"""
    if request.method == "POST":
        front_file = request.files.get("front_id")
        back_file = request.files.get("back_id")

        if not front_file or not back_file:
            flash("Please upload both the front and back sides of your ID.", "danger")
            return redirect(url_for("upload_id"))

        front_ext = front_file.filename.rsplit(".", 1)[-1].lower()
        back_ext = back_file.filename.rsplit(".", 1)[-1].lower()
        allowed_exts = {"png", "jpg", "jpeg", "pdf"}
        if front_ext not in allowed_exts or back_ext not in allowed_exts:
            flash("Invalid file type. Only JPG, PNG, or PDF allowed.", "danger")
            return redirect(url_for("upload_id"))

        save_dir = os.path.join(app.static_folder, "uploads", "ids")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = int(datetime.now().timestamp())

        front_filename = f"id_front_{current_user.id}_{timestamp}_{secure_filename(front_file.filename)}"
        back_filename = f"id_back_{current_user.id}_{timestamp}_{secure_filename(back_file.filename)}"
        front_path = os.path.join(save_dir, front_filename)
        back_path = os.path.join(save_dir, back_filename)

        try:
            front_file.save(front_path)
            back_file.save(back_path)
        except Exception as e:
            flash(f"File save failed: {e}", "danger")
            return redirect(url_for("upload_id"))

        # --- Selfie check ---
        selfie_detected = False
        try:
            import face_recognition
            image = face_recognition.load_image_file(front_path)
            faces = face_recognition.face_locations(image)
            if len(faces) == 1:
                (t, r, b, l) = faces[0]
                h, w = image.shape[:2]
                if ((r - l) * (b - t)) / (w * h) > 0.25:
                    selfie_detected = True
                    flash("⚠️ This looks like a selfie. Sending for manual review.", "warning")
        except Exception as e:
            print(f"Face detection skipped: {e}")

        # --- OCR check ---
        ocr_confidence = 0
        try:
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            
            from simple_ocr import enhanced_ocr_extract

            ocr_front = enhanced_ocr_extract(front_path)
            ocr_back = enhanced_ocr_extract(back_path)
            
            text_front = ocr_front["text"].upper() if ocr_front["success"] else ""
            text_back = ocr_back["text"].upper() if ocr_back["success"] else ""

            print("\n=== OCR FRONT ===\n", text_front)
            print("\n=== OCR BACK ===\n", text_back)

            id_keywords = ["REPUBLIC", "IDENTITY", "NUMBER", "CARD", "NATIONAL", "ID", "KENYA"]
            match_count = sum(kw in text_front + text_back for kw in id_keywords)
            ocr_confidence = match_count / len(id_keywords)  # 0 to 1 scale

            if match_count == 0:
                flash("⚠️ No ID text detected. Sending for manual review.", "warning")

        except Exception as e:
            print(f"OCR error: {e}")

        # --- AI Analysis ---
        try:
            selfie_path = None
            if current_user.avatar:
                selfie_path = os.path.join(app.config["AVATAR_FOLDER"], current_user.avatar)

            front_result = analyze_id_image(front_path, selfie_path, current_user)
            back_result = analyze_id_image(back_path, selfie_path, current_user)
            combined_score = (front_result.get("score", 0) + back_result.get("score", 0)) / 2

            # Save to database
            current_user.id_front_document = front_filename
            current_user.id_back_document = back_filename
            current_user.id_confidence_score = combined_score
            current_user.last_id_upload_at = datetime.now(timezone.utc)
            current_user.id_retry_count += 1

            # === DECISION LOGIC: Auto vs Manual ===
            
            # HIGH CONFIDENCE → AUTO APPROVE
            if combined_score >= 0.75 and ocr_confidence >= 0.5 and not selfie_detected:
                current_user.is_verified = True
                current_user.verification_status = "approved"
                current_user.manual_review_required = False
                current_user.manual_review_status = "approved"
                decision = "auto_approved"
                flash("✅ ID verified successfully!", "success")
                flash(f"🎯 Confidence Score: {combined_score:.2f}", "info")
            
            # LOW CONFIDENCE → AUTO REJECT
            elif combined_score < 0.3 and ocr_confidence < 0.2:
                current_user.is_verified = False
                current_user.verification_status = "rejected"
                current_user.manual_review_required = False
                current_user.manual_review_status = "rejected"
                decision = "auto_rejected"
                flash("❌ ID verification failed. Please upload clearer images.", "danger")
                flash("💡 Tips: Good lighting, flat surface, all corners visible", "info")
            
            # MEDIUM CONFIDENCE → MANUAL REVIEW
            else:
                current_user.is_verified = False
                current_user.verification_status = "pending"
                current_user.manual_review_required = True
                current_user.manual_review_status = "pending"
                decision = "manual_review"
                flash("📋 ID submitted for manual review by our team.", "warning")
                flash(f"⏱️ Review typically takes 24-48 hours.", "info")
                flash(f"🔍 Review Score: {combined_score:.2f}", "info")

            # Log the decision
            db.session.add(IDVerificationAudit(
                user_id=current_user.id,
                verification_type=decision,
                confidence_score=combined_score,
                decision=decision,
                decision_reason=f"Score: {combined_score:.2f}, OCR: {ocr_confidence:.2f}, Selfie: {selfie_detected}"[:200]
            ))
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            flash(f"Analysis failed: {e}", "danger")
            return redirect(url_for("upload_id"))

        return redirect(url_for("profile", username=current_user.username))

    return render_template("upload_id.html")


# === ADMIN MANUAL REVIEW ROUTE ===
@app.route("/admin/manual_reviews")
@login_required
def admin_manual_reviews():
    """Admin page to review pending IDs"""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))
    
    # Get all users needing manual review
    pending_users = User.query.filter_by(
        manual_review_required=True,
        manual_review_status="pending"
    ).order_by(User.last_id_upload_at.desc()).all()
    
    return render_template("admin/manual_reviews.html", users=pending_users)

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    """Admin dashboard"""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))
    
    # Get statistics
    total_users = User.query.count()
    pending_reviews = User.query.filter_by(
        manual_review_required=True,
        manual_review_status="pending"
    ).count()
    verified_users = User.query.filter_by(is_verified=True).count()
    
    return render_template("admin/dashboard.html",
                         total_users=total_users,
                         pending_reviews=pending_reviews,
                         verified_users=verified_users)

@app.route("/admin/review_id/<int:user_id>", methods=["GET", "POST"])
@login_required
def admin_review_id(user_id):
    """Admin reviews a specific user's ID"""
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == "POST":
        action = request.form.get("action")  # "approve" or "reject"
        notes = request.form.get("notes", "")
        
        if action == "approve":
            user.is_verified = True
            user.verification_status = "approved"
            user.manual_review_status = "approved"
            user.manual_review_required = False
            user.manual_review_notes = notes
            user.manual_reviewed_by = current_user.id
            user.manual_reviewed_at = datetime.now(timezone.utc)
            
            # Log the manual approval
            db.session.add(IDVerificationAudit(
                user_id=user.id,
                verification_type="manual_approved",
                confidence_score=user.id_confidence_score or 0,
                decision="approved",
                decision_reason=f"Manually approved by admin. Notes: {notes}"[:200]
            ))
            
            flash(f"✅ {user.username}'s ID has been approved.", "success")
        
        elif action == "reject":
            user.is_verified = False
            user.verification_status = "rejected"
            user.manual_review_status = "rejected"
            user.manual_review_required = False
            user.manual_review_notes = notes
            user.manual_reviewed_by = current_user.id
            user.manual_reviewed_at = datetime.now(timezone.utc)
            
            # Log the manual rejection
            db.session.add(IDVerificationAudit(
                user_id=user.id,
                verification_type="manual_rejected",
                confidence_score=user.id_confidence_score or 0,
                decision="rejected",
                decision_reason=f"Manually rejected by admin. Notes: {notes}"[:200]
            ))
            
            flash(f"❌ {user.username}'s ID has been rejected.", "warning")
        
        db.session.commit()
        return redirect(url_for("admin_manual_reviews"))
    
    return render_template("admin/review_id.html", user=user)


# === USER CHECKS THEIR STATUS ===
@app.route("/verification_status")
@login_required
def verification_status():
    """User checks their verification status"""
    return render_template("verification_status.html")

@app.route("/ids/<filename>")
def id_file(filename):
    return send_from_directory(app.config["ID_FOLDER"], filename)


@app.route("/conversations")
@login_required
def conversations():
    partner_ids = set()
    sent = Message.query.with_entities(Message.receiver_id).filter_by(sender_id=current_user.id).all()
    recv = Message.query.with_entities(Message.sender_id).filter_by(receiver_id=current_user.id).all()
    for r in sent + recv:
        partner_ids.add(r[0])
    partners = []
    for pid in partner_ids:
        user = User.query.get(pid)
        if not user: continue
        last_msg = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == pid)) |
            ((Message.sender_id == pid) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        unread = Message.query.filter_by(receiver_id=current_user.id, sender_id=pid, is_read=False).count()
        partners.append({"user": user, "last_message": last_msg, "unread": unread})
    partners.sort(key=lambda p: p["last_message"].timestamp if p["last_message"] else datetime.min, reverse=True)
    chats = [{"username": p["user"].username or p["user"].email, "unread_count": p["unread"], "user_id": p["user"].id} for p in partners]
    return render_template("messages.html", chats=chats)


# --------------------
# Chat Routes
# --------------------
@app.route("/chat_user/<username>", methods=["GET", "POST"])
@login_required
def chat_user(username):
    receiver = User.query.filter_by(username=username).first_or_404()

    # Only buyer–seller chat allowed
    if {current_user.role, receiver.role} != {"buyer", "seller"}:
        flash("Chat allowed only between buyers and sellers.", "warning")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        content = request.form.get("content")
        file = request.files.get("file")

        file_path = None
        safe = secure_filename(file.filename)
        filename = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S_") + safe
        save_path = os.path.join(app.config["CHAT_UPLOAD_FOLDER"], filename)
        file.save(save_path)
        file_path = f"uploads/chat/{filename}"

        msg = Message(sender_id=current_user.id, receiver_id=receiver.id,
                      content=content, file_path=file_path, is_read=False)
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for("chat", username=username))

    # fetch conversation
    messages_list = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver.id)) |
        ((Message.sender_id == receiver.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    # mark unread messages (that current_user received) as read
    unread = Message.query.filter_by(receiver_id=current_user.id, sender_id=receiver.id, is_read=False).all()
    for m in unread:
        m.is_read = True
    if unread:
        db.session.commit()

    room = chat_room_name(current_user.id, receiver.id)
    return render_template("chat.html", receiver=receiver, messages=messages_list, room=room)


@app.route("/api/unread_count")
@login_required
def api_unread_count():
    return jsonify({"unread": unread_count_for_user(current_user.id)})


@app.route("/messages/<int:other_id>", methods=["GET","POST"])
@login_required
def messages(other_id):
    other = User.query.get_or_404(other_id)
    if request.method == "POST":
        content = request.form.get("content","").strip()
        if content:
            msg = Message(sender_id=current_user.id, receiver_id=other.id, content=content, is_read=False)
            db.session.add(msg)
            db.session.commit()
            socketio.emit("notify_new_message", {"from": current_user.username, "room": chat_room_name(current_user.id, other.id)}, room=f"user_{other.id}")
            return redirect(url_for("messages", other_id=other_id))
    chat = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    return render_template("messages.html", chat=chat, other=other)


@app.route("/message_user/<int:user_id>", methods=["GET", "POST"])
@login_required
def message_user(user_id):
    """Route to start a conversation with a user"""
    other = User.query.get_or_404(user_id)

    # Only buyer–seller chat allowed
    if {current_user.role, other.role} != {"buyer", "seller"}:
        flash("Chat allowed only between buyers and sellers.", "warning")
        return redirect(url_for("dashboard"))

    # Redirect to existing chat if it exists
    return redirect(url_for("chat", username=other.username))


@socketio.on("join")
def on_join(data):
    room = data.get("room")
    user_room = data.get("user_room")
    if room: join_room(room)
    if user_room: join_room(user_room)


@socketio.on("leave")
def on_leave(data):
    room = data.get("room")
    user_room = data.get("user_room")
    if room: leave_room(room)
    if user_room: leave_room(user_room)


@socketio.on("typing")
def on_typing(data):
    room = data.get("room")
    typing = bool(data.get("typing", False))
    if room:
        emit("typing", {"room": room, "typing": typing, "user": current_user.username}, room=room, include_self=False)

@socketio.on("send_message")
def on_send_message(data):
    conversation_id = int(data.get("conversation_id"))
    receiver_id = int(data.get("receiver_id"))
    content = (data.get("content") or "").strip()

    if not content:
        return

    msg = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content
    )
    db.session.add(msg)
    db.session.commit()

    room = f"convo_{conversation_id}"

    payload = {
        "id": msg.id,
        "sender_id": current_user.id,
        "sender": current_user.username,
        "receiver_id": receiver_id,
        "content": msg.content,
        "timestamp": msg.timestamp.strftime("%H:%M"),
        "room": room
    }

    emit("receive_message", payload, room=room)


# --------------------
# Enhanced Admin ID verification endpoints
# --------------------
@app.route("/admin/id_reviews")
@login_required
@require_role("admin")
def admin_id_reviews():
    """Admin dashboard for reviewing pending ID verifications"""
    pending_users = User.query.filter(
        User.manual_review_required == True,
        User.manual_review_status == "pending"
    ).order_by(User.last_id_upload_at.desc()).all()
    
    in_review_users = User.query.filter(
        User.manual_review_status == "in_review"
    ).order_by(User.manual_reviewed_at.desc()).all()
    
    stats = {
        'pending_count': len(pending_users),
        'in_review_count': len(in_review_users),
        'total_reviews_today': IDVerificationAudit.query.filter(
            IDVerificationAudit.created_at >= datetime.now(timezone.utc).date(),
            IDVerificationAudit.verification_type == "manual"
        ).count()
    }
    
    return render_template("admin_id_reviews.html",
                         pending_users=pending_users,
                         in_review_users=in_review_users,
                         stats=stats)


@app.route("/admin/id_review/<int:user_id>", methods=["GET", "POST"])
@login_required
@require_role("admin")
def admin_id_review_detail(user_id):
    """Detailed view of a user's ID verification for manual review."""
    user = User.query.get_or_404(user_id)
    audit_trail = IDVerificationAudit.query.filter_by(user_id=user.id).order_by(IDVerificationAudit.created_at.desc()).all()

    # If GET → show review page
    if request.method == "GET":
        # Mark as in_review when an admin opens the review page
        if user.manual_review_status == "pending":
            user.manual_review_status = "in_review"
            user.manual_reviewed_by = current_user.id
            user.manual_reviewed_at = datetime.now(timezone.utc)
            db.session.commit()

        return render_template("admin_id_review_detail.html", user=user, audit_trail=audit_trail)

    # If POST → handle admin decision (approve/reject)
    action = request.form.get("action")
    reason = request.form.get("reason", "").strip() or "No reason provided"

    if action == "approve":
        user.is_verified = True
        user.manual_review_required = False
        user.manual_review_status = "approved"
        user.manual_reviewed_by = current_user.id
        user.manual_reviewed_at = datetime.now(timezone.utc)

        # Log to audit table
        audit = IDVerificationAudit(
            user_id=user.id,
            verification_type="manual",
            decision="approved",
            decision_reason=reason[:200],
            reviewer_id=current_user.id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"✅ ID for {user.username} approved successfully.", "success")
        return redirect(url_for("admin_id_reviews"))

    elif action == "reject":
        user.is_verified = False
        user.manual_review_required = False
        user.manual_review_status = "rejected"
        user.manual_reviewed_by = current_user.id
        user.manual_reviewed_at = datetime.now(timezone.utc)

        # Log rejection reason
        audit = IDVerificationAudit(
            user_id=user.id,
            verification_type="manual",
            decision="rejected",
            decision_reason=reason[:200],
            reviewer_id=current_user.id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"❌ ID for {user.username} rejected. Reason: {reason}", "danger")
        return redirect(url_for("admin_id_reviews"))

    else:
        flash("⚠️ Invalid action.", "warning")
        return redirect(url_for("admin_id_review_detail", user_id=user.id))


@app.route("/admin/approve_id/<int:user_id>", methods=["POST"])
@login_required
@require_role("admin")
def admin_approve_id(user_id):
    """Approve an ID verification after manual review"""
    user = User.query.get_or_404(user_id)
    admin_notes = request.form.get("admin_notes", "")
    
    # Update user status
    user.is_verified = True
    user.manual_review_status = "approved"
    user.manual_reviewed_by = current_user.id
    user.manual_reviewed_at = datetime.now(timezone.utc)
    user.manual_review_notes = admin_notes
    
    # Create audit entry
    audit_entry = IDVerificationAudit(
        user_id=user.id,
        verification_type="manual",
        confidence_score=user.id_confidence_score,
        content_score=user.id_content_score,
        integrity_score=user.id_integrity_score,
        quality_score=user.id_quality_score,
        face_score=user.id_face_score,
        extracted_fields=user.id_fields_extracted,
        validation_reasons=user.id_validation_reasons,
        integrity_issues=user.id_integrity_issues,
        decision="verified",
        decision_reason=f"Approved by admin: {admin_notes[:100]}",
        reviewed_by=current_user.id,
        reviewed_at=datetime.now(timezone.utc),
        notes=admin_notes
    )
    db.session.add(audit_entry)
    db.session.commit()
    
    flash(f"✅ ID approved for user {user.username or user.email}.", "success")
    return redirect(url_for("admin_id_reviews"))

from flask import render_template, abort
from flask_login import current_user


@app.route("/admin/reject_id/<int:user_id>", methods=["POST"])
@login_required
@require_role("admin")
def admin_reject_id(user_id):
    """Reject an ID verification after manual review"""
    user = User.query.get_or_404(user_id)
    admin_notes = request.form.get("admin_notes", "")
    rejection_reason = request.form.get("rejection_reason", "Manual review rejection")
    
    # Update user status
    user.is_verified = False
    user.manual_review_status = "rejected"
    user.manual_reviewed_by = current_user.id
    user.manual_reviewed_at = datetime.now(timezone.utc)
    user.manual_review_notes = admin_notes
    
    # Create audit entry
    audit_entry = IDVerificationAudit(
        user_id=user.id,
        verification_type="manual",
        confidence_score=user.id_confidence_score,
        content_score=user.id_content_score,
        integrity_score=user.id_integrity_score,
        quality_score=user.id_quality_score,
        face_score=user.id_face_score,
        extracted_fields=user.id_fields_extracted,
        validation_reasons=user.id_validation_reasons,
        integrity_issues=user.id_integrity_issues,
        decision="rejected",
        decision_reason=rejection_reason,
        reviewed_by=current_user.id,
        reviewed_at=datetime.now(timezone.utc),
        notes=admin_notes
    )
    db.session.add(audit_entry)
    db.session.commit()
    
    flash(f"❌ ID rejected for user {user.username or user.email}. Reason: {rejection_reason}", "warning")
    return redirect(url_for("admin_id_reviews"))


@app.route("/admin/request_resubmission/<int:user_id>", methods=["POST"])
@login_required
@require_role("admin")
def admin_request_resubmission(user_id):
    """Request user to resubmit ID with specific instructions"""
    user = User.query.get_or_404(user_id)
    resubmission_notes = request.form.get("resubmission_notes", "")

    # Update user status for resubmission
    user.manual_review_status = "pending"
    user.manual_review_notes = f"Resubmission requested: {resubmission_notes}"
    user.id_retry_count = max(0, user.id_retry_count - 1)  # Allow one more attempt

    # Create audit entry
    audit_entry = IDVerificationAudit(
        user_id=user.id,
        verification_type="manual",
        confidence_score=user.id_confidence_score,
        content_score=user.id_content_score,
        integrity_score=user.id_integrity_score,
        quality_score=user.id_quality_score,
        face_score=user.id_face_score,
        extracted_fields=user.id_fields_extracted,
        validation_reasons=user.id_validation_reasons,
        integrity_issues=user.id_integrity_issues,
        decision="pending",
        decision_reason=f"Resubmission requested: {resubmission_notes[:100]}",
        reviewed_by=current_user.id,
        reviewed_at=datetime.now(timezone.utc),
        notes=resubmission_notes
    )

    db.session.add(audit_entry)
    db.session.commit()

    flash("Resubmission request sent to user successfully.", "info")
    return redirect(url_for("admin_id_reviews"))


    db.session.add(audit_entry)
    db.session.commit()

    flash(f"📋 Resubmission requested for {user.username}.", "info")
    flash("✅ The user can now re-upload their ID with your new instructions.", "success")

    return redirect(url_for("admin_id_review_detail", user_id=user.id))


# Legacy admin verify endpoints (keeping for backward compatibility)
@app.route("/admin/verifications")
@login_required
@require_role("admin")
def admin_verifications():
    """Admin panel showing all pending ID verifications"""
    pending_users = User.query.filter_by(verification_status="pending").order_by(User.last_id_upload_at.desc()).all()
    return render_template("admin_verifications.html", pending_users=pending_users)


@app.route("/admin/verify_seller/<int:seller_id>", methods=["POST"])
@login_required
@require_role("admin")
def verify_seller(seller_id):
    seller = User.query.filter_by(id=seller_id, role="seller").first_or_404()
    if not seller.id_document:
        flash("No ID uploaded.", "warning")
        return redirect(url_for("admin_verify_sellers"))
    seller.is_verified = True
    db.session.commit()
    flash("Seller verified.", "success")
    return redirect(url_for("admin_verify_sellers"))


@app.route("/admin/revoke_verification/<int:seller_id>", methods=["POST"])
@login_required
@require_role("admin")
def revoke_verification(seller_id):
    seller = User.query.filter_by(id=seller_id, role="seller").first_or_404()
    seller.is_verified = False
    db.session.commit()
    flash("Verification revoked.", "info")
    return redirect(url_for("admin_verify_sellers"))

# --------------------
# Error handlers & 
# --------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html", error="Page not found"), 404


@app.errorhandler(429)
def rate_limited(e):
    return render_template("429.html", error="Too many requests"), 429


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html", error="Server error"), 500

# Enhanced Service Management Routes
# create a new service
@app.route("/service/new", methods=["GET", "POST"])
@login_required
def create_service():
    # Check if user has verified ID before allowing access
    if not current_user.is_verified:
        if current_user.manual_review_status == "pending":
            flash("Your ID verification is still under review. Please wait for approval before posting services.", "warning")
        elif current_user.manual_review_status == "in_review":
            flash("Your ID verification is being reviewed. You will be notified once it's approved.", "info")
        else:
            flash("Please complete and verify your ID before posting services. Upload your National ID documents.", "warning")
        return redirect(url_for("upload_id"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0").strip() or "0"
        currency = request.form.get("currency", "KES").strip()
        quality = request.form.get("quality", "").strip()
        category = request.form.get("category", "").strip()
        # Handle multiple contact methods
        contact_methods = {}
        if request.form.get("phone"):
            contact_methods["phone"] = request.form.get("phone").strip()
        if request.form.get("email"):
            contact_methods["email"] = request.form.get("email").strip()
        if request.form.get("instagram"):
            contact_methods["instagram"] = request.form.get("instagram").strip()
        if request.form.get("facebook"):
            contact_methods["facebook"] = request.form.get("facebook").strip()
        if request.form.get("whatsapp"):
            contact_methods["whatsapp"] = request.form.get("whatsapp").strip()
        # Include the general contact field if provided
        contact = request.form.get("contact", "").strip()
        if contact:
            contact_methods["general"] = contact

        contact_info = json.dumps(contact_methods) if contact_methods else None

        # Basic validation
        if not title:
            flash("Title is required", "danger")
            return redirect(url_for("create_service"))

        # Handle images (multiple) - save to related tables
        image_files = request.files.getlist("media")
        print(f"🔍 DEBUG: Processing {len(image_files)} media files")

        # Create service with seller_id
        svc = Service(
            seller_id=current_user.id,
            title=title,
            description=description,
            price=Decimal(price),
            currency=currency,
            quality=quality,
            category=category,
            contact_info=contact_info,
            image_filenames=json.dumps([]),
            video_filenames=json.dumps([])
        )
        db.session.add(svc)
        db.session.commit()  # Commit to get service ID

        # Save media to related tables with authentication check
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        if not user_id:
            flash("Authentication error during media upload.", "danger")
        else:
            for f in image_files:
                if f and f.filename:
                    print(f"🔍 DEBUG: Processing file: {f.filename}")
                    ext = f.filename.rsplit(".", 1)[-1].lower()
                    try:
                        if ext in ALLOWED_IMAGE_EXTENSIONS:
                            fname = save_service_image(f, user_id)
                            print(f"✅ DEBUG: Image saved as: {fname}")
                            service_image = ServiceImage(service_id=svc.id, filename=fname)
                            db.session.add(service_image)
                            if len(svc.images) >= 50:  # Updated limit
                                break
                        elif ext in ALLOWED_VIDEO_EXTENSIONS:
                            fname = save_service_video(f, user_id)
                            print(f"✅ DEBUG: Video saved as: {fname}")
                            service_video = ServiceVideo(service_id=svc.id, filename=fname)
                            db.session.add(service_video)
                            if len(svc.videos) >= 20:  # Updated limit
                                break
                    except Exception as e:
                        print(f"❌ DEBUG: Upload failed for {f.filename}: {e}")
                        flash(f"Media upload skipped: {str(e)}", "warning")

        db.session.commit()
        print(f"🔍 DEBUG: Service created with {len(svc.images)} images and {len(svc.videos)} videos")
        flash("Service posted", "success")
        return redirect(url_for("service_view", id=svc.id))

    return render_template("service_form.html", action="create", service=None, max_images=MAX_IMAGE_COUNT)


# edit existing service
@app.route("/service/<int:id>/edit", methods=["GET","POST"])
@login_required
def edit_service(id):
    svc = Service.query.get_or_404(id)
    if svc.seller_id != current_user.id and current_user.role != "admin":
        flash("Not authorized", "danger")
        return redirect(url_for("service_view", id=id))

    if request.method == "POST":
        svc.title = request.form.get("title","").strip()
        svc.description = request.form.get("description","").strip()
        svc.price = Decimal(request.form.get("price","0").strip() or "0")
        svc.currency = request.form.get("currency","KES").strip()
        svc.quality = request.form.get("quality","").strip()
        svc.category = request.form.get("category","").strip()
        # Handle multiple contact methods
        contact_methods = {}
        if request.form.get("phone"):
            contact_methods["phone"] = request.form.get("phone").strip()
        if request.form.get("email"):
            contact_methods["email"] = request.form.get("email").strip()
        if request.form.get("instagram"):
            contact_methods["instagram"] = request.form.get("instagram").strip()
        if request.form.get("facebook"):
            contact_methods["facebook"] = request.form.get("facebook").strip()
        if request.form.get("whatsapp"):
            contact_methods["whatsapp"] = request.form.get("whatsapp").strip()

        svc.contact_info = json.dumps(contact_methods) if contact_methods else None

        # Handle media updates using related tables

        # remove images that user marked for deletion
        removes = request.form.getlist("remove_images")
        if removes:
            for r in removes:
                # Find and delete the ServiceImage record
                service_image = ServiceImage.query.filter_by(service_id=svc.id, filename=r).first()
                if service_image:
                    db.session.delete(service_image)
                    try:
                        os.remove(os.path.join(SERVICE_IMG_FOLDER, r))
                    except Exception:
                        pass

        # remove videos that user marked for deletion
        remove_videos = request.form.getlist("remove_videos")
        if remove_videos:
            for r in remove_videos:
                # Find and delete the ServiceVideo record
                service_video = ServiceVideo.query.filter_by(service_id=svc.id, filename=r).first()
                if service_video:
                    db.session.delete(service_video)
                    try:
                        os.remove(os.path.join(SERVICE_IMG_FOLDER, r))
                    except Exception:
                        pass

        # add newly uploaded media
        files = request.files.getlist("media")
        for f in files:
            if f and f.filename:
                ext = f.filename.rsplit(".", 1)[-1].lower()
                try:
                    if ext in ALLOWED_IMAGE_EXTENSIONS and len(svc.images) < 50:
                        fname = save_service_image(f, current_user.id)
                        # Create ServiceImage record
                        service_image = ServiceImage(service_id=svc.id, filename=fname)
                        db.session.add(service_image)
                    elif ext in ALLOWED_VIDEO_EXTENSIONS and len(svc.videos) < 20:
                        fname = save_service_video(f, current_user.id)
                        # Create ServiceVideo record
                        service_video = ServiceVideo(service_id=svc.id, filename=fname)
                        db.session.add(service_video)
                except Exception as e:
                    flash(f"Media skipped: {e}", "warning")

        db.session.commit()
        flash("Service updated", "success")
        return redirect(url_for("service_view", id=svc.id))

    # GET -> prefill form
    images = json.loads(svc.image_filenames or "[]")
    videos = json.loads(svc.video_filenames or "[]")
    return render_template("service_form.html", action="edit", service=svc, images=images, videos=videos, max_images=MAX_IMAGE_COUNT, max_videos=MAX_VIDEO_COUNT)

# view service
@app.route("/service/<int:id>")
def service_view(id):
    svc = Service.query.get_or_404(id)

    def load_media_list(raw_value, default=None):
        if default is None:
            default = []
        if not raw_value:
            return list(default)
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return parsed
            return list(default)
        except Exception as e:
            current_app.logger.debug("Failed to parse media JSON for service %s: %s", id, e)
            return list(default)

    images = load_media_list(svc.image_filenames, [])
    videos = load_media_list(svc.video_filenames, [])

    # Use configured video folder if present, otherwise fall back to image folder
    video_folder = current_app.config.get("SERVICE_VIDEO_FOLDER", SERVICE_IMG_FOLDER)

    current_app.logger.debug("service_view: Service %s loaded (images=%d, videos=%d)", id, len(images), len(videos))
    current_app.logger.debug("service_view: Raw image field: %s", svc.image_filenames)
    current_app.logger.debug("service_view: Raw video field: %s", svc.video_filenames)

    # Check if files exist safely
    for img in images:
        try:
            img_path = safe_join(SERVICE_IMG_FOLDER, img)
        except Exception:
            current_app.logger.debug("service_view: Image path unsafe or invalid: %s", img)
            img_path = None
        exists = os.path.exists(img_path) if img_path else False
        current_app.logger.debug("service_view: Image %s exists: %s", img, exists)

    for video in videos:
        try:
            video_path = safe_join(video_folder, video)
        except Exception:
            current_app.logger.debug("service_view: Video path unsafe or invalid: %s", video)
            video_path = None
        exists = os.path.exists(video_path) if video_path else False
        current_app.logger.debug("service_view: Video %s exists: %s", video, exists)

    return render_template("service_view.html", service=svc, images=images, videos=videos)

# delete service
@app.route("/service/<int:id>/delete", methods=["POST"])
@login_required
def delete_service(id):
    svc = Service.query.get_or_404(id)
    if svc.seller_id != current_user.id and current_user.role != "admin":
        flash("Not authorized", "danger")
        return redirect(url_for("service_view", id=id))

    # delete associated images and videos from related tables
    # The cascade="all, delete-orphan" will automatically delete related ServiceImage and ServiceVideo records
    # But we still need to delete the actual files
    for img in svc.images:
        try:
            try:
                img_path = safe_join(SERVICE_IMG_FOLDER, img.filename)
            except Exception:
                current_app.logger.debug("delete_service: Unsafe image filename for service %s: %s", id, img.filename)
                img_path = None
            if img_path and os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except Exception as e:
                    current_app.logger.debug("delete_service: Failed to remove image %s: %s", img_path, e)
        except Exception:
            pass

    video_folder = current_app.config.get("SERVICE_VIDEO_FOLDER", SERVICE_VIDEO_FOLDER)
    for vid in svc.videos:
        try:
            try:
                vid_path = safe_join(video_folder, vid.filename)
            except Exception:
                current_app.logger.debug("delete_service: Unsafe video filename for service %s: %s", id, vid.filename)
                vid_path = None
            if vid_path and os.path.exists(vid_path):
                try:
                    os.remove(vid_path)
                except Exception as e:
                    current_app.logger.debug("delete_service: Failed to remove video %s: %s", vid_path, e)
        except Exception:
            pass

    db.session.delete(svc)
    db.session.commit()
    flash("Service deleted", "success")
    return redirect(url_for("dashboard"))



# Legacy post_service route for backward compatibility
@app.route("/post_service", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per hour")
def post_service():
    # Check if user has verified ID before allowing access
    if not current_user.is_verified:
        if current_user.manual_review_status == "pending":
            flash("Your ID verification is still under review. Please wait for approval before posting services.", "warning")
        elif current_user.manual_review_status == "in_review":
            flash("Your ID verification is being reviewed. You will be notified once it's approved.", "info")
        else:
            flash("Please complete and verify your ID before posting services. Upload your National ID documents.", "warning")
        return redirect(url_for("upload_id"))

    form = ServiceForm()
    if form.validate_on_submit():
        title = form.title.data.strip()
        description = form.description.data.strip()
        # Handle multiple contact methods
        contact_methods = {}
        if request.form.get("phone"):
            contact_methods["phone"] = request.form.get("phone").strip()
        if request.form.get("email"):
            contact_methods["email"] = request.form.get("email").strip()
        if request.form.get("instagram"):
            contact_methods["instagram"] = request.form.get("instagram").strip()
        if request.form.get("facebook"):
            contact_methods["facebook"] = request.form.get("facebook").strip()
        if request.form.get("whatsapp"):
            contact_methods["whatsapp"] = request.form.get("whatsapp").strip()

        try:
            price = float(form.price.data)
        except Exception:
            flash("Invalid price.", "danger")
            return render_template("post_service.html", form=form)

        file = request.files.get("image")
        filename = None
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_IMAGE_EXT:
                flash("Invalid image file type.", "danger")
                return render_template("post_service.html", form=form)
            safe = secure_filename(file.filename)
            filename = f"{int(datetime.now().timestamp())}_{safe}"
            file.save(os.path.join(SERVICE_IMG_FOLDER, filename))

        svc = Service(
            user_id=current_user.id,
            seller_id=current_user.id,
            title=title,
            description=description,
            price=price,
            currency='KES',
            contact_info=json.dumps(contact_methods) if contact_methods else None,
            image_filenames=json.dumps([filename]) if filename else None
        )
        db.session.add(svc)
        db.session.commit()
        flash("Product posted successfully.", "success")
        return redirect(url_for("service_view", id=svc.id))

    return render_template("post_service.html", form=form)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # create a default admin if none exists
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        admin_pwd = os.environ.get("ADMIN_PWD", "adminpass")
        if not User.query.filter_by(role="admin").first():
            if not User.query.filter_by(email=admin_email).first():
                u = User(username="admin", email=admin_email, password=generate_password_hash(admin_pwd), role="admin")
                db.session.add(u)
                db.session.commit()
                print(f"Created default admin: {admin_email} (overwrite ADMIN_EMAIL / ADMIN_PWD env to change)")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
