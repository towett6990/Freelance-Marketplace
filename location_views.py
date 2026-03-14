# FILE: location_views.py
# =======================
# CREATE THIS FILE IN YOUR PROJECT ROOT
# Then import it in app.py with: from location_views import location_views_bp

from flask import Blueprint, render_template
from flask_login import login_required

location_views_bp = Blueprint('location_views', __name__)


# ============================================================
# Display Location Sharing Page
# ============================================================
@location_views_bp.route('/share-location')
@login_required
def share_location():
    """Display location sharing interface"""
    return render_template('location_share.html')


# ============================================================
# Optional: Display Admin Location Dashboard
# ============================================================
@location_views_bp.route('/admin/locations')
@login_required
def admin_locations():
    """Admin view of all active locations"""
    from flask_login import current_user
    
    # Check if user is admin (adjust based on your permission system)
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return 'Unauthorized', 403
    
    from models import Location
    locations = Location.query.filter_by(is_active=True).all()
    
    return render_template('admin_locations.html', locations=locations)