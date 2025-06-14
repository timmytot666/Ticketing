import json
import os
from datetime import datetime # Not strictly needed here if only used in models.py
from typing import List, Optional, Dict, Any

try:
    from models import Notification
except ModuleNotFoundError:
    print("Error: models.py not found. Ensure it's in the same directory or PYTHONPATH.")
    # Fallback Notification class for type hinting if models cannot be imported.
    class Notification:
        def __init__(self, *args, **kwargs): pass
        def to_dict(self) -> dict: return {}
        @classmethod
        def from_dict(cls, d) -> 'Notification': return cls()
        is_read = False
        timestamp = None


NOTIFICATIONS_FILE = "notifications.json"

def _load_notifications() -> List[Notification]:
    """
    Reads notifications from NOTIFICATIONS_FILE.
    If the file doesn't exist or is empty, returns an empty list.
    Otherwise, parses the JSON content and returns a list of Notification objects.
    Handles potential FileNotFoundError and json.JSONDecodeError.
    """
    try:
        if not os.path.exists(NOTIFICATIONS_FILE) or os.path.getsize(NOTIFICATIONS_FILE) == 0:
            return []
        with open(NOTIFICATIONS_FILE, 'r') as f:
            data = json.load(f)
            return [Notification.from_dict(notif_data) for notif_data in data]
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {NOTIFICATIONS_FILE}. Returning empty list.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading notifications: {e}")
        return []

def _save_notifications(notifications: List[Notification]) -> None:
    """
    Takes a list of Notification objects.
    Converts each Notification object to its dictionary representation.
    Writes the list of dictionaries to NOTIFICATIONS_FILE as JSON.
    """
    try:
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump([notif.to_dict() for notif in notifications], f, indent=4)
    except IOError as e:
        print(f"Error saving notifications to {NOTIFICATIONS_FILE}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving notifications: {e}")

def create_notification(user_id: str, message: str, ticket_id: Optional[str] = None) -> Notification:
    """
    Creates a new Notification instance and saves it.
    """
    notifications = _load_notifications()
    try:
        # Notification class __init__ handles validation of user_id and message
        new_notification = Notification(user_id=user_id, message=message, ticket_id=ticket_id)
    except ValueError as e: # Catch validation errors from Notification class
        raise ValueError(f"Error creating notification: {e}")

    notifications.append(new_notification)
    _save_notifications(notifications)
    return new_notification

def get_notifications_for_user(user_id: str, unread_only: bool = False) -> List[Notification]:
    """
    Retrieves notifications for a given user_id.
    Optionally filters for unread notifications only.
    Sorts notifications by timestamp in descending order (most recent first).
    """
    if not user_id:
        return []

    all_notifications = _load_notifications()
    user_notifications = [n for n in all_notifications if n.user_id == user_id]

    if unread_only:
        user_notifications = [n for n in user_notifications if not n.is_read]

    # Sort by timestamp, most recent first. Relies on Notification.timestamp being a datetime object.
    # If Notification.timestamp is None (e.g. due to fallback class), this sort might fail.
    try:
        user_notifications.sort(key=lambda n: n.timestamp, reverse=True)
    except TypeError: # Handles cases where timestamp might be None if models not loaded properly
        print("Warning: Could not sort notifications due to missing timestamp data.")


    return user_notifications

def get_notification_by_id(notification_id: str) -> Optional[Notification]:
    """
    Retrieves a notification by its ID.
    """
    if not notification_id:
        return None
    notifications = _load_notifications()
    for notification in notifications:
        if notification.notification_id == notification_id:
            return notification
    return None

def mark_notification_as_read(notification_id: str) -> bool:
    """
    Marks a single notification as read.
    Returns True if updated, False otherwise (not found or already read).
    """
    if not notification_id:
        return False

    notifications = _load_notifications()
    notification_found = False
    updated = False

    for notification in notifications:
        if notification.notification_id == notification_id:
            notification_found = True
            if not notification.is_read:
                notification.is_read = True
                updated = True
            break

    if updated:
        _save_notifications(notifications)

    return updated

def mark_multiple_notifications_as_read(notification_ids: List[str]) -> int:
    """
    Marks multiple notifications as read.
    Returns the count of notifications that were actually marked as read.
    """
    if not notification_ids:
        return 0

    notifications = _load_notifications()
    marked_count = 0
    made_changes = False

    # Create a dictionary for quick lookup
    notifications_dict: Dict[str, Notification] = {n.notification_id: n for n in notifications}

    for notif_id in notification_ids:
        notification = notifications_dict.get(notif_id)
        if notification and not notification.is_read:
            notification.is_read = True
            marked_count += 1
            made_changes = True

    if made_changes:
        # Convert dict values back to list for saving
        _save_notifications(list(notifications_dict.values()))

    return marked_count
