"""
Centralized configuration for Freelance Marketplace
All configuration values and environment variable handling
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --------------------
# Core Flask Configuration
# --------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

# Database
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'database.db'))
SQLALCHEMY_TRACK_MODIFICATIONS = False

# File Upload Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
ID_FOLDER = os.path.join(UPLOAD_FOLDER, "ids")
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
CHAT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, "chat")
SERVICE_IMG_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads", "services")
SERVICE_VIDEO_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads", "services", "videos")

MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

# Service media constants
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "quicktime"}
ALLOWED_EXT = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS
MAX_IMAGE_COUNT = 50
MAX_VIDEO_COUNT = 20
MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 100

# Allowed file types
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_ID_EXT = ALLOWED_IMAGE_EXT | {"pdf"}
ALLOWED_AVATAR_EXT = ALLOWED_IMAGE_EXT

# --------------------
# Mail Configuration
# --------------------
MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
MAIL_PORT = int(os.environ.get("MAIL_PORT") or 0)
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "False") == "True"
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@example.com")

# --------------------
# External Service Configuration
# --------------------
# M-Pesa
MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE', '174379')
MPESA_CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL', 'https://yourdomain.com/mpesa/callback')
MPESA_PRODUCTION = os.getenv('MPESA_PRODUCTION', 'False').lower() == 'true'
MPESA_SECURITY_CREDENTIAL = os.getenv('MPESA_SECURITY_CREDENTIAL', '')

# Google Cloud Vision
USE_MOCK_VISION = os.environ.get("USE_MOCK_VISION", "False").lower() == "true"
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CLOUD_VISION_API_KEY = os.getenv("GOOGLE_CLOUD_VISION_API_KEY")

# --------------------
# Application Constants
# --------------------
# Admin credentials for initial setup
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PWD = os.environ.get("ADMIN_PWD", "adminpass")

# Tesseract OCR path
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Base directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# --------------------
# Directory Creation
# --------------------
def ensure_directories():
    """Ensure all required directories exist"""
    directories = [
        UPLOAD_FOLDER,
        ID_FOLDER,
        AVATAR_FOLDER,
        CHAT_UPLOAD_FOLDER,
        SERVICE_IMG_FOLDER,
        SERVICE_VIDEO_FOLDER
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    # Set directory permissions
    try:
        os.chmod(SERVICE_IMG_FOLDER, 0o755)
    except Exception:
        pass

    try:
        os.chmod(SERVICE_VIDEO_FOLDER, 0o755)
    except Exception:
        pass

# Initialize directories on import
ensure_directories()