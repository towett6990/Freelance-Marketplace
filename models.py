"""
Database models for Freelance Marketplace
All SQLAlchemy model definitions
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


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
    
    # Selling capability - allows user to be both buyer and seller
    can_sell = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_code = db.Column(db.String(6), nullable=True)
    email_code_expires_at = db.Column(db.DateTime, nullable=True)

    # ID verification fields
    id_document = db.Column(db.String(256), nullable=True)
    id_image = db.Column(db.String(255))
    verification_status = db.Column(db.String(20), nullable=True, default=None)  # None = no ID submitted yet, pending = submitted, awaiting review, approved, rejected
    id_verification_score = db.Column(db.Float, default=0.0)
    id_verified = db.Column(db.Boolean, default=False)
    vision_message = db.Column(db.String(500))
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
    resubmission_notes = db.Column(db.Text, nullable=True)

    # M-Pesa payout info
    mpesa_phone = db.Column(db.String(15), nullable=True)

    # Relationships
    services = db.relationship(
        "Service",
        back_populates="seller",
        cascade="all, delete-orphan"
    )

    orders = db.relationship(
        "Order",
        foreign_keys="Order.buyer_id",
        back_populates="buyer",
        cascade="all, delete-orphan"
    )

    sales = db.relationship(
        "Order",
        foreign_keys="Order.seller_id",
        back_populates="seller"
    )

    buyer_payments = db.relationship(
        "Payment",
        foreign_keys="Payment.buyer_id",
        back_populates="buyer",
        cascade="all, delete-orphan"
    )

    seller_payments = db.relationship(
        "Payment",
        foreign_keys="Payment.seller_id",
        back_populates="seller"
    )

    verification_audits = db.relationship(
        "IDVerificationAudit",
        foreign_keys="IDVerificationAudit.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )

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
        from werkzeug.security import check_password_hash
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
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship back to service
    service = db.relationship("Service", back_populates="images")


class ServiceVideo(db.Model):
    """Related table for service videos"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship back to service
    service = db.relationship("Service", back_populates="videos")


class Category(db.Model):
    """Model for service categories"""
    __tablename__ = 'category'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)  # e.g., "Web Development"
    slug = db.Column(db.String(120), unique=True, nullable=False)  # e.g., "web-development"
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))  # e.g., "code"
    
    # Layout type: how services are displayed
    layout_type = db.Column(db.String(50), nullable=False)  # 'freelancer', 'product', 'property', 'generic'
    
    # Price type
    price_type = db.Column(db.String(50), nullable=False)  # 'fixed', 'hourly', 'negotiable'
    
    # Custom fields configuration (JSON)
    custom_fields = db.Column(db.JSON, default=list)
    # Format: [
    #   {
    #     'name': 'skills',
    #     'label': 'Skills',
    #     'type': 'multi-select',
    #     'required': True,
    #     'options': ['React', 'Node.js', 'Python', ...]
    #   },
    #   ...
    # ]
    
    # Fields to display on card
    card_fields = db.Column(db.JSON, default=list)
    
    # Fields to display on detail page
    detail_fields = db.Column(db.JSON, default=list)
    
    # Available filters for this category
    available_filters = db.Column(db.JSON, default=list)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    services = db.relationship('Service', back_populates='category', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'icon': self.icon,
            'layout_type': self.layout_type,
            'price_type': self.price_type,
            'custom_fields': self.custom_fields or [],
            'card_fields': self.card_fields or [],
            'detail_fields': self.detail_fields or [],
            'available_filters': self.available_filters or []
        }
    
    def to_json(self):
        """Return JSON-compatible dictionary for API responses"""
        import json
        return json.dumps(self.to_dict())
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    @staticmethod
    def get_field_config(field_name, category_slug='web-development'):
        """Get specific field configuration for a category"""
        category = Category.query.filter_by(slug=category_slug).first()
        if not category:
            return None
        
        for field in category.custom_fields:
            if field['name'] == field_name:
                return field
        
        return None

    @staticmethod
    def get_all_filter_options(category_slug='web-development'):
        """Get all filter options for a category"""
        category = Category.query.filter_by(slug=category_slug).first()
        if not category:
            return {}
        
        options = {}
        for field in category.custom_fields:
            if 'options' in field:
                options[field['name']] = field['options']
        
        return options



class Service(db.Model):
    __tablename__ = 'service'
    
    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    
    # NEW: Foreign key to Category (required for multi-category system)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False, index=True)

    # Relationships
    seller = db.relationship(
        "User",
        back_populates="services"
    )
    
    # NEW: Relationship to Category
    category = db.relationship('Category', back_populates='services')

    # Core fields
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    currency = db.Column(db.String(8), nullable=False, default='KES')
    quality = db.Column(db.String(32), nullable=True)
    
    # OLD: Keep for backward compatibility - legacy category as string
    category_old = db.Column(db.String(120), nullable=True)  # Legacy field
    
    # NEW: Custom data for category-specific fields (JSON)
    # Example: {'skills': ['React', 'Node.js'], 'hourly_rate': 2500, 'experience_level': 'Expert', ...}
    custom_data = db.Column(db.JSON, default=dict)
    
    contact_info = db.Column(db.Text, nullable=True)  # JSON string
    image_filenames = db.Column(db.Text, nullable=True)
    video_filenames = db.Column(db.Text, nullable=True)
    contact = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_sold = db.Column(db.Boolean, default=False, nullable=False)


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
    
    @property
    def contact_methods(self):
        """Return parsed contact methods dict"""
        if self.contact_info:
            try:
                import json
                return json.loads(self.contact_info)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    # Rating methods
    def get_average_rating(self):
        """Calculate average overall rating for this service"""
        reviews = self.reviews.all()
        if not reviews:
            return 0.0
        total = sum(r.overall_rating for r in reviews)
        return round(total / len(reviews), 1)
    
    def get_review_count(self):
        """Get total number of reviews"""
        return self.reviews.count()
    
    def get_detailed_ratings(self):
        """Get average rating for each category"""
        reviews = self.reviews.all()
        if not reviews:
            return {
                'overall': 0.0,
                'communication': 0.0,
                'quality': 0.0,
                'timeliness': 0.0,
                'count': 0
            }
        
        # Calculate averages
        overall_avg = sum(r.overall_rating for r in reviews) / len(reviews)
        
        communication_ratings = [r.communication_rating for r in reviews if r.communication_rating]
        communication_avg = sum(communication_ratings) / len(communication_ratings) if communication_ratings else 0.0
        
        quality_ratings = [r.quality_rating for r in reviews if r.quality_rating]
        quality_avg = sum(quality_ratings) / len(quality_ratings) if quality_ratings else 0.0
        
        timeliness_ratings = [r.timeliness_rating for r in reviews if r.timeliness_rating]
        timeliness_avg = sum(timeliness_ratings) / len(timeliness_ratings) if timeliness_ratings else 0.0
        
        return {
            'overall': round(overall_avg, 1),
            'communication': round(communication_avg, 1),
            'quality': round(quality_avg, 1),
            'timeliness': round(timeliness_avg, 1),
            'count': len(reviews)
        }


class Order(db.Model):
    """Order model for tracking service purchases"""
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(8), nullable=False, default='KES')

    # Order status
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, paid, completed, cancelled

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    title = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    buyer_instructions = db.Column(db.Text, nullable=True)
    deliverables = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    package_id = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    dispute_reason = db.Column(db.Text, nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

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
        nullable=True
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
                import json
                return json.loads(self.image_filenames)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @property
    def video_list(self):
        """Return list of video filenames"""
        if self.video_filenames:
            try:
                import json
                return json.loads(self.video_filenames)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @property
    def contact_methods(self):
        """Return parsed contact methods dict"""
        if self.contact_info:
            try:
                import json
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
        return []


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)

    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(256), nullable=True)
    
    # Location field for sharing location in messages
    location_id = db.Column(db.Integer, db.ForeignKey("location.id"), nullable=True)

    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    conversation = db.relationship('Conversation', back_populates='messages')
    location = db.relationship('Location', backref=db.backref('messages', lazy=True))


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user1 = db.relationship("User", foreign_keys=[user1_id])
    user2 = db.relationship("User", foreign_keys=[user2_id])
    messages = db.relationship('Message', back_populates='conversation', cascade='all, delete-orphan')


# ========================
# Location Model
# ========================
class Location(db.Model):
    """Model for storing user location data"""
    __tablename__ = 'location'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(500), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(120), nullable=True)
    accuracy = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    shared_with = db.Column(db.JSON, default=list)
    
    user = db.relationship('User', backref=db.backref('locations', lazy='dynamic', cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'shared_with': self.shared_with or []
        }
    
    def is_expired(self):
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f'<Location {self.user_id} - {self.city}>'


# ============================================================
# CALL MODEL - For voice/video call tracking
# ============================================================
class Call(db.Model):
    """Model for tracking voice/video calls"""
    __tablename__ = "call"
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    caller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    call_type = db.Column(db.String(20), nullable=False)  # 'voice' or 'video'
    status = db.Column(db.String(20), nullable=False, default='ringing')  # 'ringing', 'accepted', 'rejected', 'ended'
    duration = db.Column(db.Integer, default=0)  # Duration in seconds
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    conversation = db.relationship("Conversation", backref="calls")
    caller = db.relationship("User", foreign_keys=[caller_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class MessageNotification(db.Model):
    """Model for tracking message notifications"""
    __tablename__ = "message_notification"
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("message.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_seen = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(50), default='message_received')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    message = db.relationship("Message", backref="notifications")
    user = db.relationship("User", backref="notifications")


# ============================================================
# Q&A MODEL
# ============================================================
class Question(db.Model):
    """Buyer questions and seller answers on service pages"""
    __tablename__ = 'question'

    id         = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False, index=True)
    asker_id   = db.Column(db.Integer, db.ForeignKey('user.id'),    nullable=False, index=True)

    body       = db.Column(db.Text, nullable=False)
    answer     = db.Column(db.Text, nullable=True)
    answered_at= db.Column(db.DateTime, nullable=True)
    is_public  = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    service = db.relationship('Service',
        backref=db.backref('questions', lazy='dynamic', cascade='all, delete-orphan'))
    asker   = db.relationship('User',
        backref=db.backref('questions_asked', lazy='dynamic'))

    @property
    def response_time_hours(self):
        """Hours between question and answer (None if unanswered)."""
        if self.answered_at and self.created_at:
            delta = self.answered_at - self.created_at
            return round(delta.total_seconds() / 3600, 1)
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'body': self.body,
            'answer': self.answer,
            'answered_at': self.answered_at.isoformat() if self.answered_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'asker': self.asker.display_name() if self.asker else 'Anonymous',
            'response_time_hours': self.response_time_hours,
        }

    def __repr__(self):
        return f'<Question id={self.id} service={self.service_id} answered={bool(self.answer)}>'


# ============================================================
# UNIFIED NOTIFICATION MODEL
# ============================================================
class Notification(db.Model):
    """
    Unified notification model for all platform events.
    Types: message, question, answer, payment, payment_received, review, order, system
    """
    __tablename__ = 'notification'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    type        = db.Column(db.String(40), nullable=False, index=True)
    title       = db.Column(db.String(120), nullable=False)
    body        = db.Column(db.Text, nullable=True)
    link        = db.Column(db.String(255), nullable=True)
    is_read     = db.Column(db.Boolean, default=False, index=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    actor_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    service_id  = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)

    user  = db.relationship('User', foreign_keys=[user_id],
                            backref=db.backref('notifications_received',
                                               lazy='dynamic', cascade='all, delete-orphan'))
    actor = db.relationship('User', foreign_keys=[actor_id])

    ICONS = {
        'message':          'fas fa-comment-dots',
        'question':         'fas fa-question-circle',
        'answer':           'fas fa-reply',
        'payment':          'fas fa-check-circle',
        'payment_received': 'fas fa-wallet',
        'review':           'fas fa-star',
        'order':            'fas fa-shopping-bag',
        'system':           'fas fa-bell',
    }
    COLORS = {
        'message':          '#00d4ff',
        'question':         '#a855f7',
        'answer':           '#00ffc8',
        'payment':          '#22c55e',
        'payment_received': '#00ffc8',
        'review':           '#eab308',
        'order':            '#f97316',
        'system':           '#a0a0a0',
    }

    @property
    def icon(self):
        return self.ICONS.get(self.type, 'fas fa-bell')

    @property
    def color(self):
        return self.COLORS.get(self.type, '#a0a0a0')

    @property
    def time_ago(self):
        now   = datetime.now(timezone.utc)
        ts    = self.created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = now - ts
        s = int(delta.total_seconds())
        if s < 60:    return 'just now'
        if s < 3600:  return f'{s//60}m ago'
        if s < 86400: return f'{s//3600}h ago'
        return f'{s//86400}d ago'

    def to_dict(self):
        return {
            'id':         self.id,
            'type':       self.type,
            'title':      self.title,
            'body':       self.body,
            'link':       self.link,
            'is_read':    self.is_read,
            'icon':       self.icon,
            'color':      self.color,
            'time_ago':   self.time_ago,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Notification {self.type} user={self.user_id} read={self.is_read}>'


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


# ============================================================
# REVIEW MODEL - For service ratings and reviews
# ============================================================
class Review(db.Model):
    """Model for service reviews and ratings"""
    __tablename__ = 'review'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys with indexes for fast queries
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Rating fields (1-5 stars)
    overall_rating = db.Column(db.Integer, nullable=False)  # Overall: 1-5 stars (required)
    communication_rating = db.Column(db.Integer, nullable=True)  # Communication: 1-5 (optional)
    quality_rating = db.Column(db.Integer, nullable=True)  # Quality: 1-5 (optional)
    timeliness_rating = db.Column(db.Integer, nullable=True)  # Timeliness: 1-5 (optional)
    
    # Review text
    comment = db.Column(db.Text, nullable=True)  # Written review/comment
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships (connections to other tables)
    service = db.relationship(
        'Service',
        backref=db.backref('reviews', lazy='dynamic', cascade='all, delete-orphan')
    )
    buyer = db.relationship(
        'User',
        foreign_keys=[buyer_id],
        backref=db.backref('reviews_given', lazy='dynamic', cascade='all, delete-orphan')
    )
    seller = db.relationship(
        'User',
        foreign_keys=[seller_id],
        backref=db.backref('reviews_received', lazy='dynamic')
    )
    
    def to_dict(self):
        """Convert review to dictionary for JSON responses"""
        return {
            'id': self.id,
            'service_id': self.service_id,
            'buyer_id': self.buyer_id,
            'buyer_name': self.buyer.display_name() if self.buyer else 'Unknown',
            'buyer_avatar': self.buyer.avatar if self.buyer else None,
            'overall_rating': self.overall_rating,
            'communication_rating': self.communication_rating,
            'quality_rating': self.quality_rating,
            'timeliness_rating': self.timeliness_rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<Review service_id={self.service_id} rating={self.overall_rating} stars>'