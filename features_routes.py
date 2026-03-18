"""
features_routes.py  — All new professional feature routes.
Register with: app.register_blueprint(features_bp)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib, os
from models import db, Service, User, Notification, Payment
from models_extra import (ServicePackage, CustomOffer, ServiceView, Favorite, SellerLevel)

features_bp = Blueprint('features', __name__)

PLATFORM_FEE_PCT = Decimal('0.05')   # 5%

# ─── helpers ────────────────────────────────────────────────────────────────
def _notify(user_id, msg, type='info', link=None):
    try:
        n = Notification(user_id=user_id, body=msg, type=category, link=link)
        db.session.add(n)
        db.session.commit()
    except Exception:
        db.session.rollback()

def _get_or_create_level(user_id):
    sl = SellerLevel.query.filter_by(user_id=user_id).first()
    if not sl:
        sl = SellerLevel(user_id=user_id)
        db.session.add(sl)
        db.session.commit()
    return sl


# ════════════════════════════════════════════════════════════════════════════
# SERVICE PACKAGES
# ════════════════════════════════════════════════════════════════════════════
@features_bp.route('/service/<int:sid>/packages', methods=['GET'])
def view_packages(sid):
    service  = Service.query.get_or_404(sid)
    packages = ServicePackage.query.filter_by(service_id=sid, is_active=True).all()
    is_freelancer = getattr(service.category, 'layout_type', 'generic') == 'freelancer' if service.category else False
    return render_template('packages_view.html', service=service, packages=packages, is_freelancer=is_freelancer)


@features_bp.route('/service/<int:sid>/packages/manage', methods=['GET', 'POST'])
@login_required
def manage_packages(sid):
    service = Service.query.get_or_404(sid)
    if service.seller_id != current_user.id and current_user.role != "admin":
        abort(403)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save':
            tiers = ['basic', 'standard', 'premium']
            for tier in tiers:
                if not request.form.get(f'{tier}_price'): continue
                pkg = ServicePackage.query.filter_by(service_id=sid, tier=tier).first()
                if not pkg:
                    pkg = ServicePackage(service_id=sid, tier=tier, seller_id=current_user.id)
                    db.session.add(pkg)
                pkg.name          = request.form.get(f'{tier}_name', tier.title())
                pkg.description   = request.form.get(f'{tier}_desc', '')
                pkg.price         = Decimal(request.form.get(f'{tier}_price', '0'))
                days_val = request.form.get(f'{tier}_days', '').strip()
                pkg.delivery_days = int(days_val) if days_val else None
                pkg.revisions     = int(request.form.get(f'{tier}_revisions', 1))
                raw_feats = request.form.get(f'{tier}_features', '')
                pkg.features      = [f.strip() for f in raw_feats.split('\n') if f.strip()]
                pkg.is_active     = True
            db.session.commit()
            flash('Packages saved successfully!', 'success')
            return redirect(url_for('features.manage_packages', sid=sid))
        elif action == 'delete':
            tier = request.form.get('tier')
            pkg  = ServicePackage.query.filter_by(service_id=sid, tier=tier).first()
            if pkg:
                db.session.delete(pkg)
                db.session.commit()
            flash(f'{tier.title()} package removed.', 'info')
            return redirect(url_for('features.manage_packages', sid=sid))

    packages = {p.tier: p for p in ServicePackage.query.filter_by(service_id=sid).all()}
    is_freelancer = getattr(service.category, 'layout_type', 'generic') == 'freelancer' if service.category else False
    return render_template('packages_manage.html', service=service, packages=packages, is_freelancer=is_freelancer)


# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# CUSTOM OFFERS
# ════════════════════════════════════════════════════════════════════════════
@features_bp.route('/offer/send/<int:buyer_id>', methods=['GET', 'POST'])
@login_required
def send_offer(buyer_id):
    buyer = User.query.get_or_404(buyer_id)
    if not current_user.can_sell:
        flash('Only users with selling capabilities can send custom offers.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        offer = CustomOffer(
            seller_id     = current_user.id,
            buyer_id      = buyer_id,
            title         = request.form.get('title', ''),
            description   = request.form.get('description', ''),
            price         = Decimal(request.form.get('price', '0')),
            delivery_days = int(request.form.get('delivery_days', 3)),
            expires_at    = datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(offer)
        db.session.commit()
        _notify(buyer_id, f'{current_user.username} sent you a custom offer: {offer.title}',
                'offer', link=f'/offer/{offer.id}')
        flash('Custom offer sent!', 'success')
        return redirect(url_for('profile', username=buyer.username))

    return render_template('send_offer.html', buyer=buyer)


@features_bp.route('/offer/<int:oid>')
@login_required
def offer_detail(oid):
    offer = CustomOffer.query.get_or_404(oid)
    # PHASE 2 FIX: Explicit IDOR protection - check ownership
    if current_user.id not in (offer.buyer_id, offer.seller_id) and current_user.role != 'admin':
        abort(403)
    return render_template('offer_detail.html', offer=offer)


@features_bp.route('/offer/<int:oid>/respond', methods=['POST'])
@login_required
def respond_offer(oid):
    offer = CustomOffer.query.get_or_404(oid)
    # PHASE 2 FIX: Explicit IDOR protection - only buyer can respond
    if offer.buyer_id != current_user.id and current_user.role != 'admin':
        abort(403)
    action = request.form.get('action')
    if action == 'accept':
        offer.status = 'accepted'
        db.session.commit()
        _notify(offer.seller_id, f'Your custom offer was accepted by {current_user.username}!',
                'offer', link=f'/offer/{oid}')
        flash('Offer accepted! Proceed to place the order.', 'success')
    elif action == 'decline':
        offer.status = 'declined'
        db.session.commit()
        _notify(offer.seller_id, f'Your custom offer was declined by {current_user.username}.', 'offer')
        flash('Offer declined.', 'info')
    return redirect(url_for('features.offer_detail', oid=oid))


@features_bp.route('/my-offers')
@login_required
def my_offers():
    sent     = CustomOffer.query.filter_by(seller_id=current_user.id)                   .order_by(CustomOffer.created_at.desc()).all()
    received = CustomOffer.query.filter_by(buyer_id=current_user.id)                   .order_by(CustomOffer.created_at.desc()).all()
    return render_template('my_offers.html', sent=sent, received=received)


# ════════════════════════════════════════════════════════════════════════════
# FAVORITES
# ════════════════════════════════════════════════════════════════════════════
@features_bp.route('/favorite/<int:sid>', methods=['POST'])
@login_required
def toggle_favorite(sid):
    service = Service.query.get_or_404(sid)
    fav = Favorite.query.filter_by(user_id=current_user.id, service_id=sid).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        if request.is_json:
            return jsonify(favorited=False)
        flash('Removed from favorites.', 'info')
    else:
        fav = Favorite(user_id=current_user.id, service_id=sid)
        db.session.add(fav)
        db.session.commit()
        if request.is_json:
            return jsonify(favorited=True)
        flash('Added to favorites!', 'success')
    return redirect(request.referrer or url_for('service_detail', service_id=sid))


@features_bp.route('/favorites')
@login_required
def my_favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id)               .order_by(Favorite.created_at.desc()).all()
    return render_template('my_favorites.html', favorites=favs)


# ════════════════════════════════════════════════════════════════════════════
# SELLER ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
@features_bp.route('/analytics')
@login_required
def seller_analytics():
    if not current_user.can_sell:
        flash('Analytics available for users with selling capabilities only.', 'warning')
        return redirect(url_for('index'))

    services = Service.query.filter_by(seller_id=current_user.id).all()
    sids     = [s.id for s in services]

    # Views last 30 days
    since = datetime.utcnow() - timedelta(days=30)
    from sqlalchemy import func
    total_views = ServiceView.query.filter(
        ServiceView.service_id.in_(sids),
        ServiceView.viewed_at >= since
    ).count() if sids else 0

    # Views per day (last 14 days)
    daily_views = []
    for i in range(13, -1, -1):
        day_start = datetime.utcnow().replace(hour=0,minute=0,second=0,microsecond=0) - timedelta(days=i)
        day_end   = day_start + timedelta(days=1)
        cnt = ServiceView.query.filter(
            ServiceView.service_id.in_(sids),
            ServiceView.viewed_at >= day_start,
            ServiceView.viewed_at < day_end
        ).count() if sids else 0
        daily_views.append({'date': day_start.strftime('%b %d'), 'count': cnt})

    # Earnings from M-Pesa payments (seller receives completed payments)
    payments        = Payment.query.filter_by(seller_id=current_user.id, status='completed').all()
    total_earned    = sum(float(p.amount or 0) for p in payments)
    this_month      = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_earned    = sum(float(p.amount or 0) for p in payments
                          if p.created_at and p.created_at >= this_month)
    total_orders    = len(payments)
    completed_orders= len(payments)
    pending_orders  = Payment.query.filter_by(seller_id=current_user.id, status='pending').count()

    # Monthly earnings chart (last 6 months)
    monthly = []
    for i in range(5, -1, -1):
        m_start = (datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i*30)).replace(day=1)
        m_end   = (m_start + timedelta(days=32)).replace(day=1)
        earn    = sum(float(p.amount or 0) for p in payments
                      if p.created_at and m_start <= p.created_at < m_end)
        monthly.append({'month': m_start.strftime('%b %Y'), 'earned': earn})

    # Favorites count
    fav_count = Favorite.query.filter(Favorite.service_id.in_(sids)).count() if sids else 0

    # Seller level
    sl = _get_or_create_level(current_user.id)

    # Top services by views
    top_services = []
    for s in services:
        v = ServiceView.query.filter(ServiceView.service_id==s.id,
                                     ServiceView.viewed_at>=since).count()
        top_services.append({'service': s, 'views': v})
    top_services.sort(key=lambda x: x['views'], reverse=True)

    return render_template('seller_analytics.html',
        services=services, total_views=total_views, daily_views=daily_views,
        total_orders=total_orders, completed_orders=completed_orders,
        pending_orders=pending_orders, total_earned=total_earned,
        month_earned=month_earned, monthly=monthly, fav_count=fav_count,
        seller_level=sl, top_services=top_services[:5])


# ════════════════════════════════════════════════════════════════════════════
# SERVICE VIEW TRACKER (call from service_detail route)
# ════════════════════════════════════════════════════════════════════════════
@features_bp.route('/api/track-view/<int:sid>', methods=['POST'])
def track_view(sid):
    ip   = request.remote_addr or ''
    ih   = hashlib.md5(ip.encode()).hexdigest()
    uid  = current_user.id if current_user.is_authenticated else None
    # Deduplicate: same user/ip within 1 hour
    since = datetime.utcnow() - timedelta(hours=1)
    exists = ServiceView.query.filter(
        ServiceView.service_id == sid,
        ServiceView.viewed_at  >= since,
        ServiceView.ip_hash    == ih
    ).first()
    if not exists:
        sv = ServiceView(service_id=sid, viewer_id=uid, ip_hash=ih)
        db.session.add(sv)
        try: db.session.commit()
        except: db.session.rollback()
    return jsonify(ok=True)


# ════════════════════════════════════════════════════════════════════════════
# SELLER LEVEL API
# ════════════════════════════════════════════════════════════════════════════
@features_bp.route('/api/seller-level/<int:uid>')
def get_seller_level(uid):
    sl = SellerLevel.query.filter_by(user_id=uid).first()
    if not sl:
        return jsonify(level='new_seller', label='New Seller', color='#64748b')
    info = SellerLevel.LEVEL_THRESHOLDS.get(sl.level, {})
    return jsonify(level=sl.level, label=info.get('label',sl.level), color=info.get('color','#64748b'),
                   completed=sl.completed_orders, earned=float(sl.total_earned or 0),
                   rating=sl.avg_rating)

@features_bp.route('/offer/<int:oid>/order', methods=['GET', 'POST'])
@login_required
def order_from_offer(oid):
    from models_extra import CustomOffer
    offer = CustomOffer.query.get_or_404(oid)
    # PHASE 2 FIX: Explicit IDOR protection
    if offer.buyer_id != current_user.id and current_user.role != 'admin':
        abort(403)
    if offer.status != 'accepted':
        flash('Offer must be accepted before placing an order.', 'warning')
        return redirect(url_for('features.offer_detail', oid=oid))

    # Use linked service_id if available, otherwise None (custom offer)
    service_id = offer.service_id

    if request.method == 'POST':
        from models import Order, db
        order = Order(
            service_id=service_id,
            buyer_id=offer.buyer_id,
            seller_id=offer.seller_id,
            amount=offer.price,
            currency='KES',
            status='pending'
        )
        db.session.add(order)
        db.session.commit()
        flash('Order placed! Proceed to payment.', 'success')
        return redirect(url_for('features.pay_offer', oid=oid, order_id=order.id))

    return render_template('order_from_offer.html', offer=offer)




@features_bp.route('/service/<int:sid>/order', methods=['GET', 'POST'])
@login_required
def create_order(sid):
    from models import Service, Order, Notification
    from models_extra import ServicePackage
    from datetime import datetime, timedelta
    service = Service.query.get_or_404(sid)
    pkg_id = request.args.get('pkg', type=int)
    pkg = ServicePackage.query.get(pkg_id) if pkg_id else None

    if current_user.id == service.seller_id:
        flash('You cannot order your own service.', 'warning')
        return redirect(url_for('features.view_packages', sid=sid))

    if request.method == 'POST':
        pkg_id = request.form.get('pkg_id', type=int)
        pkg = ServicePackage.query.get(pkg_id) if pkg_id else None
        amount = pkg.price if pkg else service.price
        delivery_days = (pkg.delivery_days if pkg else None) or getattr(service, 'delivery_days', None)
        deadline = datetime.utcnow() + timedelta(days=delivery_days) if delivery_days else None

        order = Order(
            service_id=service.id,
            buyer_id=current_user.id,
            seller_id=service.seller_id,
            amount=amount,
            currency='KES',
            status='pending',
            title=f'{pkg.name if pkg else service.title}',
            description=service.description,
            buyer_instructions=request.form.get('instructions', ''),
            deadline=deadline,
            package_id=pkg_id
        )
        db.session.add(order)
        db.session.flush()

        notif = Notification(
            user_id=service.seller_id,
            body=f'New order #{order.id} placed for your service "{service.title}".',
            type='order',
            title="New Order",
            link=url_for('order_detail', order_id=order.id)
        )
        db.session.add(notif)
        db.session.commit()
        flash('Order placed! Please complete payment.', 'success')
        return redirect(url_for('pay_order', order_id=order.id))

    return render_template('create_order.html', service=service, pkg=pkg)

@features_bp.route('/offer/<int:oid>/pay/<int:order_id>', methods=['GET'])
@login_required
def pay_offer(oid, order_id):
    from models_extra import CustomOffer
    from models import Order
    offer = CustomOffer.query.get_or_404(oid)
    order = Order.query.get_or_404(order_id)
    # PHASE 2 FIX: Explicit IDOR protection
    if offer.buyer_id != current_user.id and current_user.role != 'admin':
        abort(403)
    return render_template('payment_offer.html', offer=offer, order=order)
