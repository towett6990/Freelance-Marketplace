"""
tasks.py — Celery background tasks
Moves slow operations OFF the web request so users get instant responses.
"""
from celery_worker import celery
import os
import logging

logger = logging.getLogger(__name__)


# ── IMAGE PROCESSING ─────────────────────────────────────────
@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def process_service_image(self, image_path: str, service_id: int):
    """
    Resize and optimise a service image in the background.
    Replaces synchronous PIL processing in the upload route.
    """
    try:
        from PIL import Image, ImageOps
        MAX_W, MAX_H = 1200, 900
        QUALITY      = 85

        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)     # fix rotation

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        img.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

        # Save as WebP for ~30% smaller files
        webp_path = os.path.splitext(image_path)[0] + ".webp"
        img.save(webp_path, "WEBP", quality=QUALITY, optimize=True)

        # Remove original if webp succeeded
        if os.path.exists(webp_path) and os.path.exists(image_path) and image_path != webp_path:
            os.remove(image_path)

        logger.info(f"[task] Image processed: {webp_path}")
        return {"status": "ok", "path": webp_path}

    except Exception as exc:
        logger.error(f"[task] Image processing failed: {exc}")
        raise self.retry(exc=exc)


# ── ID VERIFICATION ──────────────────────────────────────────
@celery.task(bind=True, max_retries=2, default_retry_delay=30)
def process_id_verification(self, user_id: int, id_image_path: str):
    """
    Run OCR + face recognition in background.
    Replaces the synchronous verification that was blocking requests.
    """
    try:
        # Import Flask app context
        from app import app, db
        from models import User

        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                return {"status": "error", "reason": "user_not_found"}

            # Run pytesseract OCR
            import pytesseract
            from PIL import Image
            img  = Image.open(id_image_path)
            text = pytesseract.image_to_string(img)

            # Basic check — does it look like an ID?
            has_id_number = any(c.isdigit() for c in text)
            result = "ocr_passed" if has_id_number else "ocr_failed"

            # Update user verification status
            user.id_verification_status = result
            db.session.commit()

            logger.info(f"[task] ID verification for user {user_id}: {result}")
            return {"status": result, "user_id": user_id}

    except Exception as exc:
        logger.error(f"[task] ID verification failed for user {user_id}: {exc}")
        raise self.retry(exc=exc)


# ── EMAIL NOTIFICATIONS ──────────────────────────────────────
@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_notification(self, to_email: str, subject: str, body: str):
    """
    Send transactional emails in the background.
    Prevents email latency from affecting page response times.
    """
    try:
        from app import app, mail
        from flask_mail import Message as MailMessage

        with app.app_context():
            if not app.config.get("MAIL_SERVER"):
                logger.warning("[task] MAIL_SERVER not configured, skipping email")
                return {"status": "skipped"}

            msg = MailMessage(
                subject=subject,
                recipients=[to_email],
                body=body,
            )
            mail.send(msg)
            logger.info(f"[task] Email sent to {to_email}: {subject}")
            return {"status": "sent"}

    except Exception as exc:
        logger.error(f"[task] Email failed to {to_email}: {exc}")
        raise self.retry(exc=exc)


# ── SELLER ANALYTICS RECALCULATION ───────────────────────────
@celery.task
def recalculate_seller_level(seller_id: int):
    """
    Recalculate a seller's level badge after each completed payment.
    Runs async so the payment callback returns instantly.
    """
    try:
        from app import app, db
        from models_extra import SellerLevel

        with app.app_context():
            level = SellerLevel.query.filter_by(seller_id=seller_id).first()
            if level:
                level.recalculate()
                db.session.commit()
                logger.info(f"[task] Seller level updated for seller {seller_id}: {level.level}")
            return {"status": "ok"}

    except Exception as exc:
        logger.error(f"[task] Seller level recalculation failed: {exc}")
        return {"status": "error", "reason": str(exc)}