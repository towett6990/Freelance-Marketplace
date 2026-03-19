import os
import io
import json
import logging
import warnings
from datetime import datetime, timedelta, timezone
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_from_directory, session, jsonify, current_app
)

# Suppress noisy eventlet warnings
logging.getLogger('eventlet').setLevel(logging.ERROR)
logging.getLogger('eventlet.wsgi').setLevel(logging.ERROR)

# ── Structured logging setup ─────────────────────────────────────────────────
import logging.handlers

def setup_logging(app):
    log_level = logging.DEBUG if os.environ.get('FLASK_ENV') != 'production' else logging.INFO
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # File handler with rotation (10MB max, keep 5 backups)
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        'logs/freelancinghub.log', maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    # Error-only log
    error_handler = logging.handlers.RotatingFileHandler(
        'logs/errors.log', maxBytes=5*1024*1024, backupCount=3
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    # M-Pesa specific log
    mpesa_handler = logging.handlers.RotatingFileHandler(
        'logs/mpesa.log', maxBytes=5*1024*1024, backupCount=5
    )
    mpesa_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(log_level)
    logging.getLogger('mpesa').addHandler(mpesa_handler)
warnings.filterwarnings('ignore', message='.*Connection.*')
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
from flask_wtf.csrf import CSRFProtect
from flask_limiter.util import get_remote_address
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Mail, Message as MailMessage
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv
load_dotenv()
from decimal import Decimal
import pytesseract
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
import cv2
import face_recognition
import numpy as np
import uuid
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Import db and models from models.py - this is the single source of truth
from models import db
from models import (
    User, IDVerificationAudit, ServiceImage, ServiceVideo, Service, Order,
    Payment, Payout, Message, Location, Call, MessageNotification, Conversation,
    get_or_create_conversation, Review, Category, Question, Notification
)
from models_extra import (
    ServicePackage, CustomOffer, ServiceView, Favorite, SellerLevel
)
from features_routes import features_bp
USE_MOCK_VISION = os.environ.get("USE_MOCK_VISION", "False").lower() == "true"
KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CLOUD_VISION_API_KEY = os.getenv("GOOGLE_CLOUD_VISION_API_KEY")

# Import verification system routes
from verification_system import register_verification_routes

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


# PHASE 2 FIX: File content validation using magic bytes
def validate_file_content(file_storage, allowed_mimes=None):
    """
    Validate actual file content using magic bytes, not just extension.
    Prevents upload of malicious files with fake extensions.
    """
    if allowed_mimes is None:
        allowed_mimes = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    
    # Read first 2048 bytes for magic byte detection
    file_storage.stream.seek(0)
    header = file_storage.stream.read(2048)
    file_storage.stream.seek(0)
    
    if len(header) < 4:
        raise ValueError("File too small to validate")
    
    # Check magic bytes for common image formats
    # JPEG: FF D8 FF
    # PNG: 89 50 4E 47
    # GIF: 47 49 46 38
    # WebP: 52 49 46 46 ... 57 45 42 50
    
    is_jpeg = header[:3] == b'\xff\xd8\xff'
    is_png = header[:4] == b'\x89PNG'
    is_gif = header[:4] == b'GIF8'
    is_webp = header[:4] == b'RIFF' and header[8:12] == b'WEBP'
    
    mime_type = None
    if is_jpeg:
        mime_type = 'image/jpeg'
    elif is_png:
        mime_type = 'image/png'
    elif is_gif:
        mime_type = 'image/gif'
    elif is_webp:
        mime_type = 'image/webp'
    
    if mime_type is None:
        raise ValueError(f"Invalid file content type. Allowed: {allowed_mimes}")
    
    if mime_type not in allowed_mimes:
        raise ValueError(f"File type {mime_type} not allowed. Allowed: {allowed_mimes}")
    
    return True


def save_service_image(file_storage, user_id, max_width=1600):
    """
    Validates and saves an uploaded image.
    Returns filename (relative to static/uploads/services).
    Converts and resizes large images to JPEG (keeps png/webp if originally png/webp).
    """
    try:
        # PHASE 2 FIX: Validate file content before processing
        validate_file_content(file_storage, {'image/jpeg', 'image/png', 'image/gif', 'image/webp'})
        
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
setup_logging(app)

# ─────────────────────────────────────────
# SECRET KEY
# ─────────────────────────────────────────
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or (_ for _ in ()).throw(RuntimeError("SECRET_KEY env var not set"))
basedir = os.path.abspath(os.path.dirname(__file__))

# ─────────────────────────────────────────
# DATABASE — MySQL (prod) / SQLite (dev fallback)
# ─────────────────────────────────────────
_db_url = os.environ.get("DATABASE_URL")

if not _db_url:
    # Build MySQL URL from individual env vars if set
    _mysql_user = os.environ.get("MYSQL_USER")
    _mysql_pass = os.environ.get("MYSQL_PASSWORD")
    _mysql_host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    _mysql_port = os.environ.get("MYSQL_PORT", "3306")
    _mysql_db   = os.environ.get("MYSQL_DATABASE", "freelance_marketplace")
    if _mysql_user and _mysql_pass:
        _db_url = f"mysql+pymysql://{_mysql_user}:{_mysql_pass}@{_mysql_host}:{_mysql_port}/{_mysql_db}?charset=utf8mb4"
    else:
        # Dev fallback — SQLite
        _db_url = "sqlite:///" + os.path.join(basedir, "database.db")

app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Connection pool — critical for MySQL on cloud (avoids "connection gone away")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle":    1800,   # recycle connections every 30 min
    "pool_pre_ping":   True,   # test connection before use
    "pool_size":       10,     # base pool size
    "max_overflow":    20,     # allow 20 extra connections under burst
    "pool_timeout":    30,     # wait up to 30s for a free connection
}

app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["ID_FOLDER"]          = ID_FOLDER
app.config["AVATAR_FOLDER"]      = AVATAR_FOLDER
app.config["CHAT_UPLOAD_FOLDER"] = CHAT_UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

# ─────────────────────────────────────────
# MAIL
# ─────────────────────────────────────────
app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER", "")
app.config["MAIL_PORT"]           = int(os.environ.get("MAIL_PORT") or 0)
app.config["MAIL_USE_TLS"]        = os.environ.get("MAIL_USE_TLS", "False") == "True"
app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@example.com")

# ─────────────────────────────────────────
# CELERY (optional — background jobs)
# ─────────────────────────────────────────
_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
app.config["CELERY_BROKER_URL"]  = _redis_url
app.config["CELERY_RESULT_BACKEND"] = _redis_url

# ─────────────────────────────────────────
# EXTENSIONS
# ─────────────────────────────────────────
db.init_app(app)
migrate = Migrate(app, db)

# Rate limiter — use Redis in prod, memory in dev
_limiter_storage = os.environ.get("REDIS_URL", "memory://")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300 per hour", "60 per minute"],
    storage_uri=_limiter_storage,
)
limiter.init_app(app)
csrf = CSRFProtect(app)

# PHASE 3 FIX: Add secure session configuration
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB global max (videos)
# Per-type limits enforced in save_service_image/save_service_video (see MAX_IMAGE_SIZE_MB, MAX_VIDEO_SIZE_MB)
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

login_manager = LoginManager(app)
login_manager.login_view = "login"

mail = Mail(app)

def send_order_email(to, subject, heading, body_html, order_id, cta_text="View Order"):
    """Send a branded order notification email."""
    try:
        order_url = url_for("order_detail", order_id=order_id, _external=True)
        msg = MailMessage(
            subject=f"FreelancingHub — {subject}",
            recipients=[to],
            html=f"""<div style="font-family:sans-serif;max-width:500px;margin:auto;background:#0f1429;color:#e2e8f0;padding:2rem;border-radius:16px">
<h2 style="color:#00ffc8;margin-top:0">{heading}</h2>
<p style="color:#94a3b8;line-height:1.6">{body_html}</p>
<a href="{order_url}" style="display:inline-block;margin-top:1.5rem;padding:.75rem 1.5rem;background:#00ffc8;color:#0f1429;font-weight:700;border-radius:8px;text-decoration:none">{cta_text}</a>
<p style="color:#475569;font-size:.78rem;margin-top:2rem">FreelancingHub &mdash; Kenya Freelance Marketplace</p>
</div>"""
        )
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Order email failed (order #{order_id}): {e}")
ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])
# SECURITY FIX: Use environment variable for CORS origins instead of wildcard
_env = os.environ.get("FLASK_ENV", "development")
if _env == "production":
    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5000")
else:
    cors_origins = "*"  # Allow all origins in development
socketio = SocketIO(app, cors_allowed_origins=cors_origins, async_mode="threading")
@app.route('/api/review/add', methods=['POST'])
@login_required
@limiter.limit('5 per minute; 20 per hour')
def add_review():
    """Add a new review for a service"""
    try:
        data = request.get_json()
        
        service_id = data.get('service_id')
        overall_rating = data.get('overall_rating')
        communication_rating = data.get('communication_rating')
        quality_rating = data.get('quality_rating')
        timeliness_rating = data.get('timeliness_rating')
        comment = (data.get('comment') or '').strip()  # ✅ FIX: Handle None
        
        # Validate required fields
        if not service_id or not overall_rating:
            return jsonify({'error': 'Missing service_id or overall_rating'}), 400
        
        # Get service
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        # Check: Can't review as the seller of this service (other roles allowed)
        pass  # role check removed — any authenticated non-owner can review
        
        # Check: Can't review own service
        if service.seller_id == current_user.id:
            return jsonify({'error': 'Cannot review your own service'}), 403
        
        # Check: Already reviewed?
        existing = Review.query.filter_by(
            service_id=service_id,
            buyer_id=current_user.id
        ).first()
        
        if existing:
            return jsonify({'error': 'You have already reviewed this service'}), 400
        
        # Validate ratings (1-5)
        if not (1 <= overall_rating <= 5):
            return jsonify({'error': 'Overall rating must be between 1 and 5'}), 400
        
        if communication_rating and not (1 <= communication_rating <= 5):
            return jsonify({'error': 'Communication rating must be between 1 and 5'}), 400
        
        if quality_rating and not (1 <= quality_rating <= 5):
            return jsonify({'error': 'Quality rating must be between 1 and 5'}), 400
        
        if timeliness_rating and not (1 <= timeliness_rating <= 5):
            return jsonify({'error': 'Timeliness rating must be between 1 and 5'}), 400
        
        # Create review
        review = Review(
            service_id=service_id,
            buyer_id=current_user.id,
            seller_id=service.seller_id,
            overall_rating=overall_rating,
            communication_rating=communication_rating,
            quality_rating=quality_rating,
            timeliness_rating=timeliness_rating,
            comment=comment
        )
        
        db.session.add(review)
        db.session.commit()

        # Notify seller of new review
        notify(
            user_id=service.seller_id,
            type='review',
            title=f'{current_user.display_name()} left you a {overall_rating}★ review',
            body=comment[:120] + ('…' if comment and len(comment) > 120 else '') if comment else None,
            link=f'/service/{service_id}',
            actor_id=current_user.id,
            service_id=service_id
        )

        app.logger.info(f'Review added: service={service_id}, buyer={current_user.id}, rating={overall_rating}')
        
        return jsonify({
            'success': True,
            'message': 'Review added successfully',
            'review': review.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error adding review: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/review/<int:review_id>', methods=['GET'])
def get_review(review_id):
    """Get a single review"""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        return jsonify(review.to_dict()), 200
    except Exception as e:
        app.logger.error(f'Error getting review: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/review/service/<int:service_id>', methods=['GET'])
def get_service_reviews(service_id):
    """Get all reviews for a service with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        # Paginate reviews
        pagination = service.reviews.order_by(Review.created_at.desc()).paginate(
            page=page,
            per_page=per_page
        )
        
        reviews = [r.to_dict() for r in pagination.items]
        
        app.logger.info(f'Service reviews fetched: service={service_id}, count={len(reviews)}')
        
        return jsonify({
            'success': True,
            'reviews': reviews,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'average_rating': service.get_average_rating(),
            'review_count': service.get_review_count(),
            'detailed_ratings': service.get_detailed_ratings()
        }), 200
    
    except Exception as e:
        app.logger.error(f'Error getting service reviews: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/review/<int:review_id>/edit', methods=['PUT'])
@login_required
@limiter.limit('5 per minute; 20 per hour')
def edit_review(review_id):
    """Edit a review (only by author)"""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        # Check: Only buyer can edit their review
        if review.buyer_id != current_user.id and current_user.role != 'admin':
            return jsonify({'error': 'Not authorized to edit this review'}), 403
        
        data = request.get_json()
        
        # Update fields if provided
        if 'overall_rating' in data:
            if not (1 <= data['overall_rating'] <= 5):
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400
            review.overall_rating = data['overall_rating']
        
        if 'communication_rating' in data and data['communication_rating']:
            if not (1 <= data['communication_rating'] <= 5):
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400
            review.communication_rating = data['communication_rating']
        
        if 'quality_rating' in data and data['quality_rating']:
            if not (1 <= data['quality_rating'] <= 5):
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400
            review.quality_rating = data['quality_rating']
        
        if 'timeliness_rating' in data and data['timeliness_rating']:
            if not (1 <= data['timeliness_rating'] <= 5):
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400
            review.timeliness_rating = data['timeliness_rating']
        
        if 'comment' in data and data['comment']:
            review.comment = (data['comment'] or '').strip()
            
        
        db.session.commit()
        
        app.logger.info(f'Review edited: review_id={review_id}')
        
        return jsonify({
            'success': True,
            'message': 'Review updated successfully',
            'review': review.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error editing review: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/review/<int:review_id>/delete', methods=['DELETE'])
@login_required
@limiter.limit('5 per minute; 10 per hour')
def delete_review(review_id):
    """Delete a review (only by author or admin)"""
    try:
        review = Review.query.get(review_id)
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        # Check: Only buyer or admin can delete
        if review.buyer_id != current_user.id and current_user.role != 'admin':
            return jsonify({'error': 'Not authorized to delete this review'}), 403
        
        db.session.delete(review)
        db.session.commit()
        
        app.logger.info(f'Review deleted: review_id={review_id}')
        
        return jsonify({
            'success': True,
            'message': 'Review deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting review: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/service/<int:service_id>/can-review', methods=['GET'])
@login_required
def can_review_service(service_id):
    """Check if current user can review a service"""
    try:
        service = Service.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404
        
        # Check: Seller reviewing own service?
        # Any authenticated user can review another seller's service
        
        # Check: Own service?
        if service.seller_id == current_user.id:
            return jsonify({
                'can_review': False,
                'reason': 'Cannot review your own service'
            }), 200
        
        # Check: Already reviewed?
        existing = Review.query.filter_by(
            service_id=service_id,
            buyer_id=current_user.id
        ).first()
        
        if existing:
            return jsonify({
                'can_review': False,
                'reason': 'Already reviewed',
                'review_id': existing.id
            }), 200
        
        return jsonify({
            'can_review': True,
            'reason': 'Can review'
        }), 200
    
    except Exception as e:
        app.logger.error(f'Error checking review eligibility: {str(e)}')
        return jsonify({'error': str(e)}), 200


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


# FIX ISSUE 7: Add route for searching messages in a conversation
@app.route("/search_messages/<int:conversation_id>")
@login_required
def search_messages(conversation_id):
    """
    Search messages in a conversation by content.
    Query param 'q' contains the search term.
    """
    # Verify user is part of the conversation
    convo = Conversation.query.get_or_404(conversation_id)
    if current_user.id not in [convo.user1_id, convo.user2_id]:
        return jsonify({"error": "Not authorized"}), 403
    
    # Get search query
    search_term = request.args.get('q', '').strip()
    
    if not search_term:
        return jsonify({"results": []})
    
    # SECURITY FIX: Escape special LIKE characters to prevent SQL injection
    # Escape: % (any chars), _ (single char), \ (escape char)
    escaped_search = search_term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    
    # Filter messages by conversation_id and content containing search term
    # Use escape character so literal % and _ are matched
    results = Message.query.filter(
        Message.conversation_id == conversation_id,
        Message.content.ilike(f"%{escaped_search}%", escape='\\')
    ).order_by(Message.timestamp.desc()).all()
    
    # Return JSON with results
    messages_data = [{
        "id": msg.id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "is_read": msg.is_read
    } for msg in results]
    
    return jsonify({"results": messages_data})


# FIX ISSUE 8: Add route for deleting a conversation
@app.route("/conversation/<int:conversation_id>/delete", methods=["POST"])
@login_required
def delete_conversation(conversation_id):
    """
    Delete a conversation and all its messages (cascade delete).
    Only participants (user1_id or user2_id) can delete.
    """
    convo = Conversation.query.get_or_404(conversation_id)
    
    # Check user is in conversation
    if current_user.id not in [convo.user1_id, convo.user2_id]:
        return jsonify({"error": "Not authorized"}), 403
    
    # Delete conversation (cascade deletes messages due to relationship)
    db.session.delete(convo)
    db.session.commit()
    
    return jsonify({"success": True, "message": "Conversation deleted successfully"})


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
    submit = SubmitField("Create Account")


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


def render_custom_field_input(field_config, field_name=None, value=None):
    """
    Generate HTML input for a custom field based on its configuration.
    
    Args:
        field_config: Dict with field configuration (name, label, type, options, required)
        field_name: Optional override for field name
        value: Current value for the field
    
    Returns:
        HTML string for the input field
    """
    name = field_name or field_config.get('name', '')
    label = field_config.get('label', name)
    field_type = field_config.get('type', 'text')
    options = field_config.get('options', [])
    required = field_config.get('required', False)
    placeholder = field_config.get('placeholder', '')
    
    required_attr = 'required' if required else ''
    html = f'<div class="form-group mb-3">\n'
    html += f'  <label for="{name}" class="form-label">{label}</label>\n'
    
    if field_type == 'text':
        html += f'  <input type="text" class="form-control" id="{name}" name="{name}" '
        html += f'value="{value or ""}" placeholder="{placeholder}" {required_attr}>\n'
    
    elif field_type == 'number':
        html += f'  <input type="number" class="form-control" id="{name}" name="{name}" '
        html += f'value="{value or ""}" placeholder="{placeholder}" {required_attr}>\n'
    
    elif field_type == 'select':
        html += f'  <select class="form-select" id="{name}" name="{name}" {required_attr}>\n'
        html += f'    <option value="">Select {label}</option>\n'
        for opt in options:
            selected = 'selected' if value == opt else ''
            html += f'    <option value="{opt}" {selected}>{opt}</option>\n'
        html += f'  </select>\n'
    
    elif field_type == 'multi-select':
        # Checkbox group for multi-select
        values = value if isinstance(value, list) else []
        for opt in options:
            checked = 'checked' if opt in values else ''
            html += f'  <div class="form-check">\n'
            html += f'    <input class="form-check-input" type="checkbox" id="{name}_{opt}" '
            html += f'name="{name}" value="{opt}" {checked}>\n'
            html += f'    <label class="form-check-label" for="{name}_{opt}">{opt}</label>\n'
            html += f'  </div>\n'
    
    elif field_type == 'textarea':
        html += f'  <textarea class="form-control" id="{name}" name="{name}" '
        html += f'rows="3" placeholder="{placeholder}" {required_attr}>'
        html += f'{value or ""}</textarea>\n'
    
    else:
        # Default to text input
        html += f'  <input type="text" class="form-control" id="{name}" name="{name}" '
        html += f'value="{value or ""}" placeholder="{placeholder}" {required_attr}>\n'
    
    html += '</div>'
    return html


def chat_room_name(a_id, b_id):
    a, b = sorted([int(a_id), int(b_id)])
    return f"chat_{a}_{b}"


def unread_count_for_user(user_id):
    return Message.query.filter_by(receiver_id=user_id, is_read=False).count()


@app.route("/start_chat/<int:service_id>")
@login_required
def start_chat(service_id):
    """
    Initiate a chat with a service seller.
    Creates or retrieves an existing conversation and redirects to chat page.
    """
    # Get the service
    service = Service.query.get_or_404(service_id)
    
    # Prevent seller from chatting with themselves
    if service.seller_id == current_user.id:
        flash("You cannot chat with yourself.", "warning")
        return redirect(url_for("service_detail", service_id=service_id))
    
    # Get or create conversation with the seller
    seller = User.query.get(service.seller_id)
    if not seller:
        flash("Seller not found.", "danger")
        return redirect(url_for("service_detail", service_id=service_id))
    
    # Create or get existing conversation
    convo = get_or_create_conversation(current_user.id, seller.id)
    
    # Redirect to the chat page
    return redirect(url_for("chat", conversation_id=convo.id))

@app.route("/chat/<int:conversation_id>")
@login_required
def chat(conversation_id):
    convo = Conversation.query.get_or_404(conversation_id)

    # User must belong to the conversation
    if current_user.id not in [convo.user1_id, convo.user2_id]:
        flash("You are not part of this conversation.", "danger")
        return redirect(url_for("dashboard"))

    # Identify the other user
    other_user = convo.user1 if convo.user2_id == current_user.id else convo.user2

    # Load messages
    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp.asc()).all()

    # Room name for Socket.IO
    room = f"convo_{conversation_id}"

    return render_template(
    "chat.html",
    conversation=convo,
    other_user=other_user,
    messages=messages,
    room=room,
    can_send_offer=current_user.is_authenticated
)

@app.context_processor
def inject_globals():
    notif_count = 0
    chat_count  = 0
    if current_user.is_authenticated:
        notif_count = notif_count_for_user(current_user.id)
        chat_count  = unread_count_for_user(current_user.id)
    return {
        "current_year": datetime.now(timezone.utc).year,
        "unread_total": chat_count,
        "notif_count":  notif_count,
        "render_custom_field_input": render_custom_field_input
    }


# ============================================================
# NOTIFY HELPER — create a notification in one line anywhere
# ============================================================
def notify(user_id, type, title, body=None, link=None, actor_id=None, service_id=None):
    """Create a Notification record. Safe to call from any route — swallows errors."""
    try:
        n = Notification(
            user_id=user_id, type=type, title=title,
            body=body, link=link,
            actor_id=actor_id, service_id=service_id
        )
        db.session.add(n)
        db.session.commit()
    except Exception as e:
        app.logger.warning(f"notify() failed: {e}")


def notif_count_for_user(user_id):
    """Unread notification count for navbar badge."""
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


# --------------------
# Routes (core)
# --------------------
@app.route('/')
def index():
    services      = Service.query.order_by(Service.created_at.desc()).limit(8).all()
    categories    = Category.query.all()
    total_users   = User.query.count()
    total_services= Service.query.count()
    total_paid    = Payment.query.filter_by(status='completed').count()

    if current_user.is_authenticated:
        return render_template('home.html', services=services, user=current_user,
            categories=categories, total_users=total_users,
            total_services=total_services, total_paid=total_paid)
    else:
        return render_template('index.html', services=services,
            categories=categories, total_users=total_users,
            total_services=total_services, total_paid=total_paid)


# Folder to save uploaded IDs
app.config["ID_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "ids")
os.makedirs(app.config["ID_FOLDER"], exist_ok=True)

@app.route('/pay/<int:service_id>', methods=['GET'])
@login_required
def payment_page(service_id):
    """New payment page with two phone inputs"""
    service = Service.query.get_or_404(service_id)
    if service.seller_id == current_user.id:
        flash('You cannot purchase your own service', 'danger')
        return redirect(url_for('list_services'))
    return render_template('payment.html', service=service)


@app.route('/api/service/<int:service_id>', methods=['GET'])
def get_service_api(service_id):
    """API to load service details - Public endpoint"""
    try:
        service = Service.query.get_or_404(service_id)
        seller = db.session.get(User, service.seller_id)
        
        if not seller:
            return jsonify({'error': 'Service seller not found'}), 404
        
        response_data = {
            'id': service.id,
            'title': service.title or '',
            'description': service.description or '',
            'price': float(service.price) if service.price else 0,
            'category': service.category.name if service.category else (service.category_old or ''),
            'seller_name': seller.username or seller.email.split('@')[0] if seller.email else 'Unknown',
            'seller_phone': seller.mpesa_phone or '',
            'seller_id': seller.id
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/payment_status/<int:service_id>')
def check_payment_status(service_id):
    # simulate checking payment
    return jsonify({"status": "paid"})

# Callback route to receive MPESA confirmation
@app.route("/mpesa/callback", methods=["POST"])
@csrf.exempt
def mpesa_callback():
    """Handle M-Pesa payment callback and update payment status"""
    try:
        callback_data = request.get_json()
        app.logger.info("=" * 80)
        app.logger.info("📱 M-PESA CALLBACK RECEIVED")
        app.logger.info("=" * 80)
        app.logger.info(f"Callback Data: {callback_data}")
        
        if not callback_data:
            print("ERROR: No callback data received")
            return jsonify({"ResultCode": 1, "ResultDesc": "No data received"}), 400

        # PHASE 2 FIX: Validate M-Pesa callback authenticity
        from mpesa import validate_mpesa_callback
        is_valid, validation_result = validate_mpesa_callback(callback_data)
        
        if not is_valid:
            app.logger.warning(f"❌ Invalid M-Pesa callback: {validation_result}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Invalid callback"}), 400
        
        # Extract transaction details from validated callback
        body = callback_data.get("Body", {})
        stk_callback = body.get("stkCallback", {})
        
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc", "")
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        
        app.logger.info(f"Result Code: {result_code}, Description: {result_desc}")
        
        if result_code == 0:  # Success
            app.logger.info("✅ PAYMENT SUCCESSFUL")
            
            # Find payment by CheckoutRequestID
            payment = Payment.query.filter_by(checkout_request_id=checkout_request_id).first()
            
            if payment:
                # Get callback metadata
                callback_metadata = stk_callback.get("CallbackMetadata", {})
                item_list = callback_metadata.get("Item", [])
                
                mpesa_receipt = ""
                for item in item_list:
                    if item.get("Name") == "MpesaReceiptNumber":
                        mpesa_receipt = item.get("Value")
                        break
                
                app.logger.info(f"Receipt: {mpesa_receipt}")
                
                # Update payment
                payment.status = "completed"
                payment.mpesa_receipt_number = mpesa_receipt
                payment.payment_date = datetime.now(timezone.utc)
                db.session.commit()

                # Notify buyer — payment confirmed
                payment_link = f'/service/{payment.service_id}' if payment.service_id else '/dashboard'
                notify(
                    user_id=payment.buyer_id,
                    type='payment',
                    title='Payment confirmed!',
                    body=f'Your M-Pesa payment of KSh {payment.amount} was received. Receipt: {mpesa_receipt}',
                    link=payment_link,
                    service_id=payment.service_id
                )
                # Notify seller — money incoming
                notify(
                    user_id=payment.seller_id,
                    type='payment_received',
                    title=f'You received a payment of KSh {payment.amount}!',
                    body=f'M-Pesa receipt: {mpesa_receipt}',
                    link='/dashboard',
                    actor_id=payment.buyer_id,
                    service_id=payment.service_id
                )
                # Update linked order status if exists
                if payment.order_id:
                    from models import Order
                    order = Order.query.get(payment.order_id)
                    if order:
                        order.status = 'paid'
                        db.session.commit()

                app.logger.info(f"💾 PAYMENT #{payment.id} UPDATED TO COMPLETED")
                app.logger.info("=" * 80)
                
                return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200
            else:
                app.logger.warning(f"❌ Payment not found for CheckoutRequestID: {checkout_request_id}")
        else:
            app.logger.warning(f"❌ PAYMENT FAILED: {result_desc}")
        
        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200
        
    except Exception as e:
        app.logger.error(f"Callback error: {str(e)}", exc_info=True)
        return jsonify({"ResultCode": 1, "ResultDesc": "Error"}), 500

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
        payout_amount = int(float(order.amount) * (1 - platform_fee))

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
    # ── Params ──────────────────────────────────────────────
    q             = request.args.get("q", "").strip()
    category_slug = request.args.get("category", "").strip()
    min_price     = request.args.get("min_price", type=float)
    max_price     = request.args.get("max_price", type=float)
    min_rating    = request.args.get("min_rating", type=float)
    sort_by       = request.args.get("sort", "newest")
    page          = request.args.get("page", 1, type=int)
    per_page      = 12

    # ── Base query ──────────────────────────────────────────
    query = Service.query.options(
        db.selectinload(Service.images),
        db.selectinload(Service.seller),
        db.selectinload(Service.category),
    ).filter_by(is_active=True, is_sold=False)

    # Text search — title, description, seller username
    if q:
        query = query.filter(
            Service.title.ilike(f"%{q}%") |
            Service.description.ilike(f"%{q}%")
        )

    # Category filter
    active_category = None
    if category_slug:
        active_category = Category.query.filter_by(slug=category_slug).first()
        if active_category:
            query = query.filter(Service.category_id == active_category.id)

    # Price filter (DB level)
    if min_price is not None:
        query = query.filter(Service.price >= min_price)
    if max_price is not None:
        query = query.filter(Service.price <= max_price)

    # ── Sort (DB level where possible) ──────────────────────
    if sort_by == "price_low":
        query = query.order_by(Service.price.asc())
    elif sort_by == "price_high":
        query = query.order_by(Service.price.desc())
    elif sort_by == "oldest":
        query = query.order_by(Service.created_at.asc())
    else:  # newest (default)
        query = query.order_by(Service.created_at.desc())

    # Fetch all (needed for rating filter which is calculated)
    all_services = query.all()

    # Rating filter (post-query — computed field)
    if min_rating:
        all_services = [s for s in all_services if s.get_average_rating() >= min_rating]

    # Sort by rating post-query
    if sort_by == "rating":
        all_services = sorted(all_services, key=lambda s: s.get_average_rating(), reverse=True)

    # ── Pagination (manual) ─────────────────────────────────
    total        = len(all_services)
    total_pages  = max(1, (total + per_page - 1) // per_page)
    page         = max(1, min(page, total_pages))
    start        = (page - 1) * per_page
    services     = all_services[start:start + per_page]

    # ── Sidebar data ────────────────────────────────────────
    all_categories = Category.query.order_by(Category.name).all()

    # Price range across all services (for slider hints)
    price_range = db.session.query(
        db.func.min(Service.price),
        db.func.max(Service.price)
    ).first()
    price_min_global = float(price_range[0] or 0)
    price_max_global = float(price_range[1] or 100000)

    return render_template(
        "services.html",
        services=services,
        q=q,
        category_slug=category_slug,
        active_category=active_category,
        all_categories=all_categories,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        sort_by=sort_by,
        page=page,
        total_pages=total_pages,
        total=total,
        price_min_global=price_min_global,
        price_max_global=price_max_global,
    )


# ============================================================
# WEB DEVELOPMENT SERVICES ROUTE
# ============================================================
@app.route("/services/web-development")
def list_web_dev_services():
    """List Web Development services with category-specific filtering"""
    
    # Get Web Development category
    category = Category.query.filter_by(slug='web-development').first()
    if not category:
        flash("Web Development category not found.", "warning")
        return redirect(url_for("list_services"))
    
    # Get filter parameters
    q = request.args.get("q", type=str)
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    experience_level = request.args.get("experience_level", type=str)
    skills = request.args.getlist("skills")
    min_rating = request.args.get("min_rating", type=float)
    sort_by = request.args.get("sort", "newest")
    
    # Base query - only Web Development services
    query = Service.query.filter_by(category_id=category.id, is_active=True, is_sold=False).options(
        db.joinedload(Service.images),
        db.joinedload(Service.seller),
        db.joinedload(Service.category)
    )
    
    # Text search
    if q:
        query = query.filter(
            Service.title.ilike(f"%{q}%") |
            Service.description.ilike(f"%{q}%")
        )
    
    # Price filtering
    if min_price is not None:
        query = query.filter(Service.price >= min_price)
    if max_price is not None:
        query = query.filter(Service.price <= max_price)
    
    # Experience level filtering (stored in custom_data)
    if experience_level:
        query = query.filter(Service.custom_data['experience_level'].astext == experience_level)
    
    # Skills filtering (stored in custom_data as JSON array)
    if skills:
        for skill in skills:
            query = query.filter(Service.custom_data['skills'].cast(db.Text).ilike(f"%{skill}%"))
    
    # Rating filtering - we'll filter after query since it's a calculated field
    services = query.all()
    if min_rating:
        services = [s for s in services if s.get_average_rating() >= min_rating]
    
    # Sorting
    if sort_by == "price_low":
        services = sorted(services, key=lambda x: float(x.price) if x.price else 0)
    elif sort_by == "price_high":
        services = sorted(services, key=lambda x: float(x.price) if x.price else 0, reverse=True)
    elif sort_by == "rating":
        services = sorted(services, key=lambda x: x.get_average_rating(), reverse=True)
    elif sort_by == "newest":
        services = sorted(services, key=lambda x: x.created_at, reverse=True)
    
    # Get filter options from category
    filter_options = Category.get_all_filter_options('web-development')
    
    # Use freelancer-style template for web development services
    return render_template(
        "services_web_dev.html",
        services=services,
        category=category,
        q=q,
        min_price=min_price,
        max_price=max_price,
        experience_level=experience_level,
        skills=skills,
        min_rating=min_rating,
        sort_by=sort_by,
        filter_options=filter_options
    )


# ============================================================
# MULTI-CATEGORY LISTING ROUTES
# ============================================================

def _get_category_or_redirect(slug, flash_msg=None):
    """Return category object or None."""
    cat = Category.query.filter_by(slug=slug).first()
    if not cat and flash_msg:
        flash(flash_msg, "warning")
    return cat


def _filter_by_custom_field(services, field, value):
    """Case-insensitive equality filter on custom_data[field]."""
    if not value:
        return services
    return [s for s in services if str((s.custom_data or {}).get(field, '')).lower() == value.lower()]


def _filter_by_custom_contains(services, field, value):
    """Substring filter on custom_data[field]."""
    if not value:
        return services
    return [s for s in services if value.lower() in str((s.custom_data or {}).get(field, '')).lower()]


def _apply_price_and_sort(services, min_price, max_price, sort_by):
    if min_price:
        try:
            services = [s for s in services if float(s.price or 0) >= float(min_price)]
        except ValueError:
            pass
    if max_price:
        try:
            services = [s for s in services if float(s.price or 0) <= float(max_price)]
        except ValueError:
            pass
    if sort_by == 'price_low':
        services.sort(key=lambda s: float(s.price or 0))
    elif sort_by == 'price_high':
        services.sort(key=lambda s: float(s.price or 0), reverse=True)
    elif sort_by == 'rating':
        services.sort(key=lambda s: s.get_average_rating(), reverse=True)
    return services


def _base_cat_query(category):
    return (Service.query
            .filter_by(category_id=category.id)
            .options(
                db.selectinload(Service.seller),    # selectinload avoids N+1
                db.selectinload(Service.images),
                db.selectinload(Service.videos),
            )
            .order_by(Service.created_at.desc())
            .limit(500))    # safety cap — never load unlimited rows into Python


def _text_search_query(query, q):
    if q:
        query = query.filter(db.or_(
            Service.title.ilike(f'%{q}%'),
            Service.description.ilike(f'%{q}%')
        ))
    return query


# ── Pagination helper ──────────────────────────────────────────
def _paginate_list(items, page, per_page=12):
    """Paginate a Python list (for routes that filter in-memory)."""
    total      = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page        = max(1, min(page, total_pages))
    start       = (page - 1) * per_page
    return items[start:start + per_page], page, total_pages, total


# ── CAR SALES ────────────────────────────────────────────────

@app.route("/services/car-sales")
def list_car_sales():
    category = _get_category_or_redirect('car-sales',
        "Car Sales category not found. Run seed_all_categories.py")
    if not category:
        return redirect(url_for('index'))

    q            = request.args.get('q', '').strip()
    brand        = request.args.get('brand', '').strip()
    condition    = request.args.get('condition', '').strip()
    body_type    = request.args.get('body_type', '').strip()
    transmission = request.args.get('transmission', '').strip()
    fuel_type    = request.args.get('fuel_type', '').strip()
    min_year     = request.args.get('min_year', '').strip()
    max_year     = request.args.get('max_year', '').strip()
    max_mileage  = request.args.get('max_mileage', '').strip()
    min_price    = request.args.get('min_price', '').strip()
    max_price    = request.args.get('max_price', '').strip()
    sort_by      = request.args.get('sort', 'newest')

    services = _text_search_query(_base_cat_query(category), q).all()
    services = _filter_by_custom_field(services, 'brand', brand)
    services = _filter_by_custom_field(services, 'condition', condition)
    services = _filter_by_custom_field(services, 'body_type', body_type)
    services = _filter_by_custom_field(services, 'transmission', transmission)
    services = _filter_by_custom_field(services, 'fuel_type', fuel_type)

    if min_year:
        services = [s for s in services
                    if int((s.custom_data or {}).get('year', 0) or 0) >= int(min_year)]
    if max_year:
        services = [s for s in services
                    if int((s.custom_data or {}).get('year', 9999) or 9999) <= int(max_year)]
    if max_mileage:
        services = [s for s in services
                    if int((s.custom_data or {}).get('mileage', 0) or 0) <= int(max_mileage)]

    services = _apply_price_and_sort(services, min_price, max_price, sort_by)
    page = request.args.get('page', 1, type=int)
    services, page, total_pages, total = _paginate_list(services, page)

    return render_template('services_cars.html', category=category, services=services,
        q=q, brand=brand, condition=condition, body_type=body_type,
        transmission=transmission, fuel_type=fuel_type,
        min_year=min_year, max_year=max_year, max_mileage=max_mileage,
        min_price=min_price, max_price=max_price, sort_by=sort_by,
        page=page, total_pages=total_pages, total=total)


# ── REAL ESTATE ──────────────────────────────────────────────

@app.route("/services/real-estate")
def list_real_estate():
    category = _get_category_or_redirect('real-estate',
        "Real Estate category not found. Run seed_all_categories.py")
    if not category:
        return redirect(url_for('index'))

    q             = request.args.get('q', '').strip()
    property_type = request.args.get('property_type', '').strip()
    listing_type  = request.args.get('listing_type', '').strip()
    bedrooms      = request.args.get('bedrooms', '').strip()
    location_city = request.args.get('location_city', '').strip()
    furnished     = request.args.get('furnished', '').strip()
    min_price     = request.args.get('min_price', '').strip()
    max_price     = request.args.get('max_price', '').strip()
    sort_by       = request.args.get('sort', 'newest')

    services = _text_search_query(_base_cat_query(category), q).all()
    services = _filter_by_custom_field(services, 'property_type', property_type)
    services = _filter_by_custom_field(services, 'listing_type', listing_type)
    services = _filter_by_custom_field(services, 'bedrooms', bedrooms)
    services = _filter_by_custom_field(services, 'location_city', location_city)
    services = _filter_by_custom_field(services, 'furnished', furnished)
    services = _apply_price_and_sort(services, min_price, max_price, sort_by)
    page = request.args.get('page', 1, type=int)
    services, page, total_pages, total = _paginate_list(services, page)

    return render_template('services_realestate.html', category=category, services=services,
        q=q, property_type=property_type, listing_type=listing_type,
        bedrooms=bedrooms, location_city=location_city, furnished=furnished,
        min_price=min_price, max_price=max_price, sort_by=sort_by,
        page=page, total_pages=total_pages, total=total)


# ── ELECTRONICS ──────────────────────────────────────────────

@app.route("/services/electronics")
def list_electronics():
    category = _get_category_or_redirect('electronics',
        "Electronics category not found. Run seed_all_categories.py")
    if not category:
        return redirect(url_for('index'))

    q         = request.args.get('q', '').strip()
    brand     = request.args.get('brand', '').strip()
    device    = request.args.get('device', '').strip()
    condition = request.args.get('condition', '').strip()
    warranty  = request.args.get('warranty', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    sort_by   = request.args.get('sort', 'newest')

    services = _text_search_query(_base_cat_query(category), q).all()
    services = _filter_by_custom_field(services, 'brand', brand)
    services = _filter_by_custom_field(services, 'category', device)
    services = _filter_by_custom_field(services, 'condition', condition)
    services = _filter_by_custom_field(services, 'warranty', warranty)
    services = _apply_price_and_sort(services, min_price, max_price, sort_by)
    page = request.args.get('page', 1, type=int)
    services, page, total_pages, total = _paginate_list(services, page)

    return render_template('services_electronics.html', category=category, services=services,
        q=q, brand=brand, device=device, condition=condition, warranty=warranty,
        min_price=min_price, max_price=max_price, sort_by=sort_by,
        page=page, total_pages=total_pages, total=total)


# ── CLOTHING ─────────────────────────────────────────────────

@app.route("/services/clothing")
def list_clothing():
    category = _get_category_or_redirect('clothing',
        "Clothing category not found. Run seed_all_categories.py")
    if not category:
        return redirect(url_for('index'))

    q         = request.args.get('q', '').strip()
    brand     = request.args.get('brand', '').strip()
    cloth_cat = request.args.get('cloth_cat', '').strip()
    condition = request.args.get('condition', '').strip()
    size      = request.args.get('size', '').strip()
    gender    = request.args.get('gender', '').strip()
    material  = request.args.get('material', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    sort_by   = request.args.get('sort', 'newest')

    services = _text_search_query(_base_cat_query(category), q).all()
    services = _filter_by_custom_contains(services, 'brand', brand)
    services = _filter_by_custom_field(services, 'category', cloth_cat)
    services = _filter_by_custom_field(services, 'condition', condition)
    services = _filter_by_custom_field(services, 'size', size)
    services = _filter_by_custom_field(services, 'gender', gender)
    services = _filter_by_custom_field(services, 'material', material)
    services = _apply_price_and_sort(services, min_price, max_price, sort_by)
    page = request.args.get('page', 1, type=int)
    services, page, total_pages, total = _paginate_list(services, page)

    return render_template('services_clothing.html', category=category, services=services,
        q=q, brand=brand, cloth_cat=cloth_cat, condition=condition,
        size=size, gender=gender, material=material,
        min_price=min_price, max_price=max_price, sort_by=sort_by,
        page=page, total_pages=total_pages, total=total)


# ── OTHER ────────────────────────────────────────────────────

@app.route("/services/other")
def list_other():
    category = _get_category_or_redirect('other',
        "Other category not found. Run seed_all_categories.py")
    if not category:
        return redirect(url_for('index'))

    q         = request.args.get('q', '').strip()
    sub_cat   = request.args.get('sub_cat', '').strip()
    condition = request.args.get('condition', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    sort_by   = request.args.get('sort', 'newest')

    services = _text_search_query(_base_cat_query(category), q).all()
    services = _filter_by_custom_contains(services, 'sub_category', sub_cat)
    services = _filter_by_custom_field(services, 'condition', condition)
    services = _apply_price_and_sort(services, min_price, max_price, sort_by)
    page = request.args.get('page', 1, type=int)
    services, page, total_pages, total = _paginate_list(services, page)

    return render_template('services_other.html', category=category, services=services,
        q=q, sub_cat=sub_cat, condition=condition,
        min_price=min_price, max_price=max_price, sort_by=sort_by,
        page=page, total_pages=total_pages, total=total)


# ── FREELANCER CATEGORY HELPER ───────────────────────────────
# Shared logic for all freelancer-layout categories
# (mobile-design, ui-ux, writing, marketing, video,
#  photo, audio, data, translation, consulting)

def _list_freelancer_category(slug, template, skill_field='skills'):
    """Generic handler for freelancer-style service categories."""
    category = _get_category_or_redirect(slug,
        f"Category '{slug}' not found. Run seed_all_categories.py")
    if not category:
        return redirect(url_for('index'))

    q                = request.args.get('q', '').strip()
    experience_level = request.args.get('experience_level', '').strip()
    skill_filter     = request.args.get(skill_field, '').strip()
    availability     = request.args.get('availability', '').strip()
    min_price        = request.args.get('min_price', '').strip()
    max_price        = request.args.get('max_price', '').strip()
    sort_by          = request.args.get('sort', 'newest')

    services = _text_search_query(_base_cat_query(category), q).all()
    services = _filter_by_custom_field(services, 'experience_level', experience_level)
    services = _filter_by_custom_field(services, 'availability', availability)
    if skill_filter:
        services = _filter_by_custom_contains(services, skill_field, skill_filter)
    services = _apply_price_and_sort(services, min_price, max_price, sort_by)

    filter_options = Category.get_all_filter_options(slug)
    page = request.args.get('page', 1, type=int)
    services, page, total_pages, total = _paginate_list(services, page)

    return render_template(
        template,
        category=category,
        services=services,
        q=q,
        experience_level=experience_level,
        skill_filter=skill_filter,
        skill_field=skill_field,
        availability=availability,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        filter_options=filter_options,
        page=page,
        total_pages=total_pages,
        total=total,
    )


# ── MOBILE DESIGN ─────────────────────────────────────────────

@app.route("/services/mobile-design")
def list_mobile_design():
    return _list_freelancer_category('mobile-design', 'services_freelancer.html', 'skills')


# ── UI/UX DESIGN ──────────────────────────────────────────────

@app.route("/services/ui-ux")
def list_ui_ux():
    return _list_freelancer_category('ui-ux', 'services_freelancer.html', 'skills')


# ── WRITING ───────────────────────────────────────────────────

@app.route("/services/writing")
def list_writing():
    return _list_freelancer_category('writing', 'services_freelancer.html', 'writing_types')


# ── MARKETING ─────────────────────────────────────────────────

@app.route("/services/marketing")
def list_marketing():
    return _list_freelancer_category('marketing', 'services_freelancer.html', 'skills')


# ── VIDEO ─────────────────────────────────────────────────────

@app.route("/services/video")
def list_video():
    return _list_freelancer_category('video', 'services_freelancer.html', 'skills')


# ── PHOTO ─────────────────────────────────────────────────────

@app.route("/services/photo")
def list_photo():
    return _list_freelancer_category('photo', 'services_freelancer.html', 'specialisation')


# ── AUDIO ─────────────────────────────────────────────────────

@app.route("/services/audio")
def list_audio():
    return _list_freelancer_category('audio', 'services_freelancer.html', 'skills')


# ── DATA ──────────────────────────────────────────────────────

@app.route("/services/data")
def list_data():
    return _list_freelancer_category('data', 'services_freelancer.html', 'skills')


# ── TRANSLATION ───────────────────────────────────────────────

@app.route("/services/translation")
def list_translation():
    return _list_freelancer_category('translation', 'services_freelancer.html', 'language_pairs')


# ── CONSULTING ────────────────────────────────────────────────

@app.route("/services/consulting")
def list_consulting():
    return _list_freelancer_category('consulting', 'services_freelancer.html', 'specialisation')


# ============================================================
# API ENDPOINT FOR WEB DEV SERVICES
# ============================================================
@app.route('/api/services/web-dev')
def api_web_dev_services():
    """API endpoint for Web Development services"""
    
    # Get Web Development category
    category = Category.query.filter_by(slug='web-development').first()
    if not category:
        return jsonify({'error': 'Category not found'}), 404
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Get filter parameters
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    experience_level = request.args.get("experience_level", type=str)
    skills = request.args.getlist("skills")
    
    # Base query
    query = Service.query.filter_by(category_id=category.id).options(
        db.joinedload(Service.seller)
    )
    
    # Apply filters
    if min_price:
        query = query.filter(Service.price >= min_price)
    if max_price:
        query = query.filter(Service.price <= max_price)
    if experience_level:
        query = query.filter(Service.custom_data['experience_level'].astext == experience_level)
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Build response
    services_data = []
    for service in pagination.items:
        services_data.append({
            'id': service.id,
            'title': service.title,
            'description': service.description,
            'price': float(service.price) if service.price else 0,
            'currency': service.currency,
            'average_rating': service.get_average_rating(),
            'review_count': service.get_review_count(),
            'seller': {
                'id': service.seller.id,
                'username': service.seller.username,
                'avatar': service.seller.avatar
            } if service.seller else None,
            'custom_data': service.custom_data,
            'created_at': service.created_at.isoformat() if service.created_at else None
        })
    
    return jsonify({
        'success': True,
        'services': services_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'category': category.to_dict()
    }), 200


# ============================================================
# API ENDPOINT FOR CATEGORY CONFIGURATION
# ============================================================
@app.route('/api/category/<int:category_id>', methods=['GET'])
def api_category_config(category_id):
    """API endpoint to get category configuration including custom fields"""
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        
        return jsonify({
            'success': True,
            'category': category.to_dict()
        }), 200
    except Exception as e:
        app.logger.error(f'Error fetching category config: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/category/slug/<string:slug>', methods=['GET'])
def api_category_by_slug(slug):
    """API endpoint to get category configuration by slug"""
    try:
        category = Category.query.filter_by(slug=slug).first()
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        
        return jsonify({
            'success': True,
            'category': category.to_dict()
        }), 200
    except Exception as e:
        app.logger.error(f'Error fetching category config: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route("/service/<int:service_id>")
def service_detail(service_id):
    """Dispatch to the correct detail template based on category layout_type."""
    svc = Service.query.options(
        db.joinedload(Service.seller),
        db.joinedload(Service.images),
        db.joinedload(Service.videos),
        db.joinedload(Service.category)
    ).get_or_404(service_id)

    related = []
    if svc.category_id:
        related = Service.query.filter(
            Service.category_id == svc.category_id,
            Service.id != svc.id
        ).limit(4).all()

    category = svc.category

    TEMPLATE_MAP = {
        'freelancer': 'service_detail_freelancer.html',
        'product':    'service_detail_product.html',
        'property':   'service_detail_property.html',
        'generic':    'service_detail_generic.html',
    }
    layout   = category.layout_type if category else 'generic'
    template = TEMPLATE_MAP.get(layout, 'service_detail_generic.html')

    questions = (Question.query
                 .filter_by(service_id=svc.id, is_public=True)
                 .order_by(Question.created_at.desc())
                 .all())

    # Seller avg response time (hours) across all answered questions
    answered = [q for q in questions if q.answered_at]
    if answered:
        avg_hrs = round(sum(q.response_time_hours for q in answered) / len(answered), 1)
    else:
        avg_hrs = None

    # Track view (async-safe, deduped per hour)
    try:
        import hashlib as _hl
        ip   = request.remote_addr or ''
        ih   = _hl.md5(ip.encode()).hexdigest()
        uid  = current_user.id if current_user.is_authenticated else None
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        _since = _dt.now(_tz.utc) - _td(hours=1)
        _exists = ServiceView.query.filter(
            ServiceView.service_id == svc.id,
            ServiceView.viewed_at  >= _since,
            ServiceView.ip_hash    == ih
        ).first()
        if not _exists:
            db.session.add(ServiceView(service_id=svc.id, viewer_id=uid, ip_hash=ih))
            db.session.commit()
    except Exception:
        db.session.rollback()

    # Favorite status for current user
    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = Favorite.query.filter_by(
            user_id=current_user.id, service_id=svc.id).first() is not None

    # Packages
    packages = ServicePackage.query.filter_by(service_id=svc.id, is_active=True).all()

    return render_template(template, service=svc, related=related,
                           category=category, questions=questions,
                           avg_response_hours=avg_hrs,
                           is_favorited=is_favorited,
                           packages=packages)


# ============================================================
# Q&A ROUTES
# ============================================================

@app.route("/service/<int:service_id>/question", methods=["POST"])
@login_required
def ask_question(service_id):
    """Buyer posts a question on a service page."""
    svc = Service.query.get_or_404(service_id)

    # Sellers cannot ask questions on their own listing
    if current_user.id == svc.seller_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'You cannot ask questions on your own listing.'}), 403
        flash("You cannot ask questions on your own listing.", "warning")
        return redirect(url_for('service_detail', service_id=service_id))

    body = (request.form.get('body') or request.json.get('body', '') if request.is_json else request.form.get('body', '')).strip()
    if not body:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Question cannot be empty.'}), 400
        flash("Question cannot be empty.", "danger")
        return redirect(url_for('service_detail', service_id=service_id))

    if len(body) > 500:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Question too long (max 500 characters).'}), 400
        flash("Question too long (max 500 characters).", "danger")
        return redirect(url_for('service_detail', service_id=service_id))

    q = Question(service_id=service_id, asker_id=current_user.id, body=body)
    db.session.add(q)
    db.session.commit()

    # Notify seller of new question
    notify(
        user_id=svc.seller_id,
        type='question',
        title=f'New question on "{svc.title}"',
        body=body[:120] + ('…' if len(body) > 120 else ''),
        link=f'/service/{service_id}#qa',
        actor_id=current_user.id,
        service_id=service_id
    )

    # Send email to seller if configured
    try:
        seller = svc.seller
        if seller and seller.email:
            msg = MailMessage(
                subject=f"New question on your listing: {svc.title}",
                recipients=[seller.email],
                body=(
                    f"Hi {seller.display_name()},\n\n"
                    f"{current_user.display_name()} asked a question on your listing '{svc.title}':\n\n"
                    f"  \"{body}\"\n\n"
                    f"Reply here: {request.host_url}service/{service_id}#qa\n\n"
                    f"— FreelancingHub"
                )
            )
            mail.send(msg)
    except Exception as e:
        app.logger.warning(f"Q&A email failed: {e}")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'question': {
                'id': q.id,
                'body': q.body,
                'created_at': q.created_at.strftime('%b %d, %Y'),
                'asker': current_user.display_name(),
                'asker_avatar': current_user.avatar,
            }
        }), 201

    flash("Your question has been posted. The seller will be notified.", "success")
    return redirect(url_for('service_detail', service_id=service_id) + '#qa')


@app.route("/question/<int:question_id>/answer", methods=["POST"])
@login_required
def answer_question(question_id):
    """Seller answers a question."""
    q = Question.query.get_or_404(question_id)
    svc = Service.query.get_or_404(q.service_id)

    # Only the service owner can answer
    if current_user.id != svc.seller_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Only the seller can answer this question.'}), 403
        flash("Only the seller can answer this question.", "danger")
        return redirect(url_for('service_detail', service_id=svc.id))

    answer = (request.json.get('answer', '') if request.is_json else request.form.get('answer', '')).strip()
    if not answer:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Answer cannot be empty.'}), 400
        flash("Answer cannot be empty.", "danger")
        return redirect(url_for('service_detail', service_id=svc.id) + '#qa')

    if len(answer) > 1000:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Answer too long (max 1000 characters).'}), 400
        flash("Answer too long (max 1000 characters).", "danger")
        return redirect(url_for('service_detail', service_id=svc.id) + '#qa')

    q.answer     = answer
    q.answered_at= datetime.now(timezone.utc)
    db.session.commit()

    # Notify asker in-app
    notify(
        user_id=q.asker_id,
        type='answer',
        title=f'{svc.seller.display_name() if svc.seller else "Seller"} answered your question',
        body=answer[:120] + ('…' if len(answer) > 120 else ''),
        link=f'/service/{svc.id}#qa',
        actor_id=current_user.id,
        service_id=svc.id
    )

    # Notify asker by email
    try:
        if q.asker and q.asker.email:
            msg = MailMessage(
                subject=f"Your question was answered — {svc.title}",
                recipients=[q.asker.email],
                body=(
                    f"Hi {q.asker.display_name()},\n\n"
                    f"Your question on '{svc.title}' has been answered:\n\n"
                    f"  Q: \"{q.body}\"\n"
                    f"  A: \"{answer}\"\n\n"
                    f"View listing: {request.host_url}service/{svc.id}#qa\n\n"
                    f"— FreelancingHub"
                )
            )
            mail.send(msg)
    except Exception as e:
        app.logger.warning(f"Q&A answer email failed: {e}")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'answer': answer,
            'answered_at': q.answered_at.strftime('%b %d, %Y'),
            'response_time_hours': q.response_time_hours,
        })

    flash("Answer posted.", "success")
    return redirect(url_for('service_detail', service_id=svc.id) + '#qa')


@app.route("/question/<int:question_id>/delete", methods=["POST"])
@login_required
def delete_question(question_id):
    """Asker or seller can delete a question."""
    q   = Question.query.get_or_404(question_id)
    svc = Service.query.get_or_404(q.service_id)

    if current_user.id not in (q.asker_id, svc.seller_id):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Not authorised.'}), 403
        flash("Not authorised.", "danger")
        return redirect(url_for('service_detail', service_id=svc.id))

    db.session.delete(q)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})

    flash("Question deleted.", "info")
    return redirect(url_for('service_detail', service_id=svc.id) + '#qa')

# --------------------
# Register
# --------------------
@limiter.limit("5 per hour")   # registration — strict
@app.route("/register", methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit() or request.method == "POST":
        email = (form.email.data.strip().lower() if form.email.data else request.form.get("email", "").strip().lower())
        username = (form.username.data.strip() if form.username.data else (request.form.get("username") or None))
        password = (form.password.data if form.password.data else request.form.get("password"))
        role = "user"  # All users register as buyers; upgrade to seller via profile

        if not email or not password:
            flash("Email and password required.", "danger")
            return render_template("register.html", form=form)

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("login"))

        if username and User.query.filter_by(username=username).first():
            flash("Username taken.", "warning")
            return render_template("register.html", form=form)

        import random
        from datetime import datetime, timedelta
        code = str(random.randint(100000, 999999))
        expires = datetime.utcnow() + timedelta(minutes=15)
        u = User(username=username, email=email, password=generate_password_hash(password), role=role,
                 email_verified=False, email_verification_code=code, email_code_expires_at=expires)
        db.session.add(u)
        db.session.commit()
        try:
            msg = MailMessage(
                subject="Verify your FreelancingHub email",
                recipients=[email],
                html=f"""<div style="font-family:sans-serif;max-width:480px;margin:auto;background:#0f1429;color:#e2e8f0;padding:2rem;border-radius:16px"><h2 style="color:#00ffc8">Welcome to FreelancingHub</h2><p style="color:#94a3b8">Your verification code expires in 15 minutes.</p><div style="font-size:2.5rem;font-weight:800;letter-spacing:.3em;text-align:center;padding:1.5rem;background:rgba(0,255,200,.08);border:1px solid rgba(0,255,200,.2);border-radius:12px;color:#00ffc8;margin:1.5rem 0">{code}</div><p style="color:#475569;font-size:.82rem">If you did not create an account, ignore this email.</p></div>"""
            )
            mail.send(msg)
            flash("Account created. Check your email for a 6-digit verification code.", "success")
        except Exception as e:
            app.logger.error(f"Verification email failed: {e}")
            flash("Account created but email could not be sent. Contact support.", "warning")
        return redirect(url_for("verify_email", email=email))

    return render_template("register.html", form=form)

# --------------------
# Login
# --------------------
@app.route("/resend-verification")
def resend_verification():
    import random
    from datetime import datetime, timedelta
    email = request.args.get("email", "")
    user = User.query.filter_by(email=email).first()
    if not user or user.email_verified:
        return redirect(url_for("login"))
    code = str(random.randint(100000, 999999))
    user.email_verification_code = code
    user.email_code_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()
    try:
        msg = MailMessage(
            subject="Your new FreelancingHub verification code",
            recipients=[email],
            html=f'<div style="font-family:sans-serif;padding:2rem;background:#0f1429;color:#e2e8f0;border-radius:16px;max-width:480px;margin:auto"><h2 style="color:#00ffc8">New verification code</h2><div style="font-size:2.5rem;font-weight:800;letter-spacing:.3em;text-align:center;padding:1.5rem;background:rgba(0,255,200,.08);border:1px solid rgba(0,255,200,.2);border-radius:12px;color:#00ffc8;margin:1.5rem 0">{code}</div></div>'
        )
        mail.send(msg)
        flash("New code sent. Check your email.", "success")
    except Exception as e:
        flash("Could not send email. Try again later.", "danger")
    return redirect(url_for("verify_email", email=email))

@app.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    from datetime import datetime
    email = request.args.get("email") or request.form.get("email", "")
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Invalid verification link.", "danger")
        return redirect(url_for("register"))
    if user.email_verified:
        flash("Email already verified. Please log in.", "info")
        return redirect(url_for("login"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not user.email_code_expires_at or datetime.utcnow() > user.email_code_expires_at:
            flash("Verification code expired. Please register again.", "danger")
            return redirect(url_for("register"))
        if code == user.email_verification_code:
            user.email_verified = True
            user.email_verification_code = None
            user.email_code_expires_at = None
            db.session.commit()
            flash("Email verified successfully. Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Invalid code. Please try again.", "danger")
    return render_template("verify_email.html", email=email)

@limiter.limit("10 per minute; 50 per hour")  # brute-force protection
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.email_verified:
                flash("Please verify your email before logging in.", "warning")
                return redirect(url_for("verify_email", email=email))
            if user.role == "banned":
                flash("Your account has been suspended. Contact support for assistance.", "danger")
                return redirect(url_for("login"))
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

    # ── SELLER DASHBOARD ─────────────────────────────────────
    # Show seller section if user has can_sell=True (allows both buyer and seller)
    if current_user.can_sell:
        from sqlalchemy import extract, func as sqlfunc
        now   = datetime.now(timezone.utc)
        today = now.date()

        my_services = (Service.query
                       .filter_by(seller_id=current_user.id)
                       .order_by(Service.created_at.desc())
                       .all())
        service_ids = [s.id for s in my_services]

        # ── ORDERS ──────────────────────────────────────────
        all_orders = (Order.query
                      .filter(Order.seller_id == current_user.id)
                      .order_by(Order.created_at.desc())
                      .all())
        total_orders     = len(all_orders)
        completed_orders = [o for o in all_orders if o.status == 'completed']
        pending_orders   = [o for o in all_orders if o.status == 'pending']

        # ── REVENUE ─────────────────────────────────────────
        total_revenue = float(
            db.session.query(sqlfunc.sum(Payment.amount))
            .filter(Payment.seller_id == current_user.id,
                    Payment.status == 'completed')
            .scalar() or 0
        )

        # This month's revenue
        monthly_revenue = float(
            db.session.query(sqlfunc.sum(Payment.amount))
            .filter(Payment.seller_id == current_user.id,
                    Payment.status == 'completed',
                    extract('year',  Payment.created_at) == now.year,
                    extract('month', Payment.created_at) == now.month)
            .scalar() or 0
        )

        # Last month revenue (for % change)
        last_month     = (now.month - 1) or 12
        last_month_year= now.year if now.month > 1 else now.year - 1
        last_month_rev = float(
            db.session.query(sqlfunc.sum(Payment.amount))
            .filter(Payment.seller_id == current_user.id,
                    Payment.status == 'completed',
                    extract('year',  Payment.created_at) == last_month_year,
                    extract('month', Payment.created_at) == last_month)
            .scalar() or 0
        )
        rev_change_pct = (
            round((monthly_revenue - last_month_rev) / last_month_rev * 100, 1)
            if last_month_rev else None
        )

        # ── MONTHLY EARNINGS CHART (last 6 months) ──────────
        monthly_chart = []
        for i in range(5, -1, -1):
            # go back i months
            month_dt  = now.replace(day=1) - __import__('datetime').timedelta(days=i*30)
            m, y      = month_dt.month, month_dt.year
            rev       = float(
                db.session.query(sqlfunc.sum(Payment.amount))
                .filter(Payment.seller_id == current_user.id,
                        Payment.status == 'completed',
                        extract('year',  Payment.created_at) == y,
                        extract('month', Payment.created_at) == m)
                .scalar() or 0
            )
            monthly_chart.append({
                'label': month_dt.strftime('%b'),
                'value': rev
            })

        # ── RATINGS ─────────────────────────────────────────
        all_reviews = (Review.query
                       .filter(Review.seller_id == current_user.id)
                       .order_by(Review.created_at.desc())
                       .all())
        total_reviews  = len(all_reviews)
        avg_rating     = (
            round(sum(r.overall_rating for r in all_reviews) / total_reviews, 1)
            if total_reviews else 0.0
        )
        # Rating breakdown 1-5
        rating_breakdown = {i: 0 for i in range(1, 6)}
        for r in all_reviews:
            rating_breakdown[r.overall_rating] = rating_breakdown.get(r.overall_rating, 0) + 1

        # ── RESPONSE TIME (Q&A) ──────────────────────────────
        if service_ids:
            answered_qs = (Question.query
                           .filter(Question.service_id.in_(service_ids),
                                   Question.answered_at.isnot(None))
                           .all())
            if answered_qs:
                avg_response_hrs = round(
                    sum(q.response_time_hours for q in answered_qs) / len(answered_qs), 1
                )
            else:
                avg_response_hrs = None
        else:
            avg_response_hrs = None

        # ── TOP SERVICES by order count ──────────────────────
        svc_order_counts = {}
        for o in all_orders:
            svc_order_counts[o.service_id] = svc_order_counts.get(o.service_id, 0) + 1
        top_services = sorted(my_services,
                              key=lambda s: svc_order_counts.get(s.id, 0),
                              reverse=True)[:5]

        # ── CUSTOMER BREAKDOWN ───────────────────────────────
        buyer_ids     = [o.buyer_id for o in completed_orders]
        unique_buyers = len(set(buyer_ids))
        repeat_buyers = len([b for b in set(buyer_ids) if buyer_ids.count(b) > 1])

        # ── RECENT PAYMENTS ──────────────────────────────────
        recent_payments = (Payment.query
                           .filter_by(seller_id=current_user.id)
                           .order_by(Payment.created_at.desc())
                           .limit(8).all())

        return render_template("dashboard_seller.html",
            user=current_user,
            # services
            my_services=my_services,
            total_services=len(my_services),
            top_services=top_services,
            # orders
            total_orders=total_orders,
            completed_orders=len(completed_orders),
            pending_orders=len(pending_orders),
            recent_orders=all_orders[:8],
            # revenue
            total_revenue=total_revenue,
            monthly_revenue=monthly_revenue,
            last_month_rev=last_month_rev,
            rev_change_pct=rev_change_pct,
            monthly_chart=monthly_chart,
            # ratings
            avg_rating=avg_rating,
            total_reviews=total_reviews,
            rating_breakdown=rating_breakdown,
            all_reviews=all_reviews[:5],
            # response time
            avg_response_hrs=avg_response_hrs,
            # customers
            unique_buyers=unique_buyers,
            repeat_buyers=repeat_buyers,
            # payments
            recent_payments=recent_payments,
        )

    # For buyers, show their payment history
    else:
        payment_history = Payment.query.filter_by(buyer_id=current_user.id).\
            order_by(Payment.created_at.desc()).limit(10).all()

        return render_template("dashboard.html", user=current_user, payment_history=payment_history)

# ============================================================
# NOTIFICATIONS ROUTES
# ============================================================
@app.route("/notifications")
@login_required
def notifications():
    """Full notifications page."""
    all_notifs = (Notification.query
                  .filter_by(user_id=current_user.id)
                  .order_by(Notification.created_at.desc())
                  .limit(100).all())
    # Mark all as read
    (Notification.query
     .filter_by(user_id=current_user.id, is_read=False)
     .update({'is_read': True}))
    db.session.commit()
    return render_template('notifications.html', notifications=all_notifs)


@app.route("/notifications/mark-read", methods=["POST"])
@login_required
def mark_notifications_read():
    """Mark all (or one) notification as read. Called via AJAX."""
    notif_id = request.json.get('id') if request.is_json else None
    if notif_id:
        n = Notification.query.get(notif_id)
        if n and n.user_id == current_user.id:
            n.is_read = True
    else:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True, 'count': notif_count_for_user(current_user.id)})


@limiter.limit("10 per minute")
@app.route("/api/notifications/count")
@login_required
def api_notif_count():
    """Polled by navbar every 30s to update badge."""
    return jsonify({'count': notif_count_for_user(current_user.id)})


@app.route("/notifications/delete/<int:notif_id>", methods=["POST"])
@login_required
def delete_notification(notif_id):
    n = Notification.query.get_or_404(notif_id)
    if n.user_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(n)
    db.session.commit()
    return jsonify({'ok': True})


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
    services = Service.query.filter_by(seller_id=user.id).order_by(Service.created_at.desc()).all()

    # Aggregate stats
    total_services = len(services)
    all_reviews = []
    for svc in services:
        try:
            reviews = Review.query.filter_by(service_id=svc.id).order_by(Review.created_at.desc()).all()
            all_reviews.extend(reviews)
        except Exception:
            pass

    total_reviews = len(all_reviews)
    avg_rating = round(sum(r.overall_rating for r in all_reviews) / total_reviews, 1) if total_reviews > 0 else 0

    try:
        completed_orders = Order.query.filter_by(seller_id=user.id, status="completed").count()
    except Exception:
        completed_orders = 0

    member_since = user.created_at.strftime("%B %Y") if user.created_at else "N/A"

    return render_template("profile.html",
        user=user,
        services=services,
        total_services=total_services,
        all_reviews=all_reviews,
        total_reviews=total_reviews,
        avg_rating=avg_rating,
        completed_orders=completed_orders,
        member_since=member_since,
    )




@app.route("/become-seller", methods=["POST"])
@login_required
def become_seller():
    """Enable selling capability for a user (allows being both buyer and seller)."""
    # Check if user already has selling capability
    if current_user.can_sell:
        flash("You already have selling capabilities!", "info")
        return redirect(url_for("profile", username=current_user.username))

    # Check verification status
    verification_status = getattr(current_user, 'verification_status', None)
    
    # If already verified, enable selling immediately
    if current_user.is_verified:
        current_user.can_sell = True
        db.session.commit()
        flash("🎉 You can now sell! You can both buy and sell on the platform.", "success")
        return redirect(url_for("dashboard"))
    
    # If verification_status is None, no ID has been submitted yet - redirect to upload
    if verification_status is None:
        flash("You need to verify your ID before you can start selling.", "warning")
        return redirect(url_for("upload_id", next="become_seller"))
    
    # If pending verification, let them know to wait
    if verification_status == "pending":
        flash("⏳ Your ID verification is still pending. You'll be notified once it's reviewed.", "info")
        return redirect(url_for("profile", username=current_user.username))
    
    # If rejected, prompt for ID upload
    flash("Your ID verification was rejected. Please upload a clearer photo of your ID.", "warning")
    return redirect(url_for("upload_id", next="become_seller"))


@app.route("/toggle-seller-status", methods=["POST"])
@login_required
def toggle_seller_status():
    """Toggle selling capability on/off (allows being both buyer and seller)."""
    # Admins cannot toggle seller status
    if current_user.role == "admin":
        flash("Admin accounts cannot modify seller status.", "warning")
        return redirect(url_for("profile", username=current_user.username))

    # Toggle the can_sell flag
    if current_user.can_sell:
        current_user.can_sell = False
        db.session.commit()
        flash("Selling capability disabled. You can still buy services.", "info")
    else:
        # Check verification status
        verification_status = getattr(current_user, 'verification_status', None)
        
        # If already verified, enable selling immediately
        if current_user.is_verified:
            current_user.can_sell = True
            db.session.commit()
            flash("🎉 Selling capability enabled! You can now both buy and sell.", "success")
        # If verification_status is None, no ID has been submitted yet - redirect to upload
        elif verification_status is None:
            flash("You need to verify your ID before you can start selling.", "warning")
            return redirect(url_for("upload_id", next="toggle_seller_status"))
        # If pending verification, let them know to wait
        elif verification_status == "pending":
            flash("⏳ Your ID verification is still pending. You'll be notified once it's reviewed.", "info")
        # If rejected, prompt for ID upload
        else:
            flash("Your ID verification was rejected. Please upload a clearer photo of your ID.", "warning")
            return redirect(url_for("upload_id", next="toggle_seller_status"))

    return redirect(url_for("profile", username=current_user.username))


@app.route("/upload_avatar", methods=["POST"])
@login_required
def upload_avatar():
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
@app.route("/conversations")
@login_required
def conversations():
    # Get all conversations where current user is involved
    conversations_list = Conversation.query.filter(
        db.or_(
            Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id
        )
    ).all()
    
    chats = []
    for convo in conversations_list:
        # Get the other user
        other_user = convo.user1 if convo.user2_id == current_user.id else convo.user2

        # Skip conversations where the other user has been deleted
        if not other_user:
            continue

        # Get last message
        last_msg = Message.query.filter_by(conversation_id=convo.id).order_by(Message.timestamp.desc()).first()

        # Get unread count
        unread = Message.query.filter_by(conversation_id=convo.id, receiver_id=current_user.id, is_read=False).count()

        chats.append({
            "conversation_id": convo.id,
            "username": other_user.username or other_user.email or "Deleted User",
            "unread_count": unread,
            "user_id": other_user.id,
            "last_message": last_msg
        })
    
    # Sort by last message timestamp
    chats.sort(key=lambda c: c["last_message"].timestamp if c["last_message"] else datetime.min, reverse=True)
    
    return render_template("messages.html", chats=chats)

# --------------------
# Chat Routes
# --------------------
@app.route("/chat_user/<username>", methods=["GET", "POST"])
@login_required
def chat_user(username):
    receiver = User.query.filter_by(username=username).first_or_404()

    # Only buyer–seller chat allowed
    if not receiver or receiver.id == current_user.id:
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

    if current_user.id == other.id:
        flash("You cannot chat with yourself.", "warning")
        return redirect(url_for("dashboard"))

    # Get or create the conversation between the two users
    conversation = get_or_create_conversation(current_user.id, other.id)

    return redirect(url_for("chat", conversation_id=conversation.id))


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
    content = (data.get("content") or "").strip()
    location_data = data.get("location_data", None)

    if not content and not location_data:
        return

    # Get receiver_id from conversation object (more reliable than client data)
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return
    
    if conversation.user1_id == current_user.id:
        receiver_id = conversation.user2_id
    else:
        receiver_id = conversation.user1_id

    location_id = None
    
    # If location data is provided, create a Location record
    if location_data:
        try:
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
            
            # Create location record
            location = Location(
                user_id=current_user.id,
                latitude=float(location_data.get('latitude', 0)),
                longitude=float(location_data.get('longitude', 0)),
                address=location_data.get('address', ''),
                city=location_data.get('city', ''),
                country=location_data.get('country', ''),
                accuracy=location_data.get('accuracy'),
                expires_at=expires_at,
                shared_with=[receiver_id],
                is_active=True
            )
            db.session.add(location)
            db.session.commit()
            location_id = location.id
            print(f"✅ SocketIO: Location created with ID: {location_id}")
        except Exception as loc_err:
            print(f"❌ SocketIO: Error creating location: {loc_err}")
            db.session.rollback()

    # Use default content if only location is shared
    if not content and location_data:
        content = f"📍 {location_data.get('city', 'Location')}, {location_data.get('country', '')}"

    msg = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        location_id=location_id
    )
    db.session.add(msg)
    db.session.commit()

    room = f"convo_{conversation_id}"

    # Build payload with location info
    payload = {
        "id": msg.id,
        "sender_id": current_user.id,
        "sender": current_user.username,
        "receiver_id": receiver_id,
        "content": msg.content,
        "timestamp": msg.timestamp.strftime("%H:%M"),
        "room": room
    }
    
    # Include location data in payload if available
    if location_data:
        payload["location_data"] = location_data

    emit("receive_message", payload, room=room)


# ============================================================
# SOCKET.IO HANDLERS - Voice/Video Calls & Notifications
# ============================================================

@socketio.on("initiate_call")
def initiate_call(data):
    """
    Handle initiating a voice/video call.
    Creates a Call record and notifies the receiver.
    """
    try:
        conversation_id = data.get("conversation_id")
        receiver_id = data.get("receiver_id")
        call_type = data.get("call_type", "voice")  # 'voice' or 'video'
        
        if not conversation_id or not receiver_id:
            emit("error", {"message": "Missing conversation_id or receiver_id"})
            return
        
        # Create call record
        call = Call(
            conversation_id=conversation_id,
            caller_id=current_user.id,
            receiver_id=receiver_id,
            call_type=call_type,
            status='ringing'
        )
        db.session.add(call)
        db.session.commit()
        
        # Get caller info
        caller = User.query.get(current_user.id)
        caller_name = caller.display_name() if caller else "Unknown"
        
        # Emit incoming call to conversation room
        emit("incoming_call", {
            "call_id": call.id,
            "caller_id": current_user.id,
            "caller_name": caller_name,
            "call_type": call_type,
            "conversation_id": conversation_id
        }, room=f"convo_{conversation_id}")
        
        print(f"📞 {call_type} call initiated: conversation={conversation_id}, caller={current_user.id}")
        
    except Exception as e:
        print(f"Error initiating call: {e}")
        emit("error", {"message": "Failed to initiate call"})


@socketio.on("accept_call")
def accept_call(data):
    """
    Handle accepting an incoming call.
    Updates call status to 'accepted' and notifies the caller.
    """
    try:
        call_id = data.get("call_id")
        
        if not call_id:
            emit("error", {"message": "Missing call_id"})
            return
        
        call = Call.query.get(call_id)
        if not call:
            emit("error", {"message": "Call not found"})
            return
        
        # Verify receiver is the one accepting
        if call.receiver_id != current_user.id:
            emit("error", {"message": "Not authorized to accept this call"})
            return
        
        # Update call status
        call.status = 'accepted'
        db.session.commit()
        
        # Notify conversation that call was accepted
        emit("call_accepted", {
            "call_id": call.id,
            "call_type": call.call_type,
            "conversation_id": call.conversation_id
        }, room=f"convo_{call.conversation_id}")
        
        print(f"✅ Call accepted: call_id={call_id}")
        
    except Exception as e:
        print(f"Error accepting call: {e}")
        emit("error", {"message": "Failed to accept call"})


@socketio.on("reject_call")
def reject_call(data):
    """
    Handle rejecting an incoming call.
    Updates call status to 'rejected' and notifies the caller.
    """
    try:
        call_id = data.get("call_id")
        
        if not call_id:
            emit("error", {"message": "Missing call_id"})
            return
        
        call = Call.query.get(call_id)
        if not call:
            emit("error", {"message": "Call not found"})
            return
        
        # Verify receiver is the one rejecting
        if call.receiver_id != current_user.id:
            emit("error", {"message": "Not authorized to reject this call"})
            return
        
        # Update call status
        call.status = 'rejected'
        call.ended_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Notify conversation that call was rejected
        emit("call_rejected", {
            "call_id": call.id,
            "reason": "User declined",
            "conversation_id": call.conversation_id
        }, room=f"convo_{call.conversation_id}")
        
        print(f"❌ Call rejected: call_id={call_id}")
        
    except Exception as e:
        print(f"Error rejecting call: {e}")
        emit("error", {"message": "Failed to reject call"})


@socketio.on("end_call")
def end_call(data):
    """
    Handle ending an active call.
    Updates call status to 'ended' with duration and notifies participants.
    """
    try:
        call_id = data.get("call_id")
        duration = data.get("duration", 0)  # Duration in seconds
        
        if not call_id:
            emit("error", {"message": "Missing call_id"})
            return
        
        call = Call.query.get(call_id)
        if not call:
            emit("error", {"message": "Call not found"})
            return
        
        # Update call status
        call.status = 'ended'
        call.duration = duration
        call.ended_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Notify conversation that call ended
        emit("call_ended", {
            "call_id": call.id,
            "duration": duration,
            "conversation_id": call.conversation_id
        }, room=f"convo_{call.conversation_id}")
        
        print(f"📵 Call ended. Duration: {duration}s - call_id={call_id}")
        
    except Exception as e:
        print(f"Error ending call: {e}")
        emit("error", {"message": "Failed to end call"})


@socketio.on("notify_message_received")
def notify_message_received(data):
    """
    Send a real-time notification when a message is received.
    Creates a MessageNotification record and emits to the receiver.
    """
    try:
        message_id = data.get("message_id")
        receiver_id = data.get("receiver_id")
        
        if not message_id or not receiver_id:
            emit("error", {"message": "Missing message_id or receiver_id"})
            return
        
        # Create notification record
        notification = MessageNotification(
            message_id=message_id,
            user_id=receiver_id,
            notification_type='message_received'
        )
        db.session.add(notification)
        db.session.commit()
        
        # Get sender info
        message = Message.query.get(message_id)
        sender = User.query.get(current_user.id) if message else None
        sender_name = sender.display_name() if sender else "Unknown"
        
        # Emit notification to receiver's personal room
        emit("message_notification", {
            "message_id": message_id,
            "sender_id": current_user.id,
            "sender_name": sender_name,
            "notification_type": "message_received"
        }, room=f"user_{receiver_id}")
        
        print(f"Notification sent: message={message_id}, to_user={receiver_id}")
        
    except Exception as e:
        print(f"Error sending notification: {e}")
        emit("error", {"message": "Failed to send notification"})


# FIX ISSUE 9: Add Socket.IO handler for marking messages as read
@socketio.on("mark_as_read")
def mark_as_read(data):
    """
    Mark messages in a conversation as read.
    Sets read_at timestamp for all unread messages.
    Emits messages_read event to notify sender.
    """
    try:
        conversation_id = data.get("conversation_id")
        
        if not conversation_id:
            emit("error", {"message": "Missing conversation_id"})
            return
        
        # Get all unread messages in conversation where current user is receiver
        unread_messages = Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).all()
        
        # Mark messages as read
        now = datetime.now(timezone.utc)
        for msg in unread_messages:
            msg.is_read = True
            msg.read_at = now
        
        db.session.commit()
        
        # Emit messages_read event
        emit("messages_read", {
            "conversation_id": conversation_id,
            "message_ids": [msg.id for msg in unread_messages],
            "read_at": now.strftime("%Y-%m-%d %H:%M:%S")
        }, room=f"convo_{conversation_id}")
        
        print(f"📖 Marked {len(unread_messages)} messages as read in conversation {conversation_id}")
        
    except Exception as e:
        print(f"Error marking messages as read: {e}")
        emit("error", {"message": "Failed to mark messages as read"})


@socketio.on("join_chat")
def join_chat(data):
    """
    Handle user joining a chat conversation.
    Joins the user to the conversation room and broadcasts join event.
    """
    try:
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            emit("error", {"message": "Missing conversation_id"})
            return
        
        # Join the conversation room
        join_room(f"convo_{conversation_id}")
        
        # Get conversation info
        convo = Conversation.query.get(conversation_id)
        if convo:
            # Emit user joined event to the room
            emit("user_joined", {
                "conversation_id": conversation_id,
                "user_id": current_user.id,
                "username": current_user.display_name()
            }, room=f"convo_{conversation_id}", include_self=False)
            
            # Update user's online status in database
            current_user.is_online = True
            db.session.commit()
        
        print(f"✅ User {current_user.id} joined chat {conversation_id}")
        
    except Exception as e:
        print(f"Error in join_chat handler: {e}")
        emit("error", {"message": "Failed to join chat"})


@socketio.on("leave_chat")
def leave_chat(data):
    """
    Handle user leaving a chat conversation.
    Leaves the conversation room and broadcasts leave event.
    """
    try:
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            emit("error", {"message": "Missing conversation_id"})
            return
        
        # Leave the conversation room
        leave_room(f"convo_{conversation_id}")
        
        # Get conversation info
        convo = Conversation.query.get(conversation_id)
        if convo:
            # Emit user left event to the room
            emit("user_left", {
                "conversation_id": conversation_id,
                "user_id": current_user.id,
                "username": current_user.display_name()
            }, room=f"convo_{conversation_id}", include_self=False)
            
            # Update user's offline status in database
            current_user.is_online = False
            db.session.commit()
        
        print(f"❌ User {current_user.id} left chat {conversation_id}")
        
    except Exception as e:
        print(f"Error in leave_chat handler: {e}")
        emit("error", {"message": "Failed to leave chat"})


@socketio.on("message_read")
def message_read(data):
    """
    Handle message read acknowledgment.
    Marks messages as read and broadcasts read status to sender.
    """
    try:
        conversation_id = data.get("conversation_id")
        message_id = data.get("message_id")
        
        if not conversation_id:
            emit("error", {"message": "Missing conversation_id"})
            return
        
        # If specific message_id provided, mark that message as read
        if message_id:
            message = Message.query.get(message_id)
            if message and message.receiver_id == current_user.id:
                message.is_read = True
                message.read_at = datetime.now(timezone.utc)
                db.session.commit()
                
                # Emit read status to sender
                emit("message_read_status", {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "read_at": message.read_at.strftime("%Y-%m-%d %H:%M:%S")
                }, room=f"convo_{conversation_id}")
        
        print(f"📖 Message read: conversation={conversation_id}, message={message_id}")
        
    except Exception as e:
        print(f"Error in message_read handler: {e}")
        emit("error", {"message": "Failed to mark message as read"})


@socketio.on("message_delivered")
def message_delivered(data):
    """
    Handle message delivery acknowledgment.
    Marks messages as delivered and broadcasts delivery status to sender.
    """
    try:
        message_id = data.get("message_id")
        conversation_id = data.get("conversation_id")
        
        if not message_id:
            emit("error", {"message": "Missing message_id"})
            return
        
        message = Message.query.get(message_id)
        if message and message.receiver_id == current_user.id:
            # Create delivery notification
            notification = MessageNotification(
                message_id=message_id,
                user_id=message.sender_id,
                notification_type='message_delivered'
            )
            db.session.add(notification)
            db.session.commit()
            
            # Emit delivery status to sender
            emit("message_delivery_status", {
                "message_id": message_id,
                "conversation_id": conversation_id or message.conversation_id,
                "delivered": True,
                "delivered_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            }, room=f"convo_{message.conversation_id}")
        
        print(f"✅ Message delivered: message={message_id}")
        
    except Exception as e:
        print(f"Error in message_delivered handler: {e}")
        emit("error", {"message": "Failed to mark message as delivered"})


# FIX ISSUE 10: Add Socket.IO handlers for user presence (online/offline)
online_users = set()

@socketio.on("user_online")
def user_online(data):
    """
    Track user online status and broadcast to relevant rooms.
    """
    try:
        user_id = current_user.id
        online_users.add(user_id)
        
        # Get all conversations user is part of
        conversations = Conversation.query.filter(
            db.or_(
                Conversation.user1_id == user_id,
                Conversation.user2_id == user_id
            )
        ).all()
        
        # Broadcast to all conversation rooms
        for convo in conversations:
            emit("user_status_change", {
                "user_id": user_id,
                "status": "online"
            }, room=f"convo_{convo.id}")
        
        print(f"✅ User {user_id} is now online")
        
    except Exception as e:
        print(f"Error in user_online handler: {e}")

@socketio.on("user_offline")
def user_offline(data):
    """
    Track user offline status and broadcast to relevant rooms.
    """
    try:
        user_id = current_user.id
        if user_id in online_users:
            online_users.remove(user_id)
        
        # Get all conversations user is part of
        conversations = Conversation.query.filter(
            db.or_(
                Conversation.user1_id == user_id,
                Conversation.user2_id == user_id
            )
        ).all()
        
        # Broadcast to all conversation rooms
        for convo in conversations:
            emit("user_status_change", {
                "user_id": user_id,
                "status": "offline"
            }, room=f"convo_{convo.id}")
        
        print(f"❌ User {user_id} is now offline")
        
    except Exception as e:
        print(f"Error in user_offline handler: {e}")


@socketio.on("request_notification_permission")
def request_notification_permission(data):
    """
    Handle browser notification permission request.
    Logs the request (browser handles actual permission).
    """
    try:
        print(f"Notification permission requested by user {current_user.id}")
        emit("notification_permission_response", {"status": "requested"})
    except Exception as e:
        print(f"Error requesting notification permission: {e}")
        emit("error", {"message": "Failed to request notification permission"})


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
# FIX ISSUE 2: Removed duplicate code (lines 2360-2366) from admin_request_resubmission() function

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
        return redirect(url_for("upload_id", next="post_service"))

    # Get category from query params (default: web-development)
    category_slug = request.args.get('category', 'web-development')
    
    # Get category from database
    category_obj = Category.query.filter_by(slug=category_slug).first()
    if not category_obj:
        # Fallback to first category if slug not found
        category_obj = Category.query.first()
        if category_obj:
            category_slug = category_obj.slug
    
    # Get all categories for the form
    all_categories = Category.query.all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0").strip() or "0"
        currency = request.form.get("currency", "KES").strip()
        quality = request.form.get("quality", "").strip()
        category_slug = request.form.get("category", category_slug).strip()
        
        # Get category_id from form
        category_id = request.form.get("category_id", type=int)
        
        # Get category object for custom fields
        if category_id:
            category_obj = Category.query.get(category_id)
        else:
            category_obj = Category.query.filter_by(slug=category_slug).first()
        
        # Extract custom_data for category-specific fields
        custom_data = {}
        if category_obj and category_obj.custom_fields:
            for field in category_obj.custom_fields:
                field_name = field.get('name')
                if field_name:
                    field_value = request.form.get(field_name)
                    if field_value:
                        # Handle multi-select fields (checkboxes)
                        if field.get('type') == 'multi-select':
                            custom_data[field_name] = request.form.getlist(field_name)
                        else:
                            custom_data[field_name] = field_value
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

        # Create service with seller_id and category_id
        svc = Service(
            seller_id=current_user.id,
            title=title,
            description=description,
            price=Decimal(price),
            currency=currency,
            quality=quality,
            category_id=category_obj.id if category_obj else None,
            category_old=category_slug,  # Keep legacy field for backward compatibility
            custom_data=custom_data,  # Store category-specific data
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

    return render_template("service_form.html", action="create", service=None, max_images=MAX_IMAGE_COUNT,
                          category=category_obj, categories=all_categories)


# edit existing service
@app.route("/service/<int:id>/edit", methods=["GET","POST"])
@login_required
def edit_service(id):
    svc = Service.query.get_or_404(id)
    if svc.seller_id != current_user.id and current_user.role != "admin":
        flash("Not authorized", "danger")
        return redirect(url_for("service_view", id=id))

    # Get category for the service
    category_obj = None
    if svc.category_id:
        category_obj = Category.query.get(svc.category_id)
    elif svc.category_old:
        category_obj = Category.query.filter_by(slug=svc.category_old).first()
    
    # Get all categories for the form
    all_categories = Category.query.all()

    if request.method == "POST":
        svc.title = request.form.get("title","").strip()
        svc.description = request.form.get("description","").strip()
        svc.price = Decimal(request.form.get("price","0").strip() or "0")
        svc.currency = request.form.get("currency","KES").strip()
        svc.quality = request.form.get("quality","").strip()
        
        # Update category_id if provided
        category_id = request.form.get("category_id", type=int)
        if category_id:
            svc.category_id = category_id
            category_obj = Category.query.get(category_id)
            if category_obj:
                svc.category_old = category_obj.slug
        
        # Extract custom_data for category-specific fields
        custom_data = svc.custom_data or {}  # Start with existing data
        if category_obj and category_obj.custom_fields:
            for field in category_obj.custom_fields:
                field_name = field.get('name')
                if field_name:
                    field_value = request.form.get(field_name)
                    if field_value:
                        # Handle multi-select fields (checkboxes)
                        if field.get('type') == 'multi-select':
                            custom_data[field_name] = request.form.getlist(field_name)
                        else:
                            custom_data[field_name] = field_value
                    elif field_name in custom_data:
                        # Remove field if empty and was previously set
                        del custom_data[field_name]
        
        svc.custom_data = custom_data
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
    return render_template("service_form.html", action="edit", service=svc, images=images, videos=videos,
                          max_images=MAX_IMAGE_COUNT, max_videos=MAX_VIDEO_COUNT,
                          category=category_obj, categories=all_categories)

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
        return redirect(url_for("upload_id", next="post_service"))

    # Get all categories for the form
    categories = Category.query.all()
    
    form = ServiceForm()
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        
        # Get price and currency
        try:
            price = float(request.form.get("price", "0").strip() or "0")
        except Exception:
            flash("Invalid price.", "danger")
            return render_template("post_service.html", form=form, categories=categories)
        
        currency = request.form.get("currency", "KES").strip()
        
        # Handle category selection
        category_id = request.form.get("category_id", type=int)
        category_slug = request.form.get("category", "").strip()
        
        category_obj = None
        if category_id:
            category_obj = Category.query.get(category_id)
        elif category_slug:
            category_obj = Category.query.filter_by(slug=category_slug).first()
        
        # Extract custom_data for category-specific fields
        custom_data = {}
        if category_obj and category_obj.custom_fields:
            for field in category_obj.custom_fields:
                field_name = field.get('name')
                if field_name:
                    field_value = request.form.get(field_name)
                    if field_value:
                        # Handle multi-select fields (checkboxes)
                        if field.get('type') == 'multi-select':
                            custom_data[field_name] = request.form.getlist(field_name)
                        else:
                            custom_data[field_name] = field_value
        
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

        contact_info = json.dumps(contact_methods) if contact_methods else None
        
        # Handle media uploads (multiple files)
        image_filenames = []
        
        # Check for uploaded files - support both 'media' and 'image' field names
        files = request.files.getlist("media")
        if not files or all(not f.filename for f in files):
            files = request.files.getlist("image")
        
        for file in files:
            if file and file.filename:
                ext = file.filename.rsplit(".", 1)[-1].lower()
                if ext in ALLOWED_IMAGE_EXTENSIONS:
                    try:
                        filename = save_service_image(file, current_user.id)
                        image_filenames.append(filename)
                    except Exception as e:
                        flash(f"Image upload skipped: {str(e)}", "warning")
                elif ext in ALLOWED_VIDEO_EXTENSIONS:
                    try:
                        filename = save_service_video(file, current_user.id)
                        # Videos would be stored separately but for now add to images list
                        image_filenames.append(filename)
                    except Exception as e:
                        flash(f"Video upload skipped: {str(e)}", "warning")

        # Basic validation
        if not title:
            flash("Title is required", "danger")
            return render_template("post_service.html", form=form, categories=categories)

        svc = Service(
            seller_id=current_user.id,
            title=title,
            description=description,
            price=price,
            currency=currency,
            category_id=category_obj.id if category_obj else None,
            category_old=category_slug or (category_obj.slug if category_obj else None),
            custom_data=custom_data,
            contact_info=contact_info,
            image_filenames=json.dumps(image_filenames) if image_filenames else None
        )
        db.session.add(svc)
        db.session.commit()
        flash("Service posted successfully.", "success")
        return redirect(url_for("service_view", id=svc.id))

    return render_template("post_service.html", form=form, categories=categories)

# =============================================
# NEW PAYMENT ROUTES - Add BEFORE if __name__
# =============================================

# REPLACE the pay_service_updated function in app.py with this:

@app.route('/pay_service/<int:service_id>', methods=['POST'])
@login_required
def pay_service(service_id):
    """Process M-Pesa payment with buyer and seller phone numbers"""
    print("\n" + "="*80)
    print("💳 PAYMENT REQUEST RECEIVED")
    print("="*80)
    
    service = Service.query.get_or_404(service_id)
    
    if service.seller_id == current_user.id:
        print("❌ User trying to purchase own service")
        return jsonify({'success': False, 'message': 'Cannot purchase own service'}), 403
    
    try:
        # Get JSON data
        data = request.get_json() or {}
        print(f"📦 Received JSON data: {data}")
        
        # IMPORTANT: The form sends 'buyer_phone' and 'seller_phone'
        buyer_phone = data.get('buyer_phone', '').strip()
        seller_phone = data.get('seller_phone', '').strip()
        
        print(f"👤 Buyer Phone (raw): {buyer_phone}")
        print(f"👤 Seller Phone (raw): {seller_phone}")
        
        if not buyer_phone or not seller_phone:
            error_msg = 'Both phone numbers are required'
            print(f"❌ {error_msg}")
            return jsonify({'success': False, 'message': error_msg}), 400
        
        # Normalize phone numbers to 254 format
        if buyer_phone.startswith('0') and len(buyer_phone) == 10:
            buyer_phone = '254' + buyer_phone[1:]
        elif buyer_phone.startswith('+254'):
            buyer_phone = buyer_phone[1:]
        
        if seller_phone.startswith('0') and len(seller_phone) == 10:
            seller_phone = '254' + seller_phone[1:]
        elif seller_phone.startswith('+254'):
            seller_phone = seller_phone[1:]
        
        print(f"✅ Buyer Phone (normalized): {buyer_phone}")
        print(f"✅ Seller Phone (normalized): {seller_phone}")
        
        # Validate format
        if not buyer_phone.startswith('254') or len(buyer_phone) != 12:
            error_msg = f'Invalid buyer phone format. Use: 254712345678'
            print(f"❌ {error_msg}")
            return jsonify({'success': False, 'message': error_msg}), 400
        
        if not seller_phone.startswith('254') or len(seller_phone) != 12:
            error_msg = f'Invalid seller phone format. Use: 254712345678'
            print(f"❌ {error_msg}")
            return jsonify({'success': False, 'message': error_msg}), 400
        
        # Create payment record
        print(f"\n💾 Creating payment record...")
        payment = Payment(
            service_id=service_id,
            buyer_id=current_user.id,
            seller_id=service.seller_id,
            amount=float(service.price),
            phone_number=buyer_phone,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        print(f"✅ Payment record created: ID {payment.id}")
        
        # Import and call stk_push from mpesa module
        print(f"\n📱 Calling stk_push function...")
        from mpesa import stk_push
        
        # Get callback URL from .env
        callback_url = os.getenv("MPESA_CALLBACK_URL")
        
        stk_response = stk_push(
            phone_number=buyer_phone,
            amount=int(service.price),
            account_reference=f"SERVICE{service_id}",
            transaction_desc=f"Payment for {service.title}",
            callback_url=callback_url
        )
        
        print(f"\n📡 STK Push Response: {stk_response}")
        
        if stk_response and stk_response.get('ResponseCode') == '0':
            payment.checkout_request_id = stk_response.get('CheckoutRequestID')
            payment.merchant_request_id = stk_response.get('MerchantRequestID')
            db.session.commit()
            
            print(f"✅ Payment initiated successfully!")
            print("="*80 + "\n")
            
            return jsonify({
                'success': True,
                'message': 'STK Push sent successfully',
                'transaction_id': payment.id,
                'buyer_phone': buyer_phone,
                'checkout_request_id': payment.checkout_request_id
            }), 200
        else:
            payment.status = 'failed'
            db.session.commit()
            
            error_msg = stk_response.get('ResponseDescription', 'STK Push failed')
            print(f"❌ {error_msg}")
            print("="*80 + "\n")
            
            return jsonify({
                'success': False,
                'message': error_msg
            }), 400
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*80 + "\n")
        
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# Updated mpesa callback to properly handle responses
@app.route('/seller/settings', methods=['GET', 'POST'])
@login_required
def seller_settings():
    """Seller settings - configure M-Pesa phone for payouts"""
    
    if not current_user.can_sell:
        flash('Only users with selling capabilities can access this page', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        mpesa_phone = request.form.get('mpesa_phone', '').strip()
        
        if not mpesa_phone:
            flash('M-Pesa phone number is required', 'danger')
            return redirect(url_for('seller_settings'))
        
        # Normalize phone number
        if mpesa_phone.startswith('0') and len(mpesa_phone) == 10:
            mpesa_phone = '254' + mpesa_phone[1:]
        elif mpesa_phone.startswith('+254'):
            mpesa_phone = mpesa_phone[1:]
        
        # Validate format
        if not mpesa_phone.startswith('254') or len(mpesa_phone) != 12:
            flash('Invalid phone format. Use: 254712345678', 'danger')
            return redirect(url_for('seller_settings'))
        
        current_user.mpesa_phone = mpesa_phone
        db.session.commit()
        
        flash(f'✅ M-Pesa phone updated to: {mpesa_phone}', 'success')
        return redirect(url_for('seller_settings'))
    
    return render_template('seller_settings.html', user=current_user)

# =============================================
# END NEW PAYMENT ROUTES
# =============================================

# Register verification routes from external module
register_verification_routes(app, db)

# Import location routes - moved AFTER db initialization (line 235)
from location_routes import location_bp
from location_views import location_views_bp

# Register location blueprints
app.register_blueprint(location_bp)
app.register_blueprint(location_views_bp)
app.register_blueprint(features_bp)

# PHASE 3 FIX: Generic error messages - hide internal details from users
@app.errorhandler(Exception)
def handle_error(e):
    """Handle all uncaught exceptions with generic error messages"""
    # Log full error internally for debugging
    app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    
    # Return generic message to user - don't expose internal details
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500
    
    flash('An unexpected error occurred. Please try again later.', 'danger')
    return redirect(url_for('index'))


@app.after_request
def add_security_headers(response):
    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # XSS filter (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Referrer control
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Permissions policy — disable unnecessary browser features
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(self), payment=()"
    )
    # HSTS — force HTTPS (only in production)
    if os.environ.get("FLASK_ENV") == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.socket.io https://cdnjs.cloudflare.com "
            "https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' "
            "https://cdnjs.cloudflare.com https://unpkg.com "
            "https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com "
            "https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' data: blob:; "
        "connect-src 'self' wss: ws: https://nominatim.openstreetmap.org; "
        "frame-ancestors 'self';"
    )
    return response


# ============================================================
# SEND MESSAGE ROUTE
# ============================================================
@app.route('/send-message', methods=['POST'])
@login_required
def send_message():
    """Send message with optional location"""
    try:
        data = request.get_json()
        message_text = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        location_data = data.get('location', None)
        
        if not message_text and not location_data:
            return jsonify({'error': 'Message or location required'}), 400
        
        # Get conversation
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check authorization
        if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
            return jsonify({'error': 'Not authorized'}), 403
        
        location_id = None
        
        # If location data is provided, create a Location record
        if location_data:
            try:
                # Calculate expiration time (default 1 hour)
                from datetime import timedelta
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
                
                # Determine receiver for sharing
                receiver_id = conversation.user1_id if conversation.user2_id == current_user.id else conversation.user2_id
                
                # Create location record
                location = Location(
                    user_id=current_user.id,
                    latitude=float(location_data.get('latitude', 0)),
                    longitude=float(location_data.get('longitude', 0)),
                    address=location_data.get('address', ''),
                    city=location_data.get('city', ''),
                    country=location_data.get('country', ''),
                    accuracy=location_data.get('accuracy'),
                    expires_at=expires_at,
                    shared_with=[receiver_id],
                    is_active=True
                )
                db.session.add(location)
                db.session.commit()
                location_id = location.id
                print(f"✅ Location created with ID: {location_id}")
            except Exception as loc_err:
                print(f"❌ Error creating location: {loc_err}")
                db.session.rollback()
                # Continue without location if it fails
        
        # Get receiver_id from conversation
        receiver_id = conversation.user1_id if conversation.user2_id == current_user.id else conversation.user2_id
        
        # Create message with location reference
        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            conversation_id=conversation_id,
            content=message_text or '📍 Shared a location',
            location_id=location_id
        )
        
        db.session.add(message)
        db.session.commit()
        
        print(f"✅ Message sent in conversation {conversation_id} with location_id: {location_id}")
        
        return jsonify({
            'success': True,
            'message_id': message.id,
            'location_id': location_id
        }), 201
    
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error sending message: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Better static file serving with caching and optimization
@app.route('/static/<path:filename>')
def serve_static(filename):
    """
    Serve static files (images, CSS, JS) with proper headers
    Includes caching to reduce server load
    """
    try:
        # Prevent directory traversal attacks
        if '..' in filename:
            return "Forbidden", 403
        
        # Serve with caching headers
        response = send_from_directory(
            app.static_folder,
            filename,
            cache_timeout=86400  # Cache for 1 day (86400 seconds)
        )
        
        # Add additional headers for better performance
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Connection'] = 'keep-alive'
        
        return response
    
    except Exception as e:
        app.logger.error(f"Error serving static file {filename}: {e}")
        return "File not found", 404


# ═══════════════════════════════════════════════
# AI ASSISTANT ROUTE
# ═══════════════════════════════════════════════
@app.route('/api/ai-assistant', methods=['POST'])
@login_required
@limiter.limit("30 per minute; 200 per hour")   # protect OpenAI quota
def ai_assistant():
    """Soko AI — GPT-powered marketplace assistant."""
    try:
        import openai

        data         = request.get_json() or {}
        user_message = (data.get('message') or '').strip()
        history      = data.get('history', [])

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        if len(user_message) > 1000:
            return jsonify({'error': 'Message too long'}), 400

        openai_key = os.environ.get('OPENAI_API_KEY', '')
        if not openai_key:
            return jsonify({'error': 'AI assistant is not configured yet. Add OPENAI_API_KEY to your .env file.'}), 503

        # ── Live marketplace context ──────────────────────────
        try:
            total_services  = Service.query.count()
            total_sellers   = db.session.query(db.func.count(db.distinct(Service.seller_id))).scalar() or 0

            # Recent services with category
            recent_svcs = (Service.query
                           .options(db.selectinload(Service.category), db.selectinload(Service.seller))
                           .order_by(Service.created_at.desc())
                           .limit(8).all())
            recent_text = "\n".join([
                f"  • {s.title} — KES {s.price:,.0f} ({s.category.name if s.category else 'General'}) by @{s.seller.username if s.seller else 'unknown'}"
                for s in recent_svcs
            ])

            # Categories
            cats = Category.query.order_by(Category.name).all()
            cats_text = ", ".join([c.name for c in cats]) if cats else "Web Dev, Cars, Real Estate, Electronics, Clothing"

            # Current user info
            user_role     = "seller" if current_user.can_sell else "buyer"
            user_name     = current_user.username
            user_services = Service.query.filter_by(seller_id=current_user.id).count() if current_user.can_sell else 0

        except Exception as ctx_err:
            app.logger.warning(f"Soko AI context fetch failed: {ctx_err}")
            total_services = total_sellers = user_services = 0
            recent_text    = "  • Various services available"
            cats_text      = "Web Development, Car Sales, Real Estate, Electronics, Clothing, Photography, and more"
            user_role      = current_user.role
            user_name      = current_user.username

        # ── System prompt ────────────────────────────────────
        system_prompt = f"""You are Soko AI 🤖, the official assistant for FreelancingHub — a Kenyan freelance marketplace.
You help users find services, understand the platform, learn Kenyan market rates, and get the most out of the site.

━━━ WHO YOU'RE TALKING TO ━━━
Name: {user_name}
Role: {user_role} {'(has ' + str(user_services) + ' active listings)' if user_role == 'seller' else '(buyer who can also sell)'}

━━━ LIVE MARKETPLACE DATA ━━━
Total active listings: {total_services}
Active sellers: {total_sellers}
Categories: {cats_text}

Recent listings on the platform:
{recent_text}

━━━ PLATFORM NAVIGATION ━━━
Browse services     → /services
Search by keyword   → /services?q=KEYWORD
Browse category     → /services?category=SLUG
Post a service      → /post-service
Your dashboard      → /dashboard
Your messages       → /conversations
Your analytics      → /analytics  (sellers)
Your saved services → /features/saved
Payment (M-Pesa)    → Handled on each service page

━━━ KENYAN MARKET RATES (2025) ━━━
Web Developer (Junior)     KES 500–2,000/hr   or KES 15,000–50,000/project
Web Developer (Senior)     KES 3,000–8,000/hr or KES 80,000–300,000/project
Graphic Designer           KES 300–1,500/hr   or KES 5,000–40,000/project
Mobile App Developer       KES 2,000–7,000/hr
Digital Marketer           KES 500–2,500/hr
Photographer               KES 5,000–30,000/session
Video Editor               KES 3,000–25,000/project
Content Writer             KES 200–800/article
M-Pesa Integration Dev     KES 15,000–80,000/project
Data Analyst               KES 1,000–4,000/hr

━━━ HOW M-PESA PAYMENTS WORK ━━━
1. Buyer finds a service they like
2. Clicks "Pay with M-Pesa" on the service page
3. Enters their Safaricom M-Pesa number
4. Gets an STK push prompt on their phone
5. Enters PIN → payment confirmed instantly
6. Seller is notified and can begin work

━━━ HOW TO POST A SERVICE ━━━
1. Register/Login as a seller
2. Go to /post-service
3. Fill in: title, description, price, category, images
4. Add custom fields (e.g. experience level, skills, location)
5. Your listing goes live immediately

━━━ YOUR PERSONALITY ━━━
- Friendly, warm, and professional — like a knowledgeable Nairobi business advisor
- Always specific: give real prices in KES, real route links, real advice
- If user asks about a service category, mention what's currently on the platform
- If user is a seller, give tips to improve their listings or pricing
- If user is a buyer, help them find the right service
- Keep replies concise (3-6 sentences usually enough) but thorough when needed
- Use bullet points for lists, not walls of text
- Respond in Swahili if the user writes in Swahili, English otherwise
- Never make up services that don't exist on the platform
- If you don't know something, say so and suggest where to find it"""

        # ── Build messages ───────────────────────────────────
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-12:]:   # last 12 messages = 6 exchanges
            if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                messages.append({"role": msg['role'], "content": str(msg['content'])[:800]})
        messages.append({"role": "user", "content": user_message})

        # ── Call OpenAI ──────────────────────────────────────
        client   = openai.OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model       = "gpt-4o-mini",
            messages    = messages,
            max_tokens  = 600,
            temperature = 0.7,
        )

        reply = response.choices[0].message.content.strip()

        # Log usage (optional — remove in production if noisy)
        tokens = response.usage.total_tokens if response.usage else 0
        app.logger.info(f"Soko AI: user={current_user.id} tokens={tokens}")

        return jsonify({'reply': reply, 'success': True, 'role': user_role})

    except Exception as e:
        app.logger.error(f"Soko AI error: {e}")
        # Give user-friendly error, not raw exception
        if 'api_key' in str(e).lower() or 'auth' in str(e).lower():
            msg = "API key issue — check OPENAI_API_KEY in your .env file."
        elif 'rate' in str(e).lower():
            msg = "Too many requests — please wait a moment and try again."
        elif 'connection' in str(e).lower() or 'timeout' in str(e).lower():
            msg = "Connection timeout — please try again."
        else:
            msg = "Something went wrong. Please try again in a moment."
        return jsonify({'error': msg, 'success': False}), 500


# ═══════════════════════════════════════════════════════════
# ADMIN DASHBOARD ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/admin')
@login_required
@require_role('admin')
def admin_dashboard():
    """Main admin dashboard with platform statistics."""
    # Stats
    total_users     = User.query.count()
    total_services  = Service.query.count()
    total_payments  = Payment.query.count()
    total_revenue   = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    new_users_today = User.query.filter(User.created_at >= datetime.utcnow().date()).count()
    pending_verify  = User.query.filter_by(verification_status='pending', manual_review_required=True).count()
    banned_users    = User.query.filter_by(is_banned=True).count() if hasattr(User, 'is_banned') else 0

    # Recent users
    recent_users = User.query.order_by(User.created_at.desc()).limit(8).all()

    # Recent payments
    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(8).all()

    # Recent services
    recent_services = Service.query.order_by(Service.created_at.desc()).limit(8).all()

    # Revenue by month (last 6 months)
    from sqlalchemy import extract
    monthly = []
    for i in range(5, -1, -1):
        d = datetime.utcnow() - timedelta(days=30*i)
        rev = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.status == 'completed',
            extract('month', Payment.created_at) == d.month,
            extract('year',  Payment.created_at) == d.year
        ).scalar() or 0
        monthly.append({'month': d.strftime('%b'), 'revenue': float(rev)})

    return render_template('admin_dashboard.html',
        total_users=total_users,
        total_services=total_services,
        total_payments=total_payments,
        total_revenue=float(total_revenue),
        new_users_today=new_users_today,
        pending_verify=pending_verify,
        banned_users=banned_users,
        recent_users=recent_users,
        recent_payments=recent_payments,
        recent_services=recent_services,
        monthly=monthly,
    )


@app.route('/admin/users')
@login_required
@require_role('admin')
def admin_users():
    """List and manage all users."""
    q       = request.args.get('q', '').strip()
    role    = request.args.get('role', '')
    page    = request.args.get('page', 1, type=int)

    query = User.query
    if q:
        query = query.filter(db.or_(
            User.username.ilike(f'%{q}%'),
            User.email.ilike(f'%{q}%')
        ))
    if role:
        query = query.filter_by(role=role)

    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin_users.html', users=users, q=q, role=role)


@app.route('/admin/users/<int:user_id>/ban', methods=['POST'])
@login_required
@require_role('admin')
def admin_ban_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        return jsonify({'success': False, 'error': 'Cannot ban admin'}), 403
    # Use role field to mark banned
    user.role = 'banned'
    db.session.commit()
    return jsonify({'success': True, 'message': f'{user.username} has been banned'})


@app.route('/admin/users/<int:user_id>/unban', methods=['POST'])
@login_required
@require_role('admin')
def admin_unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'user'
    db.session.commit()
    return jsonify({'success': True, 'message': f'{user.username} has been unbanned'})


@app.route('/admin/users/<int:user_id>/verify', methods=['POST'])
@login_required
@require_role('admin')
def admin_verify_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = True
    user.verification_status = 'approved'
    user.id_verified = True
    db.session.commit()
    return jsonify({'success': True, 'message': f'{user.username} has been verified'})


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        return jsonify({'success': False, 'error': 'Cannot delete admin'}), 403
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'User deleted'})


@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@login_required
@require_role('admin')
def admin_change_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.json.get('role', 'user')
    if new_role not in ['user', 'admin']:
        return jsonify({'success': False, 'error': 'Invalid role'}), 400
    user.role = new_role
    db.session.commit()
    return jsonify({'success': True, 'message': f'Role changed to {new_role}'})


@app.route('/admin/services')
@login_required
@require_role('admin')
def admin_services():
    """List and manage all services."""
    q        = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    page     = request.args.get('page', 1, type=int)

    query = Service.query
    if q:
        query = query.filter(db.or_(
            Service.title.ilike(f'%{q}%'),
            Service.description.ilike(f'%{q}%')
        ))
    if category:
        query = query.filter(Service.category_id == category)

    services = query.order_by(Service.created_at.desc()).paginate(page=page, per_page=20)
    categories = Category.query.all()
    return render_template('admin_services.html', services=services, q=q, category=category, categories=categories)


@app.route('/admin/services/<int:service_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
def admin_delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Service deleted'})


@app.route('/admin/services/<int:service_id>/feature', methods=['POST'])
@login_required
@require_role('admin')
def admin_feature_service(service_id):
    service = Service.query.get_or_404(service_id)
    # Toggle featured using custom_data
    cd = service.custom_data or {}
    cd['featured'] = not cd.get('featured', False)
    service.custom_data = cd
    db.session.commit()
    status = 'featured' if cd['featured'] else 'unfeatured'
    return jsonify({'success': True, 'message': f'Service {status}', 'featured': cd['featured']})


@app.route('/admin/payments')
@login_required
@require_role('admin')
def admin_payments():
    """List all payments."""
    status = request.args.get('status', '')
    page   = request.args.get('page', 1, type=int)

    query = Payment.query
    if status:
        query = query.filter_by(status=status)

    payments = query.order_by(Payment.created_at.desc()).paginate(page=page, per_page=20)
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    return render_template('admin_payments.html', payments=payments, status=status, total_revenue=float(total_revenue))


@app.route("/admin/payouts")
@login_required
@require_role("admin")
def admin_payouts():
    page   = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    q = Payout.query
    if status:
        q = q.filter_by(status=status)
    payouts = q.order_by(Payout.created_at.desc()).paginate(page=page, per_page=25)
    stats = {
        "total":      Payout.query.count(),
        "completed":  Payout.query.filter_by(status="completed").count(),
        "failed":     Payout.query.filter_by(status="failed").count(),
        "processing": Payout.query.filter_by(status="processing").count(),
        "total_amt":  float(db.session.query(db.func.sum(Payout.amount)).filter_by(status="completed").scalar() or 0),
    }
    return render_template("admin/payouts.html", payouts=payouts, status=status, stats=stats)

@app.route("/admin/payouts/<int:payout_id>/retry", methods=["POST"])
@login_required
@require_role("admin")
def admin_retry_payout(payout_id):
    payout = Payout.query.get_or_404(payout_id)
    if payout.status not in ("failed", "processing"):
        flash("Only failed or processing payouts can be retried.", "warning")
        return redirect(url_for("admin_payouts"))
    order = Order.query.get(payout.order_id)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("admin_payouts"))
    try:
        from mpesa import initiate_b2c_payout
        initiate_b2c_payout(order)
        flash(f"Payout retry initiated for order #{payout.order_id}.", "success")
    except Exception as e:
        flash(f"Retry failed: {e}", "danger")
    return redirect(url_for("admin_payouts"))

@app.route('/admin/announce', methods=['POST'])
@login_required
@require_role('admin')
def admin_announce():
    """Send announcement notification to all users."""
    message = (request.json.get('message') or '').strip()
    if not message:
        return jsonify({'success': False, 'error': 'Message required'}), 400

    users = User.query.filter(User.role != 'banned').all()
    for user in users:
        notify(user_id=user.id, type='announcement',
               title='📢 Admin Announcement',
               body=message, link='/services')
    db.session.commit()
    return jsonify({'success': True, 'message': f'Announcement sent to {len(users)} users'})



@app.route('/pay_offer_mpesa', methods=['POST'])
@login_required
def pay_offer_mpesa():
    """Process M-Pesa payment for a custom offer order"""
    from models import Order
    data         = request.get_json() or {}
    buyer_phone  = data.get('buyer_phone', '').strip()
    seller_phone = data.get('seller_phone', '').strip()
    order_id     = data.get('order_id')
    amount       = data.get('amount')
    if not all([buyer_phone, seller_phone, order_id, amount]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    if buyer_phone.startswith('0') and len(buyer_phone) == 10:
        buyer_phone = '254' + buyer_phone[1:]
    if not buyer_phone.startswith('254') or len(buyer_phone) != 12:
        return jsonify({'success': False, 'message': 'Invalid buyer phone format'}), 400
    order = Order.query.get(order_id)
    if not order or order.buyer_id != current_user.id:
        return jsonify({'success': False, 'message': 'Order not found'}), 404
    try:
        payment = Payment(
            order_id=order_id,
            service_id=order.service_id,
            buyer_id=current_user.id,
            seller_id=order.seller_id,
            amount=float(amount),
            phone_number=buyer_phone,
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()
        from mpesa import stk_push
        callback_url = os.getenv('MPESA_CALLBACK_URL')
        stk_response = stk_push(
            phone_number=buyer_phone,
            amount=int(float(amount)),
            account_reference=f'OFFER-{order_id}',
            transaction_desc='FreelancingHub Custom Offer Payment',
            callback_url=callback_url
        )
        if stk_response and stk_response.get('ResponseCode') == '0':
            payment.checkout_request_id = stk_response.get('CheckoutRequestID')
            payment.merchant_request_id = stk_response.get('MerchantRequestID')
            db.session.commit()
            return jsonify({'success': True, 'message': 'STK Push sent successfully'})
        else:
            payment.status = 'failed'
            db.session.commit()
            return jsonify({'success': False, 'message': 'M-Pesa request failed. Try again.'})
    except Exception as e:
        app.logger.error(f'Offer payment error: {e}')
        return jsonify({'success': False, 'message': str(e)})



# ============================================================
# ORDER MANAGEMENT ROUTES
# ============================================================

@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    from models import Order
    order = Order.query.get_or_404(order_id)
    if current_user.id not in [order.buyer_id, order.seller_id] and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('order_detail.html', order=order)


@app.route('/order/<int:order_id>/pay')
@login_required
def pay_order(order_id):
    from models import Order
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if order.status != 'pending':
        flash('This order has already been paid or is not payable.', 'warning')
        return redirect(url_for('order_detail', order_id=order_id))
    return render_template('pay_order.html', order=order)


@app.route('/order/<int:order_id>/pay/mpesa', methods=['POST'])
@login_required
@limiter.limit("3 per minute; 10 per hour")
def pay_order_mpesa(order_id):
    from models import Order, Payment
    from mpesa import stk_push
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    # Duplicate payment check
    if order.status not in ('pending', 'failed'):
        return jsonify({'success': False, 'error': f'Order is already {order.status}'}), 400
    existing = Payment.query.filter_by(order_id=order.id, status='pending').first()
    if existing:
        return jsonify({'success': False, 'error': 'A payment is already pending for this order. Check your M-Pesa.'}), 400
    phone = request.form.get('phone', '').strip().replace(' ', '').replace('-', '')
    if not phone:
        return jsonify({'success': False, 'error': 'Phone number required'}), 400
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]
    callback_url = os.environ.get('MPESA_CALLBACK_URL', '')
    result = stk_push(
        phone_number=phone,
        amount=int(order.amount),
        account_reference=f'ORDER{order.id}',
        transaction_desc=f'Payment for order #{order.id}',
        callback_url=callback_url
    )
    if result.get('ResponseCode') == '0':
        payment = Payment(
            order_id=order.id,
            buyer_id=order.buyer_id,
            seller_id=order.seller_id,
            amount=order.amount,
            currency=order.currency or 'KES',
            phone_number=phone,
            status='pending',
            checkout_request_id=result.get('CheckoutRequestID'),
            merchant_request_id=result.get('MerchantRequestID')
        )
        db.session.add(payment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'STK push sent. Enter your M-Pesa PIN.'})
    else:
        return jsonify({'success': False, 'error': result.get('ResponseDescription', 'M-Pesa error')}), 400


@app.route('/order/<int:order_id>/start', methods=['POST'])
@login_required
def start_order(order_id):
    from models import Order, Notification
    from datetime import datetime
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.seller_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if order.status != 'paid':
        flash('Order must be paid before starting.', 'warning')
        return redirect(url_for('order_detail', order_id=order_id))
    order.status = 'in_progress'
    order.started_at = datetime.utcnow()
    notif = Notification(
        user_id=order.buyer_id,
        type='order',
        title='Order Started',
        body=f'Your order #{order.id} has been started by the seller.',
        link=url_for('order_detail', order_id=order.id)
    )
    db.session.add(notif)
    db.session.commit()
    flash('Order marked as in progress.', 'success')
    buyer = User.query.get(order.buyer_id)
    if buyer and buyer.email:
        send_order_email(buyer.email, f"Order #{order.id} Started", "Your Order Has Started 🚀",
            f"Great news! The seller has started working on order <strong>#{order.id}</strong>. You'll be notified when it's delivered.",
            order.id)
    return redirect(url_for('order_detail', order_id=order_id))


@app.route('/order/<int:order_id>/deliver', methods=['GET', 'POST'])
@login_required
def deliver_order(order_id):
    from models import Order, Notification
    from datetime import datetime
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.seller_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        if order.status != 'in_progress':
            flash('Order must be in progress to deliver.', 'warning')
            return redirect(url_for('order_detail', order_id=order_id))
        order.status = 'delivered'
        order.delivered_at = datetime.utcnow()
        order.deliverables = request.form.get('deliverables', '')
        notif = Notification(
            user_id=order.buyer_id,
            type='order',
            title='Order Delivered',
            body=f'Your order #{order.id} has been delivered! Please review and accept.',
            link=url_for('order_detail', order_id=order.id)
        )
        db.session.add(notif)
        db.session.commit()
        flash('Order delivered successfully.', 'success')
        buyer = User.query.get(order.buyer_id)
        if buyer and buyer.email:
            send_order_email(buyer.email, f"Order #{order.id} Delivered", "Your Order Has Been Delivered 📦",
                f"The seller has submitted the deliverables for order <strong>#{order.id}</strong>. Please review and accept or raise a dispute.",
                order.id, cta_text="Review Delivery")
        return redirect(url_for('order_detail', order_id=order_id))
    return render_template('deliver_order.html', order=order)


@app.route('/order/<int:order_id>/accept', methods=['POST'])
@login_required
def accept_order(order_id):
    from models import Order, Notification
    from datetime import datetime
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if order.status != 'delivered':
        flash('Order must be delivered before accepting.', 'warning')
        return redirect(url_for('order_detail', order_id=order_id))
    order.status = 'completed'
    order.completed_at = datetime.utcnow()
    # Auto mark as sold for product/property listings
    if order.service and order.service.category and order.service.category.layout_type in ('product', 'property'):
        order.service.is_sold = True
        order.service.is_active = False
    notif = Notification(
        user_id=order.seller_id,
        type='order',
        title='Order Accepted',
        body=f'Order #{order.id} has been accepted by the buyer. Payment will be released.',
        link=url_for('order_detail', order_id=order.id)
    )
    db.session.add(notif)
    db.session.commit()
    # Trigger B2C payout to seller
    try:
        order.status = "paid"
        db.session.commit()
        initiate_b2c_payout(order_id)
        order.status = "completed"
        db.session.commit()
    except Exception as e:
        logger.error(f"Payout failed for order {order_id}: {e}")
    flash("Order accepted. Payment will be released to seller.", "success")
    seller = User.query.get(order.seller_id)
    if seller and seller.email:
        send_order_email(seller.email, f"Order #{order.id} Accepted", "Order Accepted — Payment Released 💰",
            f"The buyer has accepted order <strong>#{order.id}</strong>. Your payment is being processed via M-Pesa.",
            order.id, cta_text="View Order")
    return redirect(url_for('order_detail', order_id=order_id))


@app.route('/order/<int:order_id>/dispute', methods=['GET', 'POST'])
@login_required
def file_dispute(order_id):
    from models import Order, Notification
    order = Order.query.get_or_404(order_id)
    if current_user.id not in [order.buyer_id, order.seller_id]:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        order.status = 'disputed'
        order.dispute_reason = request.form.get('reason', '').strip()
        other_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id
        notif = Notification(
            user_id=other_id,
            type='order',
            title='Dispute Filed',
            body=f'A dispute has been filed for order #{order.id}.',
            link=url_for('order_detail', order_id=order.id)
        )
        db.session.add(notif)
        db.session.commit()
        flash('Dispute filed. Our team will review shortly.', 'warning')
        other_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id
        other = User.query.get(other_id)
        if other and other.email:
            send_order_email(other.email, f"Dispute Filed on Order #{order.id}", "A Dispute Has Been Filed ⚠️",
                f"A dispute has been filed on order <strong>#{order.id}</strong>. Our team will review and reach out to both parties.",
                order.id, cta_text="View Order")
        return redirect(url_for('order_detail', order_id=order_id))
    return render_template('file_dispute.html', order=order)


@app.route('/order/<int:order_id>/review', methods=['GET', 'POST'])
@login_required
def review_order(order_id):
    from models import Order, Review
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.buyer_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if order.status != 'completed':
        flash('Order must be completed before reviewing.', 'warning')
        return redirect(url_for('order_detail', order_id=order_id))
    existing = Review.query.filter_by(service_id=order.service_id, buyer_id=current_user.id).first()
    if existing:
        flash('You have already reviewed this order.', 'info')
        return redirect(url_for('order_detail', order_id=order_id))
    if request.method == 'POST':
        review = Review(
            service_id=order.service_id,
            buyer_id=current_user.id,
            seller_id=order.seller_id,
            overall_rating=int(request.form.get('overall_rating', 5)),
            communication_rating=int(request.form.get('communication_rating', 5)),
            quality_rating=int(request.form.get('quality_rating', 5)),
            timeliness_rating=int(request.form.get('timeliness_rating', 5)),
            comment=request.form.get('comment', '')
        )
        db.session.add(review)
        db.session.commit()
        flash('Review submitted. Thank you!', 'success')
        return redirect(url_for('order_detail', order_id=order_id))
    return render_template('review_order.html', order=order)


@app.route('/order/<int:order_id>/message', methods=['POST'])
@login_required
def send_order_message(order_id):
    from models import Order, Notification
    order = Order.query.get_or_404(order_id)
    if current_user.id not in [order.buyer_id, order.seller_id]:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    content = request.form.get('content', '').strip()
    if not content:
        flash('Message cannot be empty.', 'warning')
        return redirect(url_for('order_detail', order_id=order_id))
    other_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id
    notif = Notification(
        user_id=other_id,
        type='message',
        title='New Message',
        body=f'New message on order #{order.id}',
        link=url_for('order_detail', order_id=order.id)
    )
    db.session.add(notif)
    db.session.commit()
    flash('Message sent.', 'success')
    return redirect(url_for('order_detail', order_id=order_id))


@app.route('/my-orders')
@login_required
def my_orders():
    from models import Order
    buying = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    selling = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', buying=buying, selling=selling)

# ============================================================

@app.route("/id_doc/<filename>")
@login_required
def serve_id_doc(filename):
    if current_user.role != "admin":
        abort(403)
    id_dir = os.path.join(app.root_path, "instance", "id_uploads")
    return send_from_directory(id_dir, filename)

@app.route("/admin/disputes")
@login_required
@require_role("admin")
def admin_disputes():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "disputed")
    q = Order.query.filter_by(status=status) if status != "all" else Order.query
    disputes = q.order_by(Order.updated_at.desc()).paginate(page=page, per_page=20)
    counts = {
        "disputed": Order.query.filter_by(status="disputed").count(),
        "resolved": Order.query.filter_by(status="resolved").count(),
    }
    return render_template("admin/disputes.html", disputes=disputes, status=status, counts=counts)

@app.route("/admin/disputes/<int:order_id>/resolve", methods=["POST"])
@login_required
@require_role("admin")
def admin_resolve_dispute(order_id):
    order = Order.query.get_or_404(order_id)
    resolution = request.form.get("resolution", "").strip()
    action = request.form.get("action", "")
    if not resolution:
        flash("Resolution note is required.", "warning")
        return redirect(url_for("admin_disputes"))
    order.resolution_note = resolution
    order.resolved_at = datetime.utcnow()
    order.resolved_by = current_user.id
    if action == "refund":
        order.status = "refunded"
    elif action == "complete":
        order.status = "completed"
    elif action == "hold":
        order.status = "on_hold"
    elif action == "ban_buyer":
        order.status = "resolved"
        buyer = User.query.get(order.buyer_id)
        if buyer:
            buyer.role = "banned"
            db.session.add(buyer)
    elif action == "ban_seller":
        order.status = "resolved"
        seller = User.query.get(order.seller_id)
        if seller:
            seller.role = "banned"
            db.session.add(seller)
    elif action == "warn_buyer":
        order.status = "resolved"
        buyer = User.query.get(order.buyer_id)
        if buyer and buyer.email:
            send_order_email(buyer.email, f"Warning — Order #{order.id}",
                "Account Warning ⚠️",
                f"Your account has received a warning regarding order <strong>#{order.id}</strong>.<br><br><strong>Admin note:</strong> {resolution}",
                order.id, cta_text="View Order")
    elif action == "warn_seller":
        order.status = "resolved"
        seller = User.query.get(order.seller_id)
        if seller and seller.email:
            send_order_email(seller.email, f"Warning — Order #{order.id}",
                "Account Warning ⚠️",
                f"Your account has received a warning regarding order <strong>#{order.id}</strong>.<br><br><strong>Admin note:</strong> {resolution}",
                order.id, cta_text="View Order")
    else:
        order.status = "resolved"
    # Notify both parties
    for uid, msg in [
        (order.buyer_id, f"Your dispute for order #{order.id} has been resolved by admin."),
        (order.seller_id, f"The dispute for order #{order.id} has been resolved by admin.")
    ]:
        db.session.add(Notification(
            user_id=uid, type="order", title="Dispute Resolved",
            body=msg, link=url_for("order_detail", order_id=order.id)
        ))
    # Email both
    buyer = User.query.get(order.buyer_id)
    seller = User.query.get(order.seller_id)
    for u in [buyer, seller]:
        if u and u.email:
            send_order_email(u.email, f"Dispute Resolved — Order #{order.id}",
                "Dispute Has Been Resolved ✅",
                f"The dispute for order <strong>#{order.id}</strong> has been reviewed by our team.<br><br><strong>Resolution:</strong> {resolution}",
                order.id)
    db.session.commit()
    flash(f"Order #{order.id} dispute resolved as '{order.status}'.", "success")
    return redirect(url_for("admin_disputes"))


@app.route("/service/<int:id>/mark-sold", methods=["POST"])
@login_required
def mark_service_sold(id):
    svc = Service.query.get_or_404(id)
    if svc.seller_id != current_user.id and current_user.role != "admin":
        flash("Not authorized.", "danger")
        return redirect(url_for("service_detail", service_id=id))
    svc.is_sold = True
    svc.is_active = False
    db.session.commit()
    flash("Listing marked as sold.", "success")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/service/<int:id>/toggle-active", methods=["POST"])
@login_required
def toggle_service_active(id):
    svc = Service.query.get_or_404(id)
    if svc.seller_id != current_user.id and current_user.role != "admin":
        flash("Not authorized.", "danger")
        return redirect(url_for("service_detail", service_id=id))
    if svc.is_sold:
        flash("Cannot reactivate a sold listing.", "warning")
        return redirect(request.referrer or url_for("dashboard"))
    svc.is_active = not svc.is_active
    db.session.commit()
    status = "activated" if svc.is_active else "deactivated"
    flash(f"Listing {status}.", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/account/delete", methods=["GET", "POST"])
@login_required
def delete_account():
    if request.method == "POST":
        password = request.form.get("password", "")
        if not current_user.check_password(password):
            flash("Incorrect password.", "danger")
            return redirect(url_for("delete_account"))
        user = current_user
        # Anonymize orders instead of deleting (preserve order history)
        from models import Order, Review, Notification, Favorite
        Order.query.filter_by(buyer_id=user.id).update({'buyer_id': None})
        Order.query.filter_by(seller_id=user.id).update({'seller_id': None})
        # Delete user data
        Review.query.filter_by(buyer_id=user.id).delete()
        Review.query.filter_by(seller_id=user.id).delete()
        Notification.query.filter_by(user_id=user.id).delete()
        Favorite.query.filter_by(user_id=user.id).delete()
        # Delete services
        for svc in user.services:
            db.session.delete(svc)
        db.session.flush()
        from flask_login import logout_user
        logout_user()
        db.session.delete(user)
        db.session.commit()
        flash("Your account has been permanently deleted.", "info")
        return redirect(url_for("index"))
    return render_template("delete_account.html")

@app.route("/account/export")
@login_required
def export_account_data():
    from models import Order, Review, Notification, Payment
    import json as _json
    user = current_user
    data = {
        "account": {
            "username": user.username,
            "email": user.email,
            "created_at": str(user.created_at),
            "verification_status": user.verification_status,
        },
        "orders_as_buyer": [
            {"id": o.id, "amount": str(o.amount), "status": o.status, "created_at": str(o.created_at)}
            for o in Order.query.filter_by(buyer_id=user.id).all()
        ],
        "orders_as_seller": [
            {"id": o.id, "amount": str(o.amount), "status": o.status, "created_at": str(o.created_at)}
            for o in Order.query.filter_by(seller_id=user.id).all()
        ],
        "reviews": [
            {"service_id": r.service_id, "rating": r.overall_rating, "created_at": str(r.created_at)}
            for r in Review.query.filter_by(buyer_id=user.id).all()
        ],
        "payments": [
            {"amount": str(p.amount), "status": p.status, "created_at": str(p.created_at)}
            for p in Payment.query.filter_by(buyer_id=user.id).all()
        ],
    }
    response = app.response_class(
        response=_json.dumps(data, indent=2),
        status=200,
        mimetype="application/json"
    )
    response.headers["Content-Disposition"] = f"attachment; filename=freelancinghub_data_{user.id}.json"
    return response
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
    
    # SECURITY FIX: Run in production mode (debug=False)
    # Use environment variable to control debug mode
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=debug_mode,
        allow_unsafe_werkzeug=not debug_mode,
        use_reloader=debug_mode  # Only enable reloader in debug mode
    )
