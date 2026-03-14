"""
models_extra.py — Additional models for professional features.
Import alongside existing models in app.py.
"""
from models import db
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════
# SERVICE PACKAGES — Basic / Standard / Premium
# ═══════════════════════════════════════════════════════
class ServicePackage(db.Model):
    __tablename__ = 'service_package'
    id            = db.Column(db.Integer, primary_key=True)
    service_id    = db.Column(db.Integer, db.ForeignKey('service.id', ondelete='CASCADE'), nullable=False, index=True)
    tier          = db.Column(db.String(20), nullable=False)   # basic / standard / premium
    name          = db.Column(db.String(100), nullable=False)
    description   = db.Column(db.Text)
    price         = db.Column(db.Numeric(12,2), nullable=False)
    delivery_days = db.Column(db.Integer, default=3)
    revisions     = db.Column(db.Integer, default=1)           # -1 = unlimited
    features      = db.Column(db.JSON, default=list)           # ["Feature A","Feature B"]
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    service = db.relationship('Service', backref=db.backref('packages', lazy='dynamic',
                              cascade='all, delete-orphan'))


# ═══════════════════════════════════════════════════════
# EXTENDED ORDER — full workflow
# ═══════════════════════════════════════════════════════
    seller_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buyer_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id    = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    title         = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text)
    price         = db.Column(db.Numeric(12,2), nullable=False)
    delivery_days = db.Column(db.Integer, default=3)
    status        = db.Column(db.String(20), default='pending')
    # pending | accepted | declined | expired
    expires_at    = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    seller  = db.relationship('User',    foreign_keys=[seller_id])
    buyer   = db.relationship('User',    foreign_keys=[buyer_id])
    service = db.relationship('Service', foreign_keys=[service_id])




# ═══════════════════════════════════════════════════════
# CUSTOM OFFER — seller proposes a quote to a buyer
# ═══════════════════════════════════════════════════════
class CustomOffer(db.Model):
    __tablename__ = 'custom_offer'
    id            = db.Column(db.Integer, primary_key=True)
    seller_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buyer_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id    = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    title         = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text)
    price         = db.Column(db.Numeric(12,2), nullable=False)
    delivery_days = db.Column(db.Integer, default=3)
    status        = db.Column(db.String(20), default='pending')
    # pending | accepted | declined | expired
    expires_at    = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    seller  = db.relationship('User',    foreign_keys=[seller_id])
    buyer   = db.relationship('User',    foreign_keys=[buyer_id])
    service = db.relationship('Service', foreign_keys=[service_id])

# ═══════════════════════════════════════════════════════
# SERVICE VIEWS — for analytics
# ═══════════════════════════════════════════════════════
class ServiceView(db.Model):
    __tablename__ = 'service_view'
    id         = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    viewer_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    ip_hash    = db.Column(db.String(64))
    viewed_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    service = db.relationship('Service', backref=db.backref('views', lazy='dynamic',
                              cascade='all, delete-orphan'))


# ═══════════════════════════════════════════════════════
# FAVORITES / WISHLIST
# ═══════════════════════════════════════════════════════
class Favorite(db.Model):
    __tablename__ = 'favorite'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id', ondelete='CASCADE'),
                           nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('user_id', 'service_id', name='uq_favorite'),)

    user    = db.relationship('User',    backref=db.backref('favorites', lazy='dynamic',
                              cascade='all, delete-orphan'))
    service = db.relationship('Service', backref=db.backref('favorited_by', lazy='dynamic'))


# ═══════════════════════════════════════════════════════
# SELLER LEVELS
# ═══════════════════════════════════════════════════════
class SellerLevel(db.Model):
    __tablename__ = 'seller_level'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                                 nullable=False, unique=True)
    level            = db.Column(db.String(30), default='new_seller')
    # new_seller | active_seller | level_1 | level_2 | top_rated
    total_orders     = db.Column(db.Integer, default=0)
    completed_orders = db.Column(db.Integer, default=0)
    total_earned     = db.Column(db.Numeric(12,2), default=0)
    avg_rating       = db.Column(db.Float, default=0.0)
    on_time_rate     = db.Column(db.Float, default=100.0)
    last_evaluated   = db.Column(db.DateTime)
    updated_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                                 onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('seller_level', uselist=False,
                           cascade='all, delete-orphan'))

    LEVEL_THRESHOLDS = {
        'new_seller':    {'orders': 0,  'rating': 0.0, 'label': 'New Seller',    'color': '#64748b'},
        'active_seller': {'orders': 1,  'rating': 0.0, 'label': 'Active Seller', 'color': '#3b82f6'},
        'level_1':       {'orders': 10, 'rating': 4.0, 'label': 'Level 1',       'color': '#22c55e'},
        'level_2':       {'orders': 50, 'rating': 4.5, 'label': 'Level 2',       'color': '#f59e0b'},
        'top_rated':     {'orders': 100,'rating': 4.8, 'label': 'Top Rated',     'color': '#00ffc8'},
    }

    def recalculate(self):
        completed = self.completed_orders
        rating    = self.avg_rating
        if completed >= 100 and rating >= 4.8:
            self.level = 'top_rated'
        elif completed >= 50 and rating >= 4.5:
            self.level = 'level_2'
        elif completed >= 10 and rating >= 4.0:
            self.level = 'level_1'
        elif completed >= 1:
            self.level = 'active_seller'
        else:
            self.level = 'new_seller'
        self.last_evaluated = datetime.now(timezone.utc)