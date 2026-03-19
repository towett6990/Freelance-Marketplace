# 🔧 Security Remediation Work Plan
## Freelance Marketplace - Priority-Based Fix Schedule

---

## 🚨 PHASE 1: CRITICAL - Fix Immediately (Week 1)

### 1.1 Rotate All Exposed Credentials ⚡
**Time**: 2 hours | **Priority**: P0

| Credential | Action | New Value Source |
|------------|--------|------------------|
| MySQL Password | Generate new strong password | `openssl rand -base64 24` |
| M-Pesa Keys | Regenerate in Daraja portal | sandbox.safaricom.co.ke |
| Google API Key | Revoke in Google Cloud Console | Regenerate new key |
| Email Password | Generate app-specific password | Gmail 2FA app passwords |
| Admin Password | Change immediately | Use password manager |

**Files to update**: `.env`, database (for MySQL)

---

### 1.2 Fix SQL Injection ⚡
**Time**: 1 hour | **Priority**: P0

**File**: [`app.py:630`](app.py:630)

```python
# BEFORE (VULNERABLE)
results = Message.query.filter(
    Message.conversation_id == conversation_id,
    Message.content.ilike(f"%{search_term}%")
).order_by(Message.timestamp.desc()).all()

# AFTER (SAFE)
from sqlalchemy import literal
# Escape special LIKE characters to prevent injection
escaped = search_term.replace('%', r'\%').replace('_', r'\_')
results = Message.query.filter(
    Message.conversation_id == conversation_id,
    Message.content.ilike(f"%{escaped}%", escape='\\')
).order_by(Message.timestamp.desc()).all()
```

---

### 1.3 Enable Production Settings ⚡
**Time**: 30 minutes | **Priority**: P0

**File**: `.env`
```env
# Change from:
DEBUG=True
TESTING=True
FLASK_ENV=development

# To:
DEBUG=False
TESTING=False
FLASK_ENV=production
```

---

### 1.4 Fix CORS Configuration ⚡
**Time**: 15 minutes | **Priority**: P0

**File**: [`app.py:322`](app.py:322)

```python
# BEFORE
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# AFTER - Replace "*" with your domain
socketio = SocketIO(app, cors_allowed_origins=["https://yourdomain.com"], async_mode="threading")
```

---

### 1.5 Fix Secret Key ⚡
**Time**: 15 minutes | **Priority**: P0

**File**: `.env`
```env
# Generate new key
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

---

## 🚀 PHASE 2: HIGH PRIORITY - This Week (Week 2)

### 2.1 Implement Brute Force Protection
**Time**: 2 hours | **Priority**: P1

Add rate limiting for login in `app.py`:

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=_limiter_storage,
)

# Add to login route
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 15 minutes")
def login():
    # ... existing code
```

---

### 2.2 Add Security Headers
**Time**: 1 hour | **Priority**: P1

Add to `app.py`:

```python
@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data: https:; font-src 'self' https://cdnjs.cloudflare.com;"
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
```

---

### 2.3 Secure File Upload
**Time**: 3 hours | **Priority**: P1

**File**: [`app.py:128-195`](app.py:128-195)

```python
import magic

def validate_file_content(file_storage):
    """Validate actual file content, not just extension"""
    # Read first 2048 bytes for magic byte detection
    file_storage.stream.seek(0)
    header = file_storage.stream.read(2048)
    file_storage.stream.seek(0)
    
    # Check magic bytes for images
    mime = magic.from_buffer(header, mime=True)
    allowed_mimes = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    
    if mime not in allowed_mimes:
        raise ValueError(f"Invalid file content type: {mime}")
    
    return True
```

Also reduce max file sizes:
```python
MAX_IMAGE_SIZE_MB = 5   # Reduced from 10
MAX_VIDEO_SIZE_MB = 50  # Reduced from 100
```

---

### 2.4 Fix IDOR Vulnerabilities
**Time**: 2 hours | **Priority**: P1

Add ownership checks to offer routes in [`features_routes.py`](features_routes.py):

```python
@features_bp.route('/offer/<int:oid>')
@login_required
def offer_detail(oid):
    offer = CustomOffer.query.get_or_404(oid)
    # Add explicit check
    if current_user.id not in (offer.buyer_id, offer.seller_id) and current_user.role != 'admin':
        abort(403)  # Forbidden
    return render_template('offer_detail.html', offer=offer)
```

---

### 2.5 M-Pesa Callback Validation
**Time**: 4 hours | **Priority**: P1

Create a callback validation module. Add signature verification:

```python
def validate_mpesa_callback(request_data, signature):
    """Validate M-Pesa callback authenticity"""
    # Verify using your security credential
    expected_signature = generate_hmac_signature(request_data)
    return hmac.compare_digest(signature, expected_signature)
```

---

## ⚡ PHASE 3: MEDIUM PRIORITY - This Month (Weeks 3-4)

### 3.1 Strengthen Password Policy
**Time**: 1 hour | **Priority**: P2

**File**: [`forms.py`](forms.py)

```python
from wtforms.validators import Regexp

class RegistrationForm(FlaskForm):
    password = PasswordField("Password", validators=[
        DataRequired(), 
        Length(min=8, message="Password must be at least 8 characters"),
        Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]',
               message="Password must contain uppercase, lowercase, number, and special character")
    ])
```

---

### 3.2 Generic Error Messages
**Time**: 1 hour | **Priority**: P2

**File**: [`app.py`](app.py)

```python
@app.errorhandler(Exception)
def handle_error(e):
    # Log full error internally
    app.logger.error(f"Error: {str(e)}", exc_info=True)
    # Return generic message to user
    return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500
```

---

### 3.3 Session Configuration
**Time**: 1 hour | **Priority**: P2

Add session config in `app.py`:

```python
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
```

---

### 3.4 Manual Review for ID Verification
**Time**: 2 hours | **Priority**: P2

**File**: [`verification_system.py:38`](verification_system.py:38)

```python
# Change from auto-approval to manual review only
ENABLE_OCR = True
AUTO_APPROVE_THRESHOLD = 0.95  # Only auto-approve at 95%+ confidence

# In verify method:
if confidence >= AUTO_APPROVE_THRESHOLD and not ocr['has_critical_issues']:
    result['status'] = 'verified'
else:
    result['status'] = 'manual_review'  # Default to manual review
```

---

## 📋 PHASE 4: LOW PRIORITY - Ongoing

### 4.1 HTTPS Enforcement
Add to your web server (nginx/apache) or Flask:

```python
@app.before_request
def require_https():
    if not request.is_secure and app.env == 'production':
        return redirect(request.url.replace('http://', 'https://'), code=301)
```

---

### 4.2 Audit Logging
Add comprehensive audit trail:

```python
def log_audit(user_id, action, details):
    audit = AuditLog(
        user_id=user_id,
        action=action,
        details=json.dumps(details),
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()
```

---

### 4.3 Database Backup & Security
- Enable encrypted backups
- Restrict database user permissions (least privilege)
- Enable slow query log for monitoring

---

## 📊 Implementation Timeline

| Week | Tasks | Deliverables |
|------|-------|--------------|
| 1 | Phase 1 (Critical) | Credentials rotated, SQL injection fixed, production mode enabled |
| 2 | Phase 2.1-2.3 | Brute force protection, security headers, file upload security |
| 3 | Phase 2.4-2.5 | IDOR fixes, M-Pesa validation |
| 4 | Phase 3 | Password policy, error messages, sessions |
| Ongoing | Phase 4 | HTTPS, audit logging, monitoring |

---

## ✅ Verification Checklist

After each phase, verify:

- [ ] No credentials in git history
- [ ] SQL injection test passes (use SQLMap)
- [ ] CORS restricted to domain only
- [ ] DEBUG=False in production
- [ ] Security headers present (use securityheaders.com)
- [ ] File uploads reject invalid content types
- [ ] All sensitive endpoints require authentication
- [ ] Passwords meet complexity requirements
- [ ] Session expires after 30 minutes inactivity

---

## 🧪 Testing Resources

- **SQL Injection**: `sqlmap -u "http://target/search?q=test"`
- **Security Headers**: https://securityheaders.com
- **SSL Labs**: https://www.ssllabs.com/ssltest/
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
