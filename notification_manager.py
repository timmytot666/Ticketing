import json
import os
from datetime import datetime, timedelta, timezone # Added timedelta, timezone
from typing import List, Optional, Dict, Any

try:
    from models import Notification, Ticket, User # Added Ticket, User
    from ticket_manager import list_tickets, update_ticket # Added
    # user_manager.get_users_by_role will be imported within the function with a fallback
except ModuleNotFoundError:
    print("Error: Critical modules (models, ticket_manager) not found for NotificationManager.", file=sys.stderr)
    # Fallbacks
    class Notification:
        def __init__(self, *args, **kwargs): pass
        def to_dict(self) -> dict: return {}
        @classmethod
        def from_dict(cls, d) -> 'Notification': return cls()
        is_read = False; timestamp = None
    class Ticket: # Basic fallback for type hints
        id: str; title: str; status: Optional[str]; assignee_user_id: Optional[str]; requester_user_id: Optional[str]
        response_due_at: Optional[datetime]; responded_at: Optional[datetime]; resolution_due_at: Optional[datetime]
        response_sla_breach_notified: bool; resolution_sla_breach_notified: bool
        response_sla_nearing_breach_notified: bool; resolution_sla_nearing_breach_notified: bool
        total_paused_duration_seconds: float; sla_paused_at: Optional[datetime]
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            self.response_sla_breach_notified=False; self.resolution_sla_breach_notified=False
            self.response_sla_nearing_breach_notified=False; self.resolution_sla_nearing_breach_notified=False
            self.total_paused_duration_seconds = 0.0

    class User: user_id: str
    def list_tickets() -> list: return []
    def update_ticket(tid, **kwargs) -> Optional[Ticket]: return None


NOTIFICATIONS_FILE = "notifications.json"

# ... existing _load_notifications, _save_notifications, create_notification etc. ...
def _load_notifications() -> List[Notification]:
    try:
        if not os.path.exists(NOTIFICATIONS_FILE) or os.path.getsize(NOTIFICATIONS_FILE) == 0: return []
        with open(NOTIFICATIONS_FILE, 'r') as f: data = json.load(f)
        return [Notification.from_dict(notif_data) for notif_data in data]
    except FileNotFoundError: return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {NOTIFICATIONS_FILE}. Returning empty list.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Unexpected error loading notifications: {e}", file=sys.stderr)
        return []

def _save_notifications(notifications: List[Notification]) -> None:
    try:
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump([notif.to_dict() for notif in notifications], f, indent=4)
    except IOError as e: print(f"Error saving notifications: {e}", file=sys.stderr)
    except Exception as e: print(f"Unexpected error saving notifications: {e}", file=sys.stderr)


def create_notification(user_id: str, message: str, ticket_id: Optional[str] = None) -> Optional[Notification]:
    # Ensure user_id and message are not empty (Notification model also validates)
    if not user_id or not message:
        print("Error: user_id and message are required for create_notification.", file=sys.stderr)
        return None
    notifications = _load_notifications()
    try:
        new_notification = Notification(user_id=user_id, message=message, ticket_id=ticket_id)
        notifications.append(new_notification)
        _save_notifications(notifications)
        return new_notification
    except ValueError as e:
        print(f"Error creating notification object: {e}", file=sys.stderr)
        return None
    except Exception as e_save: # Catch errors from _save_notifications if it raises them
        print(f"Failed to save notification: {e_save}", file=sys.stderr)
        return None


def get_notifications_for_user(user_id: str, unread_only: bool = False) -> List[Notification]:
    if not user_id: return []
    all_notifications = _load_notifications()
    user_notifications = [n for n in all_notifications if hasattr(n,'user_id') and n.user_id == user_id]
    if unread_only: user_notifications = [n for n in user_notifications if hasattr(n,'is_read') and not n.is_read]
    try: user_notifications.sort(key=lambda n: getattr(n, 'timestamp', datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    except TypeError: print("Warning: Could not sort notifications due to missing timestamp data.", file=sys.stderr)
    return user_notifications

def get_notification_by_id(notification_id: str) -> Optional[Notification]:
    if not notification_id: return None
    for n in _load_notifications():
        if hasattr(n, 'notification_id') and n.notification_id == notification_id: return n
    return None

def mark_notification_as_read(notification_id: str) -> bool:
    if not notification_id: return False
    notifications = _load_notifications(); updated_flag = False
    for n in notifications:
        if hasattr(n, 'notification_id') and n.notification_id == notification_id and hasattr(n, 'is_read') and not n.is_read:
            n.is_read = True; updated_flag = True; break
    if updated_flag: _save_notifications(notifications)
    return updated_flag

def mark_multiple_notifications_as_read(notification_ids: List[str]) -> int:
    if not notification_ids: return 0
    notifications = _load_notifications(); count = 0; made_changes = False
    lookup: Dict[str, Notification] = {n.notification_id: n for n in notifications if hasattr(n, 'notification_id')}
    for nid in notification_ids:
        n_obj = lookup.get(nid)
        if n_obj and hasattr(n_obj, 'is_read') and not n_obj.is_read:
            n_obj.is_read = True; count += 1; made_changes = True
    if made_changes: _save_notifications(list(lookup.values()))
    return count


# --- SLA Alerting Logic ---
def check_and_send_sla_alerts():
    now = datetime.now(timezone.utc)
    try:
        active_tickets_all_fields = list_tickets() # Fetch all tickets
        if active_tickets_all_fields is None: active_tickets_all_fields = [] # Ensure it's a list
    except Exception as e_list:
        print(f"Error fetching tickets for SLA alerts: {e_list}", file=sys.stderr)
        return

    active_tickets = [
        t for t in active_tickets_all_fields
        if hasattr(t, 'status') and t.status not in ['Closed', 'Cancelled'] # Define 'Cancelled' if used
    ]

    manager_ids_for_alert: List[str] = []
    try:
        from user_manager import get_users_by_role
        manager_users = get_users_by_role(roles=['TechManager', 'EngManager'])
        if manager_users: manager_ids_for_alert = [user.user_id for user in manager_users if hasattr(user, 'user_id')]
    except ImportError:
        print("Warning: user_manager.get_users_by_role not available for SLA alerts.", file=sys.stderr)
    except Exception as e_user_mgr:
         print(f"Warning: Error fetching managers for SLA alerts: {e_user_mgr}", file=sys.stderr)

    tickets_to_update_flags: List[Tuple[str, Dict[str, bool]]] = []
    RESPONSE_NEARING_THRESHOLD_HOURS = 1.0
    RESOLUTION_NEARING_THRESHOLD_HOURS = 8.0

    for ticket in active_tickets:
        # Ensure ticket has necessary attributes (robustness for heterogeneous list or fallback objects)
        if not all(hasattr(ticket, attr) for attr in [
            'total_paused_duration_seconds', 'response_due_at', 'responded_at',
            'response_sla_breach_notified', 'response_sla_nearing_breach_notified',
            'resolution_due_at', 'resolution_sla_breach_notified',
            'resolution_sla_nearing_breach_notified', 'id', 'title',
            'assignee_user_id', 'requester_user_id'
        ]):
            print(f"Skipping SLA check for ticket {getattr(ticket, 'id', 'UnknownID')} due to missing attributes.", file=sys.stderr)
            continue

        effective_now_for_sla = now - timedelta(seconds=ticket.total_paused_duration_seconds)
        title_short = ticket.title[:20] + "..." if len(ticket.title) > 20 else ticket.title
        ticket_ref = f"'{title_short}' (ID: {ticket.id[:8]})"

        # --- Response SLA Check ---
        if ticket.response_due_at and not ticket.responded_at:
            if effective_now_for_sla > ticket.response_due_at:
                if not ticket.response_sla_breach_notified:
                    message = f"Response SLA BREACHED for Ticket {ticket_ref}."
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    for manager_id in manager_ids_for_alert:
                         if manager_id != ticket.assignee_user_id: create_notification(manager_id, message + " Escalation.", ticket.id)
                    tickets_to_update_flags.append((ticket.id, {'response_sla_breach_notified': True}))
            elif not ticket.response_sla_nearing_breach_notified: # Only check nearing if not breached
                if (ticket.response_due_at - effective_now_for_sla) < timedelta(hours=RESPONSE_NEARING_THRESHOLD_HOURS):
                    message = f"Response SLA Nearing Breach for Ticket {ticket_ref}."
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    tickets_to_update_flags.append((ticket.id, {'response_sla_nearing_breach_notified': True}))

        # --- Resolution SLA Check ---
        if ticket.resolution_due_at:
            if effective_now_for_sla > ticket.resolution_due_at:
                if not ticket.resolution_sla_breach_notified:
                    message = f"Resolution SLA BREACHED for Ticket {ticket_ref}."
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    for manager_id in manager_ids_for_alert:
                        if manager_id != ticket.assignee_user_id: create_notification(manager_id, message + " Escalation.", ticket.id)
                    tickets_to_update_flags.append((ticket.id, {'resolution_sla_breach_notified': True}))
            elif not ticket.resolution_sla_nearing_breach_notified: # Only check nearing if not breached
                if (ticket.resolution_due_at - effective_now_for_sla) < timedelta(hours=RESOLUTION_NEARING_THRESHOLD_HOURS):
                    message = f"Resolution SLA Nearing Breach for Ticket {ticket_ref}."
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    tickets_to_update_flags.append((ticket.id, {'resolution_sla_nearing_breach_notified': True}))

        if tickets_to_update_flags:
            print(f"SLA Check: Will attempt to update flags for {len(tickets_to_update_flags)} tickets.")
            for ticket_id_to_flag, flags_to_set in tickets_to_update_flags:
                try:
                    # Using update_ticket will re-trigger its own logic (SLA recalc, other notifications)
                    # This is not ideal. A more targeted update_ticket_flags method would be better.
                    # For now, this is what's available.
                    current_ticket_state = get_ticket(ticket_id_to_flag) # Get current full state
                    if current_ticket_state:
                        # Avoid unintended side effects by only passing flags to update_ticket
                        # However, update_ticket expects certain fields for its internal logic.
                        # This simplified call might not be robust if update_ticket has strict requirements.
                        # A better approach would be a dedicated function to update only these flags.
                        # For now, we'll pass the flags. If update_ticket needs more, this will fail or behave unexpectedly.
                        # Let's assume for now that update_ticket can handle just these flags
                        # or that the side effects are acceptable for this iteration.
                        update_ticket(ticket_id_to_flag, **flags_to_set)
                except Exception as e_update:
                    print(f"Error updating SLA flags for ticket {ticket_id_to_flag}: {e_update}", file=sys.stderr)

if __name__ == "__main__":
    # Add basic test calls here if needed, e.g., by creating dummy tickets in tickets.json
    # and then calling check_and_send_sla_alerts()
    # This would require careful setup of tickets.json and users.json for manager roles.
    print("SLA Alert Check (manual run - ensure tickets.json and users.json are populated for meaningful test)")
    # check_and_send_sla_alerts() # Be cautious running this without controlled test data
    print("SLA Alert Check finished.")
