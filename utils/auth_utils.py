"""
Authentication and authorization utilities for Freelance Marketplace
"""

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def require_role(role):
    """Decorator to require specific user role"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash("Access denied.", "danger")
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def chat_room_name(a_id, b_id):
    """Generate chat room name from two user IDs"""
    a, b = sorted([int(a_id), int(b_id)])
    return f"chat_{a}_{b}"


def unread_count_for_user(user_id):
    """Get count of unread messages for a user"""
    from models import Message
    return Message.query.filter_by(receiver_id=user_id, is_read=False).count()