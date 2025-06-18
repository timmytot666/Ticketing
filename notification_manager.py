import sqlite3
import sys # For stderr
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

try:
    from models import Notification, Ticket, User # Ticket, User are for type hints if used by imported functions
except ModuleNotFoundError:
    print("Critical Error: models.py not found. Notification manager may not function correctly.", file=sys.stderr)
    class Notification: # Basic fallback
        notification_id: str; user_id: str; ticket_id: Optional[str]; message: str; timestamp: datetime; is_read: bool
        def __init__(self, user_id: str, message: str, ticket_id: Optional[str] = None, **kwargs):
            self.notification_id = kwargs.get("notification_id", "fb_notif_id_" + uuid.uuid4().hex)
            self.user_id = user_id; self.message = message; self.ticket_id = ticket_id
            self.timestamp = kwargs.get("timestamp", datetime.now(timezone.utc))
            self.is_read = kwargs.get("is_read", False)
        def to_dict(self) -> dict: return {k:v for k,v in self.__dict__.items() if not k.startswith('_')}
        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> 'Notification': return cls(**data)
    class Ticket: pass # Define fallbacks for other models if needed by type hints
    class User: pass


try:
    from database_setup import get_db_connection
except ModuleNotFoundError:
    print("Critical Error: database_setup.py not found. Notification manager cannot function.", file=sys.stderr)
    def get_db_connection(): raise ConnectionError("Database setup module not found.")

# ticket_manager and user_manager will be imported locally within functions
# where needed to avoid circular dependencies at module load time.

def _iso_to_datetime(iso_str: Optional[str]) -> Optional[datetime]:
    if not iso_str: return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def _row_to_notification(row: sqlite3.Row) -> Optional[Notification]:
    """Converts a sqlite3.Row to a Notification object."""
    if not row:
        return None
    return Notification(
        notification_id=row["notification_id"],
        user_id=row["user_id"],
        ticket_id=row["ticket_id"],
        message=row["message"],
        timestamp=_iso_to_datetime(row["timestamp"]),
        is_read=bool(row["is_read"])
    )

def create_notification(user_id: str, message: str, ticket_id: Optional[str] = None) -> Optional[Notification]:
    if not user_id or not message: # Basic validation
        print("Error: user_id and message are required for create_notification.", file=sys.stderr)
        return None

    try: # Validation also happens in Notification model constructor
        new_notification = Notification(user_id=user_id, message=message, ticket_id=ticket_id)
    except ValueError as ve:
        print(f"Error creating Notification object: {ve}", file=sys.stderr)
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO notifications (
                notification_id, user_id, ticket_id,
                message, timestamp, is_read
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            new_notification.notification_id, new_notification.user_id,
            new_notification.ticket_id, new_notification.message,
            new_notification.timestamp.isoformat(), new_notification.is_read
        ))
        conn.commit()
        return new_notification
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error creating notification: {e}", file=sys.stderr)
        return None
    finally:
        conn.close()

def get_notifications_for_user(user_id: str, unread_only: bool = False) -> List[Notification]:
    if not user_id: return []
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM notifications WHERE user_id = ?"
    params: List[Any] = [user_id]

    if unread_only:
        query += " AND is_read = ?"
        params.append(False) # SQLite stores booleans as 0 (False) or 1 (True)

    query += " ORDER BY timestamp DESC"

    try:
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        notifications = [_row_to_notification(row) for row in rows if row]
        return [n for n in notifications if n is not None]
    except sqlite3.Error as e:
        print(f"Database error getting notifications for user {user_id}: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()

def get_notification_by_id(notification_id: str) -> Optional[Notification]:
    if not notification_id: return None
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM notifications WHERE notification_id = ?", (notification_id,))
        row = cursor.fetchone()
        return _row_to_notification(row)
    except sqlite3.Error as e:
        print(f"Database error getting notification by ID {notification_id}: {e}", file=sys.stderr)
        return None
    finally:
        conn.close()

def mark_notification_as_read(notification_id: str) -> bool:
    if not notification_id: return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE notifications SET is_read = ? WHERE notification_id = ? AND is_read = ?",
                       (True, notification_id, False))
        conn.commit()
        return cursor.rowcount > 0 # True if a row was updated
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error marking notification {notification_id} as read: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

def mark_multiple_notifications_as_read(notification_ids: List[str]) -> int:
    if not notification_ids: return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    updated_count = 0
    try:
        # SQLite doesn't directly support list of IDs in a single UPDATE statement easily without string formatting.
        # It's safer to do it one by one or use a temporary table for larger lists.
        # For simplicity and safety with typical list sizes for this app, update one by one.
        for nid in notification_ids:
            cursor.execute("UPDATE notifications SET is_read = ? WHERE notification_id = ? AND is_read = ?",
                           (True, nid, False))
            if cursor.rowcount > 0:
                updated_count += 1
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error marking multiple notifications as read: {e}", file=sys.stderr)
        return 0 # Or return count before error
    finally:
        conn.close()
    return updated_count


# --- SLA Alerting Logic ---
def check_and_send_sla_alerts():
    now = datetime.now(timezone.utc)

    # Dynamically import managers to avoid circular dependencies at load time
    try:
        from ticket_manager import list_tickets, update_ticket
        from user_manager import get_users_by_role
    except ImportError as e:
        print(f"Critical Error: Could not import ticket_manager or user_manager for SLA alerts: {e}", file=sys.stderr)
        return

    try:
        # list_tickets and get_users_by_role are now DB backed via their respective managers
        active_tickets_all_fields = list_tickets(filters={'status_not_in': ['Closed', 'Cancelled']}) # Assuming list_tickets can take such a filter
        # If list_tickets doesn't support 'status_not_in', filter in Python:
        # active_tickets_all_fields = [t for t in list_tickets() if t.status not in ['Closed', 'Cancelled']]

    except Exception as e_list:
        print(f"Error fetching tickets for SLA alerts: {e_list}", file=sys.stderr)
        return

    if active_tickets_all_fields is None: active_tickets_all_fields = []

    # Filter tickets - this might be redundant if list_tickets handles it
    active_tickets = [
        t for t in active_tickets_all_fields
        if hasattr(t, 'status') and t.status not in ['Closed', 'Cancelled']
    ]


    manager_ids_for_alert: List[str] = []
    try:
        manager_users = get_users_by_role(roles=['TechManager', 'EngManager'])
        if manager_users:
            manager_ids_for_alert = [user.user_id for user in manager_users if hasattr(user, 'user_id')]
    except Exception as e_user_mgr:
         print(f"Warning: Error fetching managers for SLA alerts: {e_user_mgr}", file=sys.stderr)

    # Use a list to collect ticket IDs and the flags that need to be updated.
    # This avoids calling update_ticket multiple times for the same ticket within this loop.
    ticket_flags_to_batch_update: Dict[str, Dict[str, bool]] = {}

    RESPONSE_NEARING_THRESHOLD_HOURS = 1.0
    RESOLUTION_NEARING_THRESHOLD_HOURS = 8.0

    for ticket in active_tickets:
        # Ensure ticket has necessary attributes
        required_attrs = [
            'total_paused_duration_seconds', 'response_due_at', 'responded_at',
            'response_sla_breach_notified', 'response_sla_nearing_breach_notified',
            'resolution_due_at', 'resolution_sla_breach_notified',
            'resolution_sla_nearing_breach_notified', 'id', 'title',
            'assignee_user_id', 'requester_user_id', 'created_at' # created_at is needed for effective_now
        ]
        if not all(hasattr(ticket, attr) for attr in required_attrs):
            print(f"Skipping SLA check for ticket {getattr(ticket, 'id', 'UnknownID')} due to missing attributes.", file=sys.stderr)
            continue

        # SLA calculations should consider paused time
        # effective_now_for_sla = now - timedelta(seconds=ticket.total_paused_duration_seconds)
        # It's better if the due dates themselves are already adjusted or calculated against a fixed point (created_at)
        # and the `now` is compared directly, assuming due dates are absolute UTC times.
        # The current structure seems to imply due_dates are fixed, and `now` is the moving part.
        # Let's assume total_paused_duration_seconds means the SLA clock was paused for that duration.
        # So, if a task is due at T, and was paused for P, it's effectively due at T+P from a calendar perspective,
        # OR, we compare T with (now - P). The latter is used in the original code.

        # If sla_paused_at is set, the SLA is currently paused.
        if ticket.sla_paused_at is not None:
            continue # Skip SLA checks for currently paused tickets.

        effective_now_for_sla = now - timedelta(seconds=ticket.total_paused_duration_seconds)

        title_short = ticket.title[:20] + "..." if len(ticket.title) > 20 else ticket.title
        ticket_ref = f"'{title_short}' (ID: {ticket.id[:8]})"

        current_flags_for_ticket = ticket_flags_to_batch_update.get(ticket.id, {})

        # --- Response SLA Check ---
        if ticket.response_due_at and not ticket.responded_at:
            if effective_now_for_sla > ticket.response_due_at:
                if not ticket.response_sla_breach_notified and not current_flags_for_ticket.get('response_sla_breach_notified'):
                    message = f"Response SLA BREACHED for Ticket {ticket_ref}."
                    # create_notification now writes to DB
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    for manager_id in manager_ids_for_alert:
                         if manager_id != ticket.assignee_user_id: create_notification(manager_id, message + " Escalation.", ticket.id)
                    current_flags_for_ticket['response_sla_breach_notified'] = True
            elif not ticket.response_sla_nearing_breach_notified and not current_flags_for_ticket.get('response_sla_nearing_breach_notified'):
                if (ticket.response_due_at - effective_now_for_sla) < timedelta(hours=RESPONSE_NEARING_THRESHOLD_HOURS):
                    message = f"Response SLA Nearing Breach for Ticket {ticket_ref}."
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    current_flags_for_ticket['response_sla_nearing_breach_notified'] = True

        # --- Resolution SLA Check ---
        if ticket.resolution_due_at: # Assuming status is not 'Closed' or 'Resolved' yet
            if effective_now_for_sla > ticket.resolution_due_at:
                if not ticket.resolution_sla_breach_notified and not current_flags_for_ticket.get('resolution_sla_breach_notified'):
                    message = f"Resolution SLA BREACHED for Ticket {ticket_ref}."
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    for manager_id in manager_ids_for_alert:
                        if manager_id != ticket.assignee_user_id: create_notification(manager_id, message + " Escalation.", ticket.id)
                    current_flags_for_ticket['resolution_sla_breach_notified'] = True
            elif not ticket.resolution_sla_nearing_breach_notified and not current_flags_for_ticket.get('resolution_sla_nearing_breach_notified'):
                if (ticket.resolution_due_at - effective_now_for_sla) < timedelta(hours=RESOLUTION_NEARING_THRESHOLD_HOURS):
                    message = f"Resolution SLA Nearing Breach for Ticket {ticket_ref}."
                    if ticket.assignee_user_id: create_notification(ticket.assignee_user_id, message, ticket.id)
                    current_flags_for_ticket['resolution_sla_nearing_breach_notified'] = True

        if current_flags_for_ticket: # If any flags were set for this ticket
            ticket_flags_to_batch_update[ticket.id] = current_flags_for_ticket

    # Batch update ticket flags
    if ticket_flags_to_batch_update:
        print(f"SLA Check: Will attempt to update flags for {len(ticket_flags_to_batch_update)} tickets.")
        for ticket_id_to_flag, flags_to_set in ticket_flags_to_batch_update.items():
            try:
                # ticket_manager.update_ticket is now DB backed.
                # Pass only the flags that need to be set.
                update_ticket(ticket_id_to_flag, **flags_to_set)
            except Exception as e_update:
                print(f"Error updating SLA flags for ticket {ticket_id_to_flag} via ticket_manager: {e_update}", file=sys.stderr)

if __name__ == "__main__":
    print("Notification Manager - Manual SLA Alert Check (ensure DB is populated for meaningful test)")
    # check_and_send_sla_alerts() # Caution: Modifies data and sends notifications
    print("SLA Alert Check finished (manual run).")
