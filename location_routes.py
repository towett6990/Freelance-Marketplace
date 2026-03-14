# FILE: location_routes.py
# =======================
# CREATE THIS FILE IN YOUR PROJECT ROOT
# Then import it in app.py with: from location_routes import location_bp

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Location, Conversation
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

location_bp = Blueprint('location', __name__, url_prefix='/api/location')


# ============================================================
# HELPER FUNCTION - Calculate distance between coordinates
# ============================================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in kilometers using Haversine formula"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    R = 6371  # Earth radius in kilometers
    return R * c


# ============================================================
# ENDPOINT 1: Share Location
# ============================================================
@location_bp.route('/share', methods=['POST'])
@login_required
def share_location():
    """Share user's location with others (optionally in a conversation)"""
    try:
        print(f"DEBUG: share_location() called by user {current_user.id}")
        
        data = request.get_json()
        print(f"DEBUG: Received data: {data}")
        
        # Validate
        if not data.get('latitude') or not data.get('longitude'):
            return jsonify({'error': 'Latitude and longitude required'}), 400
        
        try:
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
            print(f"DEBUG: Coordinates validated: {latitude}, {longitude}")
        except ValueError:
            return jsonify({'error': 'Invalid coordinates'}), 400
        
        # Set expiration
        expires_in = data.get('expires_in_minutes', 60)
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in)
        
        # Get shared_with list
        shared_with = data.get('share_with', [])
        
        # If conversation_id is provided, add participants to shared_with
        conversation_id = data.get('conversation_id')
        if conversation_id:
            try:
                convo = Conversation.query.get(int(conversation_id))
                if convo:
                    # Add the other user to shared_with
                    if convo.user1_id == current_user.id:
                        if convo.user2_id not in shared_with:
                            shared_with.append(convo.user2_id)
                    elif convo.user2_id == current_user.id:
                        if convo.user1_id not in shared_with:
                            shared_with.append(convo.user1_id)
            except Exception as conv_err:
                print(f"DEBUG: Could not fetch conversation: {conv_err}")
        
        # Create location
        print(f"DEBUG: Creating Location object")
        location = Location(
            user_id=current_user.id,
            latitude=latitude,
            longitude=longitude,
            address=data.get('address', ''),
            city=data.get('city', ''),
            country=data.get('country', ''),
            accuracy=data.get('accuracy'),
            expires_at=expires_at,
            shared_with=shared_with,
            is_active=True
        )
        
        print(f"DEBUG: Location object created: {location}")
        
        db.session.add(location)
        db.session.commit()
        
        print(f"DEBUG: Location saved successfully with ID {location.id}")
        
        return jsonify({
            'success': True,
            'message': 'Location shared successfully',
            'location': location.to_dict()
        }), 201
    
    except Exception as e:
        print(f"ERROR in share_location: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================
# ENDPOINT 2: Stop Sharing Location
# ============================================================
@location_bp.route('/stop', methods=['POST'])
@login_required
def stop_sharing_location():
    """Stop sharing location"""
    try:
        data = request.get_json()
        location_id = data.get('location_id')
        
        if not location_id:
            return jsonify({'error': 'Location ID required'}), 400
        
        location = Location.query.filter_by(
            id=location_id,
            user_id=current_user.id
        ).first()
        
        if not location:
            return jsonify({'error': 'Location not found'}), 404
        
        location.is_active = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Location sharing stopped'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================
# ENDPOINT 3: Get User's Location
# ============================================================
@location_bp.route('/get/<int:user_id>', methods=['GET'])
@login_required
def get_user_location(user_id):
    """Get a seller's current location"""
    try:
        location = Location.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(Location.timestamp.desc()).first()
        
        if not location:
            return jsonify({'error': 'Location not available'}), 404
        
        # Check expiration
        if location.is_expired():
            location.is_active = False
            db.session.commit()
            return jsonify({'error': 'Location sharing expired'}), 410
        
        # Check authorization
        if location.shared_with and current_user.id not in location.shared_with:
            if user_id != current_user.id:
                return jsonify({'error': 'Not authorized to view this location'}), 403
        
        return jsonify({
            'success': True,
            'location': location.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# ENDPOINT 4: Update Location (Real-time Tracking)
# ============================================================
@location_bp.route('/update', methods=['POST'])
@login_required
def update_location():
    """Update current location (for real-time tracking)"""
    try:
        data = request.get_json()
        
        if not data.get('latitude') or not data.get('longitude'):
            return jsonify({'error': 'Latitude and longitude required'}), 400
        
        try:
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
        except ValueError:
            return jsonify({'error': 'Invalid coordinates'}), 400
        
        # Get or create location
        location = Location.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).first()
        
        if not location:
            # Create new
            location = Location(
                user_id=current_user.id,
                latitude=latitude,
                longitude=longitude,
                address=data.get('address', ''),
                city=data.get('city', ''),
                country=data.get('country', ''),
                accuracy=data.get('accuracy'),
                expires_at=datetime.utcnow() + timedelta(minutes=60),
                is_active=True
            )
            db.session.add(location)
        else:
            # Update existing
            location.latitude = latitude
            location.longitude = longitude
            location.address = data.get('address', location.address)
            location.city = data.get('city', location.city)
            location.country = data.get('country', location.country)
            location.accuracy = data.get('accuracy', location.accuracy)
            location.timestamp = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Location updated',
            'location': location.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================
# ENDPOINT 5: Get Active Locations
# ============================================================
@location_bp.route('/active', methods=['GET'])
@login_required
def get_active_locations():
    """Get all active location sharings for current user"""
    try:
        print(f"DEBUG: get_active_locations() called by user {current_user.id}")
        
        locations = Location.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        print(f"DEBUG: Found {len(locations)} active locations")
        
        # Mark expired as inactive
        for loc in locations:
            if loc.is_expired():
                loc.is_active = False
        
        db.session.commit()
        
        active = [loc.to_dict() for loc in locations if loc.is_active]
        
        print(f"DEBUG: Returning {len(active)} non-expired locations")
        
        return jsonify({
            'success': True,
            'locations': active,
            'count': len(active)
        }), 200
    
    except Exception as e:
        print(f"ERROR in get_active_locations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================
# ENDPOINT 6: Find Nearby Sellers
# ============================================================
@location_bp.route('/nearby', methods=['POST'])
@login_required
def find_nearby_sellers():
    """Find sellers nearby within specified radius"""
    try:
        data = request.get_json()
        
        user_lat = float(data['latitude'])
        user_lon = float(data['longitude'])
        radius_km = float(data.get('radius_km', 5))
        
        # Get all active locations
        locations = Location.query.filter_by(is_active=True).all()
        
        nearby = []
        for loc in locations:
            # Skip if expired
            if loc.is_expired():
                loc.is_active = False
                continue
            
            # Skip own location
            if loc.user_id == current_user.id:
                continue
            
            # Calculate distance
            distance_km = haversine_distance(user_lat, user_lon, loc.latitude, loc.longitude)
            
            if distance_km <= radius_km:
                seller = User.query.get(loc.user_id)
                if seller:
                    nearby.append({
                        'location': loc.to_dict(),
                        'seller': {
                            'id': seller.id,
                            'username': seller.username,
                            'email': seller.email
                        },
                        'distance_km': round(distance_km, 2)
                    })
        
        db.session.commit()
        
        # Sort by distance
        nearby.sort(key=lambda x: x['distance_km'])
        
        return jsonify({
            'success': True,
            'nearby_sellers': nearby,
            'count': len(nearby)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# ENDPOINT 7: Calculate Distance Between Two Points
# ============================================================
@location_bp.route('/calculate-distance', methods=['POST'])
@login_required
def calculate_distance():
    """Calculate distance between two GPS coordinates"""
    try:
        data = request.get_json()
        
        lat1 = float(data['lat1'])
        lon1 = float(data['lon1'])
        lat2 = float(data['lat2'])
        lon2 = float(data['lon2'])
        
        distance_km = haversine_distance(lat1, lon1, lat2, lon2)
        distance_miles = distance_km * 0.621371
        
        return jsonify({
            'success': True,
            'distance_km': round(distance_km, 2),
            'distance_miles': round(distance_miles, 2)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500