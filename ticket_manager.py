import json
import os
import shutil
import uuid
import mimetypes
import sqlite3
import sys # For stderr
from datetime import datetime, timezone, date, timedelta # Added timedelta
from typing import List, Dict, Any, Optional, Tuple

try:
    from models import Ticket
except ModuleNotFoundError:
    print("Critical Error: models.py not found. Ticket manager cannot function.", file=sys.stderr)
    class Ticket: # Basic fallback
        id: str; title: str; description: str; type: str; status: str; priority: str
        requester_user_id: str; created_by_user_id: str; assignee_user_id: Optional[str]
        comments: List[Dict[str, str]]; created_at: datetime; updated_at: datetime
        attachments: List[Dict[str, Any]]
        # Simplified init for fallback
        def __init__(self, title: str, description: str, type: str, requester_user_id: str, created_by_user_id: str, **kwargs):
            self.id = kwargs.get('ticket_id') or "fb_ticket_id_" + uuid.uuid4().hex
            self.title = title; self.description = description; self.type = type
            self.requester_user_id = requester_user_id; self.created_by_user_id = created_by_user_id
            self.status = kwargs.get('status', 'Open'); self.priority = kwargs.get('priority', 'Medium')
            self.assignee_user_id = kwargs.get('assignee_user_id')
            self.comments = kwargs.get('comments', [])
            self.created_at = kwargs.get('created_at') or datetime.now(timezone.utc)
            self.updated_at = kwargs.get('updated_at') or self.created_at
            self.attachments = kwargs.get('attachments', [])
            # Add other fields as dummy if needed by methods below
            self.sla_policy_id=None; self.response_due_at=None; self.resolution_due_at=None; self.responded_at=None;
            self.sla_paused_at=None; self.total_paused_duration_seconds=0.0; self.response_sla_breach_notified=False;
            self.resolution_sla_breach_notified=False; self.response_sla_nearing_breach_notified=False;
            self.resolution_sla_nearing_breach_notified=False

        def add_comment(self, user_id: str, text: str): self.comments.append({'user_id': user_id, 'text': text, 'timestamp': datetime.now(timezone.utc).isoformat()})
        @classmethod
        def from_dict(cls, data:dict): return cls(**data) # Highly simplified
        def to_dict(self) -> dict: return {k:v for k,v in self.__dict__.items() if not k.startswith('_')}


try:
    from database_setup import get_db_connection
except ModuleNotFoundError:
    print("Critical Error: database_setup.py not found. Ticket manager cannot function.", file=sys.stderr)
    def get_db_connection(): raise ConnectionError("Database setup module not found.")

# user_manager.get_user_by_username will be imported dynamically to avoid circular dependency issues at init
# If it was refactored to not depend on ticket_manager, direct import is fine.

# Settings Manager and SLA Calculator imports (assuming they don't import ticket_manager at module level)
try:
    from settings_manager import get_matching_sla_policy, get_business_schedule, get_public_holidays
    from sla_calculator import calculate_due_date
except ModuleNotFoundError:
    print("Warning: settings_manager or sla_calculator not found. SLA features will be impaired.", file=sys.stderr)
    def get_matching_sla_policy(priority: str, ticket_type: str, policies=None): return None
    def get_business_schedule(): return {day: None for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]}
    def get_public_holidays(): return []
    def calculate_due_date(start, hours, schedule, holidays): return start + timedelta(hours=hours)


ATTACHMENT_DIR = "ticket_attachments" # Directory to store attachments
os.makedirs(ATTACHMENT_DIR, exist_ok=True) # Ensure it exists

def _iso_to_datetime(iso_str: Optional[str]) -> Optional[datetime]:
    if not iso_str: return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None # Or raise error

def _row_to_ticket(row: sqlite3.Row) -> Optional[Ticket]:
    """Converts a sqlite3.Row to a Ticket object."""
    if not row:
        return None

    # Deserialize JSON fields
    comments_list = json.loads(row["comments"]) if row["comments"] else []
    attachments_list = json.loads(row["attachments"]) if row["attachments"] else []

    # Create Ticket object using direct field mapping (constructor validates)
    # Pass password_hash as None since it's not stored with the ticket object directly
    return Ticket(
        ticket_id=row["id"], # Constructor uses ticket_id
        title=row["title"],
        description=row["description"],
        type=row["type"],
        status=row["status"],
        priority=row["priority"],
        requester_user_id=row["requester_user_id"],
        created_by_user_id=row["created_by_user_id"],
        assignee_user_id=row["assignee_user_id"],
        comments=comments_list,
        created_at=_iso_to_datetime(row["created_at"]),
        updated_at=_iso_to_datetime(row["updated_at"]),
        sla_policy_id=row["sla_policy_id"],
        response_due_at=_iso_to_datetime(row["response_due_at"]),
        resolution_due_at=_iso_to_datetime(row["resolution_due_at"]),
        responded_at=_iso_to_datetime(row["responded_at"]),
        sla_paused_at=_iso_to_datetime(row["sla_paused_at"]),
        total_paused_duration_seconds=row["total_paused_duration_seconds"],
        response_sla_breach_notified=bool(row["response_sla_breach_notified"]),
        resolution_sla_breach_notified=bool(row["resolution_sla_breach_notified"]),
        response_sla_nearing_breach_notified=bool(row["response_sla_nearing_breach_notified"]),
        resolution_sla_nearing_breach_notified=bool(row["resolution_sla_nearing_breach_notified"]),
        attachments=attachments_list
    )

def _get_ticket_internal(ticket_id: str, cursor: sqlite3.Cursor) -> Optional[Ticket]:
    """Internal helper to fetch a ticket using an existing cursor."""
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    return _row_to_ticket(row)

def create_ticket(
    title: str, description: str, type: str, requester_user_id: str,
    created_by_user_id: str, # Added this for consistency with model
    priority: str = 'Medium', assignee_user_id: Optional[str] = None
) -> Ticket:
    # Validations are largely handled by the Ticket model constructor
    # Create ticket instance first (this also sets created_at, default status/priority etc.)
    new_ticket = Ticket(
        title=title, description=description, type=type, priority=priority,
        requester_user_id=requester_user_id, created_by_user_id=created_by_user_id,
        assignee_user_id=assignee_user_id
    )

    # Calculate SLA due dates (logic remains the same)
    try:
        business_schedule = get_business_schedule()
        public_holidays = get_public_holidays()
        sla_policy = get_matching_sla_policy(new_ticket.priority, new_ticket.type)

        if sla_policy:
            new_ticket.sla_policy_id = sla_policy['policy_id']
            response_hours = sla_policy.get('response_time_hours')
            resolution_hours = sla_policy.get('resolution_time_hours')

            if response_hours is not None:
                new_ticket.response_due_at = calculate_due_date(
                    new_ticket.created_at, float(response_hours),
                    business_schedule, public_holidays
                )
            if resolution_hours is not None:
                new_ticket.resolution_due_at = calculate_due_date(
                    new_ticket.created_at, float(resolution_hours),
                    business_schedule, public_holidays
                )
    except Exception as e:
        print(f"Error applying SLA policy during ticket creation for {new_ticket.id}: {e}", file=sys.stderr)
        # Decide if this error should prevent ticket creation or just be logged

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO tickets (
                id, title, description, type, status, priority,
                requester_user_id, created_by_user_id, assignee_user_id,
                comments, created_at, updated_at, sla_policy_id,
                response_due_at, resolution_due_at, responded_at, sla_paused_at,
                total_paused_duration_seconds, response_sla_breach_notified,
                resolution_sla_breach_notified, response_sla_nearing_breach_notified,
                resolution_sla_nearing_breach_notified, attachments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_ticket.id, new_ticket.title, new_ticket.description, new_ticket.type, new_ticket.status, new_ticket.priority,
            new_ticket.requester_user_id, new_ticket.created_by_user_id, new_ticket.assignee_user_id,
            json.dumps(new_ticket.comments), new_ticket.created_at.isoformat(), new_ticket.updated_at.isoformat(),
            new_ticket.sla_policy_id,
            new_ticket.response_due_at.isoformat() if new_ticket.response_due_at else None,
            new_ticket.resolution_due_at.isoformat() if new_ticket.resolution_due_at else None,
            new_ticket.responded_at.isoformat() if new_ticket.responded_at else None,
            new_ticket.sla_paused_at.isoformat() if new_ticket.sla_paused_at else None,
            new_ticket.total_paused_duration_seconds,
            new_ticket.response_sla_breach_notified, new_ticket.resolution_sla_breach_notified,
            new_ticket.response_sla_nearing_breach_notified, new_ticket.resolution_sla_nearing_breach_notified,
            json.dumps(new_ticket.attachments)
        ))
        conn.commit()
        return new_ticket
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error creating ticket {new_ticket.id}: {e}", file=sys.stderr)
        raise Exception(f"Failed to save ticket {new_ticket.id} to database.") from e # Re-raise
    finally:
        conn.close()

def get_ticket(ticket_id: str) -> Optional[Ticket]:
    if not ticket_id: return None
    conn = get_db_connection()
    cursor = conn.cursor()
    ticket = _get_ticket_internal(ticket_id, cursor)
    conn.close()
    return ticket

def update_ticket(ticket_id: str, **kwargs: Any) -> Optional[Ticket]:
    if not ticket_id: return None

    conn = get_db_connection()
    cursor = conn.cursor()

    ticket_to_update = _get_ticket_internal(ticket_id, cursor)
    if not ticket_to_update:
        conn.close()
        return None

    original_data = {
        'status': ticket_to_update.status,
        'assignee_user_id': ticket_to_update.assignee_user_id,
        'priority': ticket_to_update.priority,
        'type': ticket_to_update.type
    }

    # Dynamically import get_user_by_username to avoid circular import issues at startup
    try:
        from user_manager import get_user_by_username
    except ImportError:
        print("Warning: user_manager.get_user_by_username not found for assignee lookup in update_ticket.", file=sys.stderr)
        def get_user_by_username(username: str): return None # Fallback

    # Handle assignee_username if provided
    if 'assignee_username' in kwargs:
        username_to_assign = kwargs.pop('assignee_username', None)
        actual_assignee_user_id: Optional[str] = None
        if username_to_assign and isinstance(username_to_assign, str) and username_to_assign.strip():
            assignee_user_object = get_user_by_username(username_to_assign.strip()) # user_manager is now DB backed
            if assignee_user_object is None:
                conn.close()
                raise ValueError(f"Assignee username '{username_to_assign.strip()}' not found.")
            actual_assignee_user_id = assignee_user_object.user_id

        if ticket_to_update.assignee_user_id != actual_assignee_user_id:
            kwargs['assignee_user_id'] = actual_assignee_user_id
            # No need to set updated_fields here, the loop below handles it.

    # Process other valid fields
    fields_to_update_on_model: Dict[str, Any] = {}
    valid_fields = ['title', 'description', 'type', 'status', 'priority', 'assignee_user_id',
                    'response_sla_breach_notified', 'resolution_sla_breach_notified',
                    'response_sla_nearing_breach_notified', 'resolution_sla_nearing_breach_notified'] # Added SLA flags

    for key, value in kwargs.items():
        if key in valid_fields and hasattr(ticket_to_update, key):
            if getattr(ticket_to_update, key) != value:
                setattr(ticket_to_update, key, value) # Update the model instance
                fields_to_update_on_model[key] = value

    if not fields_to_update_on_model: # No actual changes to attributes that are directly updatable this way
        conn.close()
        return ticket_to_update

    ticket_to_update.updated_at = datetime.now(timezone.utc)
    fields_to_update_on_model['updated_at'] = ticket_to_update.updated_at.isoformat()


    # SLA Recalculation, Pause/Resume, Responded_at logic (operates on the ticket_to_update model instance)
    priority_changed = 'priority' in fields_to_update_on_model and ticket_to_update.priority != original_data['priority']
    type_changed = 'type' in fields_to_update_on_model and ticket_to_update.type != original_data['type']

    if priority_changed or type_changed:
        try:
            # ... (SLA calculation logic as before, update ticket_to_update fields) ...
            # This logic updates ticket_to_update.sla_policy_id, response_due_at, resolution_due_at
            # These will then need to be added to fields_to_update_on_model for DB commit
            business_schedule = get_business_schedule()
            public_holidays = get_public_holidays()
            new_sla_policy = get_matching_sla_policy(ticket_to_update.priority, ticket_to_update.type)

            ticket_to_update.sla_policy_id = new_sla_policy['policy_id'] if new_sla_policy else None
            fields_to_update_on_model['sla_policy_id'] = ticket_to_update.sla_policy_id

            if new_sla_policy and new_sla_policy.get('response_time_hours') is not None:
                ticket_to_update.response_due_at = calculate_due_date(
                    ticket_to_update.created_at, float(new_sla_policy['response_time_hours']),
                    business_schedule, public_holidays)
            else: ticket_to_update.response_due_at = None
            fields_to_update_on_model['response_due_at'] = ticket_to_update.response_due_at.isoformat() if ticket_to_update.response_due_at else None

            if new_sla_policy and new_sla_policy.get('resolution_time_hours') is not None:
                ticket_to_update.resolution_due_at = calculate_due_date(
                    ticket_to_update.created_at, float(new_sla_policy['resolution_time_hours']),
                    business_schedule, public_holidays)
            else: ticket_to_update.resolution_due_at = None
            fields_to_update_on_model['resolution_due_at'] = ticket_to_update.resolution_due_at.isoformat() if ticket_to_update.resolution_due_at else None
        except Exception as e:
            print(f"Error recalculating SLA for ticket {ticket_id}: {e}", file=sys.stderr)


    status_changed = 'status' in fields_to_update_on_model and ticket_to_update.status != original_data['status']
    if status_changed:
        # ... (SLA Pause/Resume logic as before, update ticket_to_update fields) ...
        # This logic updates ticket_to_update.sla_paused_at, total_paused_duration_seconds, responded_at
        if ticket_to_update.status == 'On Hold' and ticket_to_update.sla_paused_at is None: # Assuming 'On Hold' is a valid status
            ticket_to_update.sla_paused_at = datetime.now(timezone.utc)
        elif original_data['status'] == 'On Hold' and ticket_to_update.status != 'On Hold' and ticket_to_update.sla_paused_at is not None:
            paused_duration = datetime.now(timezone.utc) - ticket_to_update.sla_paused_at
            ticket_to_update.total_paused_duration_seconds += paused_duration.total_seconds()
            ticket_to_update.sla_paused_at = None
        fields_to_update_on_model['sla_paused_at'] = ticket_to_update.sla_paused_at.isoformat() if ticket_to_update.sla_paused_at else None
        fields_to_update_on_model['total_paused_duration_seconds'] = ticket_to_update.total_paused_duration_seconds

        if ticket_to_update.responded_at is None and original_data['status'] == 'Open' and ticket_to_update.status == 'In Progress':
            ticket_to_update.responded_at = ticket_to_update.updated_at
        fields_to_update_on_model['responded_at'] = ticket_to_update.responded_at.isoformat() if ticket_to_update.responded_at else None


    # Prepare SQL update statement
    set_clauses = [f"{key} = ?" for key in fields_to_update_on_model.keys()]
    sql_values = list(fields_to_update_on_model.values())
    sql_values.append(ticket_id)

    try:
        cursor.execute(f"UPDATE tickets SET {', '.join(set_clauses)} WHERE id = ?", tuple(sql_values))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error updating ticket {ticket_id}: {e}", file=sys.stderr)
        conn.close()
        # Potentially re-fetch to ensure consistency if partial updates on model occurred before error
        return get_ticket(ticket_id) # Or return None / raise
    finally:
        if conn: conn.close() # Ensure connection is closed

    # Notifications logic (remains the same, but uses updated ticket_to_update object)
    # Import create_notification locally to avoid circular dependency
    try:
        from notification_manager import create_notification # notification_manager will be DB backed
    except ModuleNotFoundError:
        def create_notification(user_id, message, ticket_id=None): print(f"Fallback create_notification for {user_id}")

    if status_changed:
        msg = f"Ticket '{ticket_to_update.title}' ({ticket_to_update.id[:8]}) status: {original_data['status']} -> {ticket_to_update.status}."
        if ticket_to_update.requester_user_id: create_notification(user_id=ticket_to_update.requester_user_id, message=msg, ticket_id=ticket_to_update.id)

    assignee_changed_in_kwargs = 'assignee_user_id' in fields_to_update_on_model # Check if this specific field was part of the update
    if assignee_changed_in_kwargs and ticket_to_update.assignee_user_id != original_data['assignee_user_id']:
        new_assignee_id = ticket_to_update.assignee_user_id
        old_assignee_id = original_data['assignee_user_id']
        ref = f"'{ticket_to_update.title[:20]}...' ({ticket_to_update.id[:8]})"
        if new_assignee_id: create_notification(new_assignee_id, f"You are assigned Ticket {ref}.", ticket_to_update.id)
        if old_assignee_id: create_notification(old_assignee_id, f"You are unassigned from Ticket {ref}.", ticket_to_update.id)
        # ... (notify requester logic)

    return get_ticket(ticket_id) # Re-fetch the fully updated ticket from DB

def list_tickets(filters: Optional[Dict[str, Any]] = None) -> List[Ticket]:
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM tickets"
    filter_values = []

    if filters:
        conditions = []
        for key, value in filters.items():
            # Whitelist keys to prevent SQL injection if filters come from less trusted sources
            # For internal use, this might be relaxed, but good practice.
            valid_filter_keys = [
                'id', 'title', 'type', 'status', 'priority',
                'requester_user_id', 'created_by_user_id', 'assignee_user_id',
                'sla_policy_id'
                # Date fields need special handling if filtering by range or partial date
            ]
            if key in valid_filter_keys:
                if key == 'title': # Partial match for title
                    conditions.append(f"LOWER(title) LIKE ?")
                    filter_values.append(f"%{str(value).lower()}%")
                else: # Exact match
                    conditions.append(f"{key} = ?")
                    filter_values.append(value)
            elif key == 'created_at_date': # Example: filter by specific date part
                 if isinstance(value, date) or (isinstance(value, str) and _iso_to_datetime(value)):
                    conditions.append("DATE(created_at) = ?")
                    filter_values.append(str(value) if isinstance(value, date) else value.split('T')[0])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

    # Add sorting (optional, example: by updated_at desc)
    query += " ORDER BY updated_at DESC"

    try:
        cursor.execute(query, tuple(filter_values))
        rows = cursor.fetchall()
        tickets = [_row_to_ticket(row) for row in rows if row]
        return [t for t in tickets if t is not None]
    except sqlite3.Error as e:
        print(f"Database error listing tickets: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()


def add_comment_to_ticket(ticket_id: str, user_id: str, comment_text: str) -> Optional[Ticket]:
    if not comment_text.strip(): raise ValueError("Comment text cannot be empty.")
    if not user_id.strip(): raise ValueError("User ID for comment cannot be empty.")

    conn = get_db_connection()
    cursor = conn.cursor()

    ticket = _get_ticket_internal(ticket_id, cursor)
    if not ticket:
        conn.close()
        return None

    original_status_for_response_check = ticket.status

    # Add comment to the Python model instance
    ticket.add_comment(user_id=user_id, text=comment_text) # This updates ticket.updated_at locally

    # Set responded_at on the model instance if applicable
    if ticket.responded_at is None and \
        user_id != ticket.requester_user_id and \
        original_status_for_response_check == 'Open':
        ticket.responded_at = ticket.updated_at

    # Persist changes to DB
    try:
        cursor.execute('''
            UPDATE tickets
            SET comments = ?, updated_at = ?, responded_at = ?
            WHERE id = ?
        ''', (
            json.dumps(ticket.comments),
            ticket.updated_at.isoformat(),
            ticket.responded_at.isoformat() if ticket.responded_at else None,
            ticket_id
        ))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error adding comment to ticket {ticket_id}: {e}", file=sys.stderr)
        return None # Or re-fetch the ticket to return its previous state
    finally:
        conn.close()

    # Notifications (logic remains the same)
    try:
        from notification_manager import create_notification
    except ModuleNotFoundError:
        def create_notification(uid, msg, tid=None): print(f"Fallback notif for {uid}")

    # ... (notification sending logic as before, using the 'ticket' object) ...
    try:
        ref = f"'{ticket.title[:20]}...' ({ticket.id[:8]})"
        commenter_ref = f"user {user_id[:8]}" # Assuming user_id is a string like object
        if ticket.requester_user_id != user_id and ticket.requester_user_id:
             create_notification(user_id=ticket.requester_user_id,
                                 message=f"New comment on Ticket {ref} by {commenter_ref}.",
                                 ticket_id=ticket.id)
        if ticket.assignee_user_id and ticket.assignee_user_id != user_id and \
            ticket.assignee_user_id != ticket.requester_user_id:
            create_notification(user_id=ticket.assignee_user_id,
                                message=f"New comment on assigned Ticket {ref} by {commenter_ref}.",
                                ticket_id=ticket.id)
    except Exception as e: print(f"Error (comment notification) for {ticket_id}: {e}", file=sys.stderr)

    return get_ticket(ticket_id) # Re-fetch to ensure consistency

def add_attachment_to_ticket(
    ticket_id: str, uploader_user_id: str, source_file_path: str, original_filename: str
) -> Optional[Ticket]:
    # File system operations remain largely the same
    if not all([ticket_id, uploader_user_id, source_file_path, original_filename]):
        raise ValueError("All parameters are required for adding attachment.")
    if not os.path.exists(source_file_path) or not os.path.isfile(source_file_path):
        raise FileNotFoundError(f"Source file not found or is not a file: {source_file_path}")

    attachment_id = "att_" + uuid.uuid4().hex
    _, file_extension = os.path.splitext(original_filename)
    stored_filename = f"{attachment_id}{file_extension}"
    destination_path = os.path.join(ATTACHMENT_DIR, stored_filename)

    try:
        shutil.copy2(source_file_path, destination_path)
    except IOError as e:
        print(f"Error copying attachment file for ticket {ticket_id}: {e}", file=sys.stderr)
        raise # Re-raise, operation failed critically

    filesize = os.path.getsize(destination_path)
    mimetype, _ = mimetypes.guess_type(destination_path)
    mimetype = mimetype or 'application/octet-stream'

    attachment_metadata = {
        "attachment_id": attachment_id, "original_filename": original_filename,
        "stored_filename": stored_filename, "uploader_user_id": uploader_user_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "filesize": filesize, "mimetype": mimetype
    }

    conn = get_db_connection()
    cursor = conn.cursor()
    ticket = _get_ticket_internal(ticket_id, cursor)

    if not ticket:
        conn.close()
        # Cleanup copied file if ticket not found
        if os.path.exists(destination_path): os.remove(destination_path)
        return None

    ticket.attachments.append(attachment_metadata)
    ticket.updated_at = datetime.now(timezone.utc)

    try:
        cursor.execute("UPDATE tickets SET attachments = ?, updated_at = ? WHERE id = ?",
                       (json.dumps(ticket.attachments), ticket.updated_at.isoformat(), ticket_id))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error adding attachment to ticket {ticket_id}: {e}", file=sys.stderr)
        # Cleanup copied file on DB error
        if os.path.exists(destination_path): os.remove(destination_path)
        return None # Or re-fetch
    finally:
        conn.close()

    return get_ticket(ticket_id) # Re-fetch

def remove_attachment_from_ticket(ticket_id: str, attachment_id: str) -> Optional[Ticket]:
    if not ticket_id or not attachment_id:
        raise ValueError("Ticket ID and Attachment ID are required.")

    conn = get_db_connection()
    cursor = conn.cursor()
    ticket = _get_ticket_internal(ticket_id, cursor)

    if not ticket:
        conn.close()
        return None

    attachment_to_remove_metadata: Optional[Dict[str, Any]] = None
    new_attachments_list = []
    for att in ticket.attachments:
        if att.get("attachment_id") == attachment_id:
            attachment_to_remove_metadata = att
        else:
            new_attachments_list.append(att)

    if attachment_to_remove_metadata is None: # Attachment not found in metadata
        conn.close()
        return ticket # No change

    ticket.attachments = new_attachments_list
    ticket.updated_at = datetime.now(timezone.utc)

    try:
        cursor.execute("UPDATE tickets SET attachments = ?, updated_at = ? WHERE id = ?",
                       (json.dumps(ticket.attachments), ticket.updated_at.isoformat(), ticket_id))
        conn.commit()

        # If DB update is successful, delete the file
        stored_filename = attachment_to_remove_metadata.get("stored_filename")
        if stored_filename:
            file_path_to_delete = os.path.join(ATTACHMENT_DIR, stored_filename)
            if os.path.exists(file_path_to_delete):
                try:
                    os.remove(file_path_to_delete)
                except OSError as e_file: # Log error but proceed, metadata is removed
                    print(f"Error deleting attachment file {file_path_to_delete}: {e_file}", file=sys.stderr)
            else:
                print(f"Warning: Attachment file not found for deletion: {file_path_to_delete}", file=sys.stderr)

    except sqlite3.Error as e_db:
        conn.rollback()
        print(f"Database error removing attachment from ticket {ticket_id}: {e_db}", file=sys.stderr)
        return None # Or re-fetch to return previous state
    finally:
        conn.close()

    return get_ticket(ticket_id) # Re-fetch
