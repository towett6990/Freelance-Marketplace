"""
verification_system.py
ID Verification — OCR first, then manual review fallback
Flow:
  1. User uploads ID
  2. OCR runs automatically
     → HIGH confidence  : auto-approved instantly ✅
     → NOT a national ID: hard rejected ❌ (re-upload)
     → LOW confidence   : queued for manual review ⏳
  3. On manual review queue → all admins get a notification
  4. Admin views ID images, approves or rejects
  5. User gets notification with result
"""

import os
import uuid
import json
import cv2
import pytesseract
import re
from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import shutil
_tess = shutil.which("tesseract") or os.environ.get("TESSERACT_CMD") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = _tess

# ─────────────────────────────────────────────────────────────
# MASTER SWITCH  —  set False to skip OCR and always queue
#                   for manual review (useful during testing)
# ─────────────────────────────────────────────────────────────
ENABLE_OCR = True


# ═══════════════════════════════════════════════════════════════
# OCR VERIFIER
# ═══════════════════════════════════════════════════════════════
class NationalIDVerifier:

    ID_PATTERNS = {
        'KENYA': {
            'keywords': ['KENYA','JAMHURI','IDENTITY','CARD','ID','NATIONAL',
                         'DATE','BIRTH','KENYATTA','REPUBLIC'],
            'min_confidence': 0.50,
        },
        'UGANDA': {
            'keywords': ['UGANDA','NATIONAL IDENTIFICATION','ID NUMBER',
                         'DATE OF BIRTH','REPUBLIC OF UGANDA'],
            'min_confidence': 0.65,
        },
        'TANZANIA': {
            'keywords': ['TANZANIA','NATIONAL IDENTIFICATION','DATE OF BIRTH',
                         'REPUBLIC OF TANZANIA'],
            'min_confidence': 0.65,
        },
        'SOUTH AFRICA': {
            'keywords': ['REPUBLIC OF SOUTH AFRICA','IDENTITY DOCUMENT',
                         'RSA ID','IDENTIFICATION NUMBER'],
            'min_confidence': 0.65,
        },
        'NIGERIA': {
            'keywords': ['FEDERAL REPUBLIC OF NIGERIA','NATIONAL IDENTIFICATION',
                         'NIN','NATIONAL ID CARD'],
            'min_confidence': 0.65,
        },
    }

    REJECTION_PATTERNS = {
        'SCHOOL':   ['SCHOOL','STUDENT','ADMISSION','UNIVERSITY','COLLEGE'],
        'PASSPORT': ['PASSPORT','TRAVEL DOCUMENT','MINISTRY OF FOREIGN'],
        'DRIVER':   ['DRIVER LICENSE','DRIVING PERMIT','VEHICLE','MOTOR'],
        'WORK':     ['EMPLOYEE','STAFF ID','COMPANY ID','EMPLOYMENT'],
        'LIBRARY':  ['LIBRARY CARD'],
        'HEALTH':   ['HEALTH INSURANCE','MEDICAL CARD'],
    }

    def verify(self, front_path, back_path=None):
        """
        Returns dict:
          status  : 'verified' | 'manual_review' | 'rejected'
          country : detected country or None
          confidence : float 0-1
          message : human-readable result
          risks   : list of strings
        """
        result = {
            'status': 'manual_review',
            'country': None,
            'confidence': 0.0,
            'id_type_score': 0.0,
            'authenticity_score': 0.0,
            'is_national_id': False,
            'message': '',
            'risks': [],
        }

        try:
            # 1. Is it a national ID at all?
            id_type = self._detect_id_type(front_path)
            result['id_type_score']  = id_type['confidence']
            result['is_national_id'] = id_type['is_national_id']

            if not id_type['is_national_id']:
                result['status']  = 'rejected'
                result['message'] = f"Not a national ID — detected: {id_type['detected_type']}"
                result['risks'].append(result['message'])
                return result

            # 2. Which country?
            country = self._detect_country(front_path, back_path)
            result['country'] = country['country'] or 'KENYA'   # default Kenya

            # 3. Authenticity / image quality
            auth = self._check_authenticity(front_path)
            result['authenticity_score'] = auth['score']
            result['risks'].extend(auth['risks'])

            # 4. OCR text quality
            ocr = self._extract_fields(front_path, back_path)
            result['risks'].extend(ocr['risks'])

            # 5. Overall confidence
            confidence = (
                result['id_type_score']      * 0.35 +
                result['authenticity_score'] * 0.40 +
                ocr['text_confidence']       * 0.25
            )
            result['confidence'] = round(confidence, 4)

            min_conf = self.ID_PATTERNS.get(result['country'], {}).get('min_confidence', 0.65)

            if confidence >= min_conf and not ocr['has_critical_issues']:
                result['status']  = 'verified'
                result['message'] = f"{result['country']} National ID auto-verified ({confidence:.0%})"
            else:
                result['status']  = 'manual_review'
                result['message'] = (
                    f"Low OCR confidence ({confidence:.0%}) — queued for manual review"
                )

            return result

        except Exception as e:
            logger.error(f"OCR verify error: {e}", exc_info=True)
            result['status']  = 'manual_review'
            result['message'] = f"OCR error — queued for manual review"
            result['risks'].append(str(e))
            return result

    # ── helpers ──────────────────────────────────────────────────────

    def _best_rotation(self, path):
        from PIL import Image
        try:
            img = Image.open(path)
            kw = ["KITAMBULISHO", "NATIONAL IDENTITY", "JAMHURI", "ID NUMBER", "DATE OF BIRTH", "SURNAME"]
            best_img, best_score = img, 0
            for angle in [0, 90, 180, 270]:
                rotated = img.rotate(angle, expand=True)
                text = pytesseract.image_to_string(rotated).upper()
                score = sum(1 for k in kw if k in text)
                if score > best_score:
                    best_score, best_img = score, rotated
            return best_img
        except:
            return None

    def _ocr_text(self, path):
        try:
            img = self._best_rotation(path)
            if img:
                return pytesseract.image_to_string(img).upper()
            return pytesseract.image_to_string(path).upper()
        except:
            return ""

    def _detect_id_type(self, path):
        try:
            text = self._ocr_text(path)
            # Hard reject if 2+ rejection keyword sets match
            rej = sum(
                1 for kws in self.REJECTION_PATTERNS.values()
                if sum(1 for k in kws if k in text) >= 2
            )
            if rej >= 2:
                return {'is_national_id': False, 'confidence': 0.95,
                        'detected_type': 'Non-national document'}

            nat_kws = ['KENYA','IDENTITY','CARD','ID','NATIONAL','DATE',
                       'BIRTH','JAMHURI','REPUBLIC']
            count   = sum(1 for k in nat_kws if k in text)
            kw_conf = min(0.95, count / len(nat_kws) * 1.5)
            fmt     = self._format_score(path)
            conf    = (kw_conf + fmt) / 2

            return {
                'is_national_id': conf >= 0.30,
                'confidence': conf,
                'detected_type': 'National ID' if conf >= 0.30 else 'Unknown',
            }
        except Exception as e:
            logger.error(f"_detect_id_type: {e}")
            return {'is_national_id': True, 'confidence': 0.45, 'detected_type': 'Unknown'}

    def _format_score(self, path):
        try:
            img = cv2.imread(path)
            if img is None: return 0.5
            h, w = img.shape[:2]
            ar = w / h
            if 1.4 < ar < 2.0:  return 0.90  # landscape
            if 0.5 < ar < 0.75: return 0.90  # portrait (rotated ID)
            return 0.60
        except:
            return 0.5

    def _detect_country(self, front, back=None):
        try:
            text = self._ocr_text(front)
            if back:
                text += " " + self._ocr_text(back)
            best, score = None, 0
            for country, p in self.ID_PATTERNS.items():
                s = sum(1 for k in p['keywords'] if k in text)
                if s > score:
                    best, score = country, s
            return {'country': best, 'score': score}
        except Exception as e:
            logger.error(f"_detect_country: {e}")
            return {'country': 'KENYA', 'score': 0}

    def _check_authenticity(self, path):
        try:
            img = cv2.imread(path)
            if img is None: return {'score': 0.65, 'risks': []}
            risks, score = [], 0.85
            lap = cv2.Laplacian(img, cv2.CV_64F).var()
            if lap < 30:   risks.append("Very blurry image");   score -= 0.15
            elif lap < 80: risks.append("Slightly blurry");     score -= 0.05
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if gray.std() < 20: risks.append("Low contrast");   score -= 0.05
            return {'score': max(0.50, min(0.95, score)), 'risks': risks}
        except Exception as e:
            logger.error(f"_check_authenticity: {e}")
            return {'score': 0.65, 'risks': []}

    def _extract_fields(self, front, back=None):
        try:
            text = self._ocr_text(front)
            if back: text += " " + self._ocr_text(back)
            risks, critical = [], False
            length = len(text.strip())
            if length < 20:
                risks.append("Very little text detected"); critical = True
            return {
                'risks': risks,
                'has_critical_issues': critical,
                'text_confidence': min(0.95, length / 60),
            }
        except:
            return {'risks': [], 'has_critical_issues': False, 'text_confidence': 0.5}


# ═══════════════════════════════════════════════════════════════
# NOTIFICATION HELPER
# ═══════════════════════════════════════════════════════════════
def _notify(db, user_id, ntype, title, body, link=None, actor_id=None):
    from models import Notification
    db.session.add(Notification(
        user_id=user_id, type=ntype, title=title,
        body=body, link=link, actor_id=actor_id,
    ))


# ═══════════════════════════════════════════════════════════════
# FLASK ROUTES
# ═══════════════════════════════════════════════════════════════
def register_verification_routes(app, db):
    from models import User, IDVerificationAudit

    # ── USER: upload ID ─────────────────────────────────────────────────
    @app.route("/upload_id", methods=["GET", "POST"])
    @login_required
    def upload_id():
        next_page = request.args.get("next", "")

        if request.method == "POST":
            front_file = request.files.get("id_front")
            back_file  = request.files.get("id_back")
            if not front_file or not back_file:
                flash("Please upload both the front and back sides of your ID.", "danger")
                return redirect(url_for("upload_id", next=next_page))

            allowed = {"png", "jpg", "jpeg", "pdf", "webp"}
            if (front_file.filename.rsplit(".", 1)[-1].lower() not in allowed or
                    back_file.filename.rsplit(".", 1)[-1].lower() not in allowed):
                flash("Invalid file type. Only JPG, PNG, WEBP or PDF allowed.", "danger")
                return redirect(url_for("upload_id", next=next_page))

            # Save files
            save_dir = os.path.join(app.root_path, "instance", "id_uploads")
            os.makedirs(save_dir, exist_ok=True)
            ts       = int(datetime.now().timestamp())
            front_fn = f"idf_{uuid.uuid4().hex}{os.path.splitext(secure_filename(front_file.filename))[1]}"
            back_fn  = f"idb_{uuid.uuid4().hex}{os.path.splitext(secure_filename(back_file.filename))[1]}"
            front_path = os.path.join(save_dir, front_fn)
            back_path  = os.path.join(save_dir, back_fn)

            try:
                front_file.save(front_path)
                back_file.save(back_path)
            except Exception as e:
                flash(f"File save failed: {e}", "danger")
                return redirect(url_for("upload_id", next=next_page))

            # Update user
            current_user.id_front_document     = front_fn
            current_user.id_back_document      = back_fn
            current_user.last_id_upload_at     = datetime.now(timezone.utc)
            current_user.id_retry_count        = (current_user.id_retry_count or 0) + 1
            current_user.id_submission_ip      = request.remote_addr

            # ── RUN OCR ─────────────────────────────────────────────────
            if ENABLE_OCR:
                try:
                    logger.info(f"▶ OCR starting for user {current_user.id}")
                    vr = NationalIDVerifier().verify(front_path, back_path)
                    logger.info(f"◀ OCR result: {vr['status']} | conf={vr['confidence']:.2%} | {vr['message']}")
                except Exception as e:
                    logger.error(f"OCR crashed: {e}", exc_info=True)
                    vr = {'status': 'manual_review', 'country': 'KENYA',
                          'confidence': 0.0, 'id_type_score': 0.0,
                          'authenticity_score': 0.0, 'is_national_id': True,
                          'message': 'OCR error', 'risks': [str(e)]}
            else:
                # OCR disabled → always queue for manual review
                vr = {'status': 'manual_review', 'country': 'KENYA',
                      'confidence': 0.0, 'id_type_score': 0.0,
                      'authenticity_score': 0.0, 'is_national_id': True,
                      'message': 'OCR disabled — manual review', 'risks': []}

            # ── HARD REJECT (not a national ID) ─────────────────────────
            if vr['status'] == 'rejected':
                current_user.is_verified           = False
                current_user.verification_status   = "rejected"
                current_user.manual_review_required = False
                current_user.manual_review_status  = "rejected"
                current_user.auto_rejection_reasons = vr['message']
                db.session.add(IDVerificationAudit(
                    user_id=current_user.id, verification_type="auto_rejected",
                    confidence_score=vr['confidence'],
                    content_score=vr['id_type_score'],
                    integrity_score=vr['authenticity_score'],
                    decision="rejected", decision_reason=vr['message'],
                ))
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    flash(f"Database error: {e}", "danger")
                    return redirect(url_for("upload_id", next=next_page))

                flash(f"❌ {vr['message']}", "danger")
                flash("Only national government-issued IDs are accepted. Please try again.", "warning")
                return redirect(url_for("upload_id", next=next_page))

            # ── AUTO APPROVED ────────────────────────────────────────────
            elif vr['status'] == 'verified':
                current_user.is_verified           = True
                current_user.verification_status   = "approved"
                current_user.manual_review_required = False
                current_user.manual_review_status  = "approved"
                current_user.detected_country      = vr['country']
                current_user.id_confidence_score   = vr['confidence']
                
                # Auto-enable selling capability after ID verification
                # (only if they haven't explicitly disabled it before)
                if not current_user.can_sell:
                    current_user.can_sell = True
                
                db.session.add(IDVerificationAudit(
                    user_id=current_user.id, verification_type="auto_approved",
                    confidence_score=vr['confidence'],
                    content_score=vr['id_type_score'],
                    integrity_score=vr['authenticity_score'],
                    decision="verified",
                    decision_reason=f"Auto-verified: {vr['message']}",
                ))
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    flash(f"Database error: {e}", "danger")
                    return redirect(url_for("upload_id", next=next_page))

                flash(f"✅ ID verified automatically! Country: {vr['country']} ({vr['confidence']:.0%} confidence)", "success")
                # Check if this was triggered by become_seller flow
                if next_page == "become_seller":
                    flash("🎉 You can now sell! You can both buy and sell on the platform.", "success")
                    return redirect(url_for("dashboard"))
                elif next_page == "post_service":
                    return redirect(url_for("post_service"))
                elif next_page == "toggle_seller_status":
                    return redirect(url_for("profile", username=current_user.username))
                return redirect(url_for("profile", username=current_user.username))

            # ── MANUAL REVIEW QUEUE ──────────────────────────────────────
            else:
                current_user.is_verified           = False
                current_user.verification_status   = "pending"
                current_user.manual_review_required = True
                current_user.manual_review_status  = "pending"
                current_user.detected_country      = vr.get('country')
                current_user.id_confidence_score   = vr['confidence']
                if vr.get('risks'):
                    current_user.id_validation_reasons = json.dumps(vr['risks'])

                db.session.add(IDVerificationAudit(
                    user_id=current_user.id, verification_type="manual_review",
                    confidence_score=vr['confidence'],
                    content_score=vr['id_type_score'],
                    integrity_score=vr['authenticity_score'],
                    decision="pending",
                    decision_reason=vr['message'],
                ))

                # Notify all admins
                admins = User.query.filter_by(role="admin").all()
                review_link = url_for("admin_review_id", user_id=current_user.id)
                for admin in admins:
                    _notify(db,
                        user_id  = admin.id,
                        ntype    = "system",
                        title    = "🆔 ID Needs Manual Review",
                        body     = (f"{current_user.display_name()} submitted their ID "
                                    f"(OCR confidence: {vr['confidence']:.0%})."),
                        link     = review_link,
                        actor_id = current_user.id,
                    )

                try:
                    db.session.commit()
                    logger.info(f"User {current_user.id} queued for manual review — "
                                f"{len(admins)} admin(s) notified")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Database error: {e}", "danger")
                    return redirect(url_for("upload_id", next=next_page))

                flash("📋 Your ID has been submitted for manual review.", "info")
                flash("You'll be notified within 24–48 hours once reviewed.", "info")
                return redirect(url_for("profile", username=current_user.username))

        # ── GET ──────────────────────────────────────────────────────────
        status = "upload"
        if current_user.verification_status == "approved":  status = "approved"
        elif current_user.verification_status == "rejected": status = "rejected"
        elif current_user.verification_status == "pending":  status = "pending"
        return render_template("upload_id.html", status=status, next=next_page)


    # ── ADMIN: pending list ──────────────────────────────────────────────
    @app.route("/admin/manual_reviews")
    @login_required
    def admin_manual_reviews():
        if current_user.role != "admin":
            flash("Access denied.", "danger")
            return redirect(url_for("index"))
        pending = User.query.filter_by(
            manual_review_required=True,
            manual_review_status="pending"
        ).order_by(User.last_id_upload_at.desc()).all()
        return render_template("admin/manual_reviews.html", users=pending)


    # ── ADMIN: review individual ─────────────────────────────────────────
    @app.route("/admin/review_id/<int:user_id>", methods=["GET", "POST"])
    @login_required
    def admin_review_id(user_id):
        if current_user.role != "admin":
            flash("Access denied.", "danger")
            return redirect(url_for("index"))

        user = User.query.get_or_404(user_id)

        if request.method == "POST":
            action = request.form.get("action")
            notes  = request.form.get("notes", "").strip()

            if action not in ("approve", "reject"):
                flash("Invalid action.", "danger")
                return redirect(url_for("admin_review_id", user_id=user_id))

            now = datetime.now(timezone.utc)

            if action == "approve":
                user.is_verified            = True
                user.verification_status    = "approved"
                user.manual_review_status   = "approved"
                user.manual_review_required = False
                user.manual_review_notes    = notes
                user.manual_reviewed_by     = current_user.id
                user.manual_reviewed_at     = now
                
                # Auto-enable selling capability after manual ID verification
                if not user.can_sell:
                    user.can_sell = True
                
                db.session.add(IDVerificationAudit(
                    user_id=user.id, verification_type="manual_approved",
                    confidence_score=1.0, decision="approved",
                    decision_reason=f"Manually approved. Notes: {notes}",
                    reviewed_by=current_user.id, reviewed_at=now,
                ))
                
                # Check if user was trying to become a seller
                selling_enabled = not getattr(user, '_was_seller_before', False) if hasattr(user, '_was_seller_before') else (not user.can_sell_before_verification)
                
                _notify(db,
                    user_id  = user.id,
                    ntype    = "system",
                    title    = "✅ ID Verified!",
                    body     = "Your identity has been verified. You can now post services on FreelancingHub.",
                    link     = url_for("dashboard"),
                    actor_id = current_user.id,
                )
                flash(f"✅ ID approved for {user.username}.", "success")
                
                # Notify user about selling capability if auto-enabled
                if user.can_sell:
                    _notify(db,
                        user_id  = user.id,
                        ntype    = "system",
                        title    = "🎉 Selling Enabled!",
                        body     = "Your ID has been verified and selling has been automatically enabled. You can now both buy and sell on the platform!",
                        link     = url_for("dashboard"),
                        actor_id = current_user.id,
                    )
                
                logger.info(f"Admin {current_user.id} approved user {user.id}")

            else:
                user.is_verified            = False
                user.verification_status    = "rejected"
                user.manual_review_status   = "rejected"
                user.manual_review_required = False
                user.manual_review_notes    = notes
                user.manual_reviewed_by     = current_user.id
                user.manual_reviewed_at     = now
                db.session.add(IDVerificationAudit(
                    user_id=user.id, verification_type="manual_rejected",
                    confidence_score=0.0, decision="rejected",
                    decision_reason=f"Manually rejected. Notes: {notes}",
                    reviewed_by=current_user.id, reviewed_at=now,
                ))
                reason_msg = f" Reason: {notes}" if notes else ""
                _notify(db,
                    user_id  = user.id,
                    ntype    = "system",
                    title    = "❌ ID Verification Failed",
                    body     = f"Your ID could not be verified.{reason_msg} Please re-upload a clearer photo.",
                    link     = url_for("upload_id"),
                    actor_id = current_user.id,
                )
                flash(f"❌ ID rejected for {user.username}.", "warning")
                logger.warning(f"Admin {current_user.id} rejected user {user.id}")

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Database error: {e}", "danger")
                return redirect(url_for("admin_review_id", user_id=user_id))

            return redirect(url_for("admin_manual_reviews"))

        # GET — build image URLs
        front_url = (url_for("serve_id_doc", filename=user.id_front_document)
                     if user.id_front_document else None)
        back_url  = (url_for("serve_id_doc", filename=user.id_back_document)
                     if user.id_back_document else None)

        return render_template("admin/review_id.html",
                               user=user, front_url=front_url, back_url=back_url)