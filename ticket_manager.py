import json
import os
import shutil # Added for file operations
import uuid # Added for attachment ID
import mimetypes # Added for mimetype guessing
from datetime import datetime, timezone, date
from typing import List, Dict, Any, Optional, Tuple

from models import Ticket

try:
    from user_manager import get_user_by_username
except ModuleNotFoundError:
    print("Warning: user_manager.py not found. Assignee username lookup will not work.", file=sys.stderr)
    def get_user_by_username(username: str) -> Optional[Any]: # Fallback
        return None

# Settings Manager and SLA Calculator imports
try:
    from settings_manager import get_matching_sla_policy, get_business_schedule, get_public_holidays
    from sla_calculator import calculate_due_date
except ModuleNotFoundError:
    print("Warning: settings_manager or sla_calculator not found. SLA features will be impaired.", file=sys.stderr)
    # Fallbacks for SLA related functions
    def get_matching_sla_policy(priority: str, ticket_type: str, policies: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        return None
    def get_business_schedule() -> Dict[str, Optional[Tuple[Any, Any]]]: # Using Any for time fallback
        return {day: None for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]}
    def get_public_holidays() -> List[date]:
        return []
    def calculate_due_date(start_time_utc: datetime, business_hours_to_add: float,
                           business_schedule: Dict[str, Optional[Tuple[Any, Any]]],
                           public_holidays: List[date]) -> datetime:
        # Simple fallback: just add calendar hours
        return start_time_utc + timedelta(hours=business_hours_to_add)


TICKETS_FILE = "tickets.json"

def _load_tickets() -> List[Ticket]:
    try:
        if not os.path.exists(TICKETS_FILE) or os.path.getsize(TICKETS_FILE) == 0: return []
        with open(TICKETS_FILE, 'r') as f: data = json.load(f)
        return [Ticket.from_dict(ticket_data) for ticket_data in data]
    except FileNotFoundError: return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {TICKETS_FILE}. Returning empty list.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Unexpected error loading tickets: {e}", file=sys.stderr)
        return []


def _save_tickets(tickets: List[Ticket]) -> None:
    try:
        with open(TICKETS_FILE, 'w') as f:
            json.dump([ticket.to_dict() for ticket in tickets], f, indent=4)
    except IOError as e:
        print(f"Error saving tickets to {TICKETS_FILE}: {e}", file=sys.stderr)
        raise # Re-raise to indicate save failed
    except Exception as e:
        print(f"Unexpected error saving tickets: {e}", file=sys.stderr)
        raise


def create_ticket(
    title: str, description: str, type: str, requester_user_id: str,
    priority: str = 'Medium', assignee_user_id: Optional[str] = None
) -> Ticket:
    if not title or not isinstance(title, str): raise ValueError("Title required.")
    if not description or not isinstance(description, str): raise ValueError("Description required.")
    if not type or not isinstance(type, str): raise ValueError("Type required.")
    if not requester_user_id or not isinstance(requester_user_id, str): raise ValueError("Requester User ID required.")
    if assignee_user_id is not None and not isinstance(assignee_user_id, str): raise ValueError("Assignee User ID must be string if provided.")

    tickets = _load_tickets()

    # Create ticket instance first (this also sets created_at)
    new_ticket = Ticket(
        title=title, description=description, type=type, priority=priority,
        requester_user_id=requester_user_id, created_by_user_id=requester_user_id,
        assignee_user_id=assignee_user_id
        # SLA fields will be populated next
    )

    # Calculate SLA due dates
    try:
        business_schedule = get_business_schedule()
        public_holidays = get_public_holidays()
        # get_matching_sla_policy will call get_sla_policies if policies=None
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
        # Continue without SLA if calculation fails, or re-raise if SLA is critical

    tickets.append(new_ticket)
    _save_tickets(tickets)
    return new_ticket


def get_ticket(ticket_id: str) -> Optional[Ticket]:
    tickets = _load_tickets()
    for ticket in tickets:
        if ticket.id == ticket_id: return ticket
    return None


def update_ticket(ticket_id: str, **kwargs: Any) -> Optional[Ticket]:
    tickets = _load_tickets()
    ticket_to_update: Optional[Ticket] = None
    ticket_index: int = -1
    for i, t in enumerate(tickets):
        if t.id == ticket_id:
            ticket_to_update = t; ticket_index = i; break
    if not ticket_to_update: return None

    original_data = {
        'status': ticket_to_update.status,
        'assignee_user_id': ticket_to_update.assignee_user_id,
        'priority': ticket_to_update.priority,
        'type': ticket_to_update.type
    }
    updated_fields = False # Initialize before username processing

    # Handle assignee_username if provided
    if 'assignee_username' in kwargs:
        username_to_assign = kwargs.pop('assignee_username', None)
        actual_assignee_user_id: Optional[str] = None
        if username_to_assign and isinstance(username_to_assign, str) and username_to_assign.strip():
            assignee_user_object = get_user_by_username(username_to_assign.strip())
            if assignee_user_object is None:
                raise ValueError(f"Assignee username '{username_to_assign.strip()}' not found.")
            actual_assignee_user_id = assignee_user_object.user_id
        # If username_to_assign is empty or None, actual_assignee_user_id remains None (unassign)

        # Only mark as updated if the derived ID is different from current
        if ticket_to_update.assignee_user_id != actual_assignee_user_id:
            kwargs['assignee_user_id'] = actual_assignee_user_id
            # updated_fields = True # This will be set later when iterating kwargs
        else:
            # If the username maps to the same user ID, no change needed for this field
            # We don't want to process assignee_user_id further if it's not changing.
            # However, if it was the *only* thing passed in kwargs (as assignee_username)
            # and it resolved to the current ID, then updated_fields might remain False.
            # The loop below will handle setting updated_fields correctly if other fields are changing.
            # If assignee_username was the only kwarg and it resolved to the current ID,
            # we effectively do nothing for this field.
            pass


    # Process other valid fields and the potentially derived assignee_user_id
    valid_fields = ['title', 'description', 'type', 'status', 'priority', 'assignee_user_id']
    fields_actually_changed_in_loop = False
    for key, value in kwargs.items():
        if key in valid_fields:
            # Basic validation (can be more granular)
            if key in ['title', 'description'] and (not isinstance(value, str) or not value):
                raise ValueError(f"{key.capitalize()} cannot be empty.")

            if key == 'assignee_user_id':
                # Value here is the ID, either passed directly or derived from username
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    value = None # Allow empty string to unassign
                if value is not None and not isinstance(value, str): # After "" -> None, check type if not None
                     raise ValueError("Assignee User ID must be a string or None.")

            # Actual update
            if getattr(ticket_to_update, key) != value:
                setattr(ticket_to_update, key, value)
                fields_actually_changed_in_loop = True

    # Determine if any update actually happened
    if not fields_actually_changed_in_loop:
        # This means that after processing assignee_username (if any) and all other kwargs,
        # no attribute on ticket_to_update was actually changed from its original value.
        return ticket_to_update # No actual changes to attributes

    ticket_to_update.updated_at = datetime.now(timezone.utc)

    # SLA Recalculation (if priority/type changed)
    priority_changed = 'priority' in kwargs and ticket_to_update.priority != original_data['priority']
    type_changed = 'type' in kwargs and ticket_to_update.type != original_data['type']

    if priority_changed or type_changed:
        try:
            business_schedule = get_business_schedule()
            public_holidays = get_public_holidays()
            new_sla_policy = get_matching_sla_policy(ticket_to_update.priority, ticket_to_update.type)

            ticket_to_update.sla_policy_id = new_sla_policy['policy_id'] if new_sla_policy else None

            if new_sla_policy and new_sla_policy.get('response_time_hours') is not None:
                ticket_to_update.response_due_at = calculate_due_date(
                    ticket_to_update.created_at, float(new_sla_policy['response_time_hours']),
                    business_schedule, public_holidays)
            else: ticket_to_update.response_due_at = None

            if new_sla_policy and new_sla_policy.get('resolution_time_hours') is not None:
                ticket_to_update.resolution_due_at = calculate_due_date(
                    ticket_to_update.created_at, float(new_sla_policy['resolution_time_hours']),
                    business_schedule, public_holidays)
            else: ticket_to_update.resolution_due_at = None
        except Exception as e:
            print(f"Error recalculating SLA for ticket {ticket_id}: {e}", file=sys.stderr)

    # SLA Pause/Resume
    status_changed = 'status' in kwargs and ticket_to_update.status != original_data['status']
    if status_changed:
        if ticket_to_update.status == 'On Hold' and ticket_to_update.sla_paused_at is None:
            ticket_to_update.sla_paused_at = datetime.now(timezone.utc)
        elif original_data['status'] == 'On Hold' and ticket_to_update.status != 'On Hold' and ticket_to_update.sla_paused_at is not None:
            paused_duration = datetime.now(timezone.utc) - ticket_to_update.sla_paused_at
            ticket_to_update.total_paused_duration_seconds += paused_duration.total_seconds()
            ticket_to_update.sla_paused_at = None

        # Set responded_at
        if ticket_to_update.responded_at is None and original_data['status'] == 'Open' and ticket_to_update.status == 'In Progress':
            ticket_to_update.responded_at = ticket_to_update.updated_at # Use ticket's update time for consistency

    # Notifications (Status and Assignment)
    # Import create_notification locally to avoid circular dependency at module level
    try:
        from notification_manager import create_notification
    except ModuleNotFoundError:
        def create_notification(user_id: str, message: str, ticket_id: Optional[str] = None): # type: ignore
            print(f"Warning: create_notification fallback (local in update_ticket) for user {user_id}, msg: {message[:30]}...")
            pass

    if status_changed:
        try:
            msg = f"Ticket '{ticket_to_update.title}' ({ticket_to_update.id[:8]}) status: {original_data['status']} -> {ticket_to_update.status}."
            if ticket_to_update.requester_user_id: create_notification(user_id=ticket_to_update.requester_user_id, message=msg, ticket_id=ticket_to_update.id)
        except Exception as e: print(f"Error (status notification) for {ticket_id}: {e}", file=sys.stderr)

    assignee_changed = 'assignee_user_id' in kwargs and ticket_to_update.assignee_user_id != original_data['assignee_user_id']
    if assignee_changed:
        new_assignee = ticket_to_update.assignee_user_id
        old_assignee = original_data['assignee_user_id']
        ref = f"'{ticket_to_update.title[:20]}...' ({ticket_to_update.id[:8]})"
        try:
            if new_assignee: create_notification(new_assignee, f"You are assigned Ticket {ref}.", ticket_to_update.id)
            if old_assignee: create_notification(old_assignee, f"You are unassigned from Ticket {ref}.", ticket_to_update.id)
            if ticket_to_update.requester_user_id and ticket_to_update.requester_user_id not in [new_assignee, old_assignee]:
                msg = f"Ticket {ref} assigned to {new_assignee}." if new_assignee else f"Ticket {ref} is unassigned."
                create_notification(ticket_to_update.requester_user_id, msg, ticket_to_update.id)
        except Exception as e: print(f"Error (assignment notification) for {ticket_id}: {e}", file=sys.stderr)

    tickets[ticket_index] = ticket_to_update
    _save_tickets(tickets)
    return ticket_to_update


def list_tickets(filters: Optional[Dict[str, Any]] = None) -> List[Ticket]:
    tickets = _load_tickets()
    if not filters: return tickets
    def ticket_matches(ticket: Ticket, key: str, value: Any) -> bool:
        attr_val = getattr(ticket, key, None)
        if isinstance(attr_val, list) and isinstance(value, list): return value == attr_val # For comments maybe
        if isinstance(attr_val, datetime) and isinstance(value, date): return attr_val.date() == value
        return attr_val == value
    return [t for t in tickets if all(ticket_matches(t, k, v) for k, v in filters.items())]


def add_comment_to_ticket(ticket_id: str, user_id: str, comment_text: str) -> Optional[Ticket]:
    if not comment_text.strip(): raise ValueError("Comment text cannot be empty.")
    if not user_id.strip(): raise ValueError("User ID for comment cannot be empty.")

    tickets = _load_tickets()
    ticket_to_update: Optional[Ticket] = None; ticket_index: int = -1
    for i, t in enumerate(tickets):
        if t.id == ticket_id: ticket_to_update = t; ticket_index = i; break
    if not ticket_to_update: return None

    original_status_for_response_check = ticket_to_update.status # For responded_at logic

    ticket_to_update.add_comment(user_id=user_id, text=comment_text) # This updates ticket.updated_at

    # Set responded_at if first non-requester comment on an Open ticket
    if ticket_to_update.responded_at is None and \
       user_id != ticket_to_update.requester_user_id and \
       original_status_for_response_check == 'Open': # Check original status
        ticket_to_update.responded_at = ticket_to_update.updated_at # Use comment's effective timestamp

    tickets[ticket_index] = ticket_to_update
    try: _save_tickets(tickets)
    except Exception as e:
        print(f"Error saving tickets after adding comment to {ticket_id}: {e}", file=sys.stderr)
        return None # Save failed

    # Comment Notifications
    # Import create_notification locally to avoid circular dependency at module level
    try:
        from notification_manager import create_notification
    except ModuleNotFoundError:
        # This inner fallback is less likely to be hit if the one in update_ticket is defined,
        # but kept for robustness if add_comment_to_ticket is called from elsewhere without update_ticket's import.
        def create_notification(user_id: str, message: str, ticket_id: Optional[str] = None): # type: ignore
            print(f"Warning: create_notification fallback (local in add_comment) for user {user_id}, msg: {message[:30]}...")
            pass

    try:
        ref = f"'{ticket_to_update.title[:20]}...' ({ticket_to_update.id[:8]})"
        commenter_ref = f"user {user_id[:8]}"
        if ticket_to_update.requester_user_id != user_id:
            if ticket_to_update.requester_user_id: # Ensure requester_user_id is not None
                 create_notification(user_id=ticket_to_update.requester_user_id,
                                     message=f"New comment on Ticket {ref} by {commenter_ref}.",
                                     ticket_id=ticket_to_update.id)
        if ticket_to_update.assignee_user_id and \
           ticket_to_update.assignee_user_id != user_id and \
           ticket_to_update.assignee_user_id != ticket_to_update.requester_user_id:
            create_notification(user_id=ticket_to_update.assignee_user_id,
                                message=f"New comment on assigned Ticket {ref} by {commenter_ref}.",
                                ticket_id=ticket_to_update.id)
    except Exception as e: print(f"Error (comment notification) for {ticket_id}: {e}", file=sys.stderr)

    return ticket_to_update


ATTACHMENT_DIR = "ticket_attachments" # Directory to store attachments

def add_attachment_to_ticket(
    ticket_id: str,
    uploader_user_id: str,
    source_file_path: str,
    original_filename: str
) -> Optional[Ticket]:
    """Adds attachment metadata to a ticket, copies the file to a storage directory, and saves the ticket."""
    if not all([ticket_id, uploader_user_id, source_file_path, original_filename]):
        raise ValueError("Ticket ID, uploader ID, source file path, and original filename are required.")
    if not os.path.exists(source_file_path):
        raise FileNotFoundError(f"Source file not found: {source_file_path}")
    if not os.path.isfile(source_file_path):
        raise ValueError(f"Source path is not a file: {source_file_path}")

    os.makedirs(ATTACHMENT_DIR, exist_ok=True)

    attachment_id = "att_" + uuid.uuid4().hex
    _, file_extension = os.path.splitext(original_filename)
    stored_filename = f"{attachment_id}{file_extension}"
    destination_path = os.path.join(ATTACHMENT_DIR, stored_filename)

    try:
        shutil.copy2(source_file_path, destination_path)
    except IOError as e:
        print(f"Error copying attachment file for ticket {ticket_id}: {e}", file=sys.stderr)
        raise

    filesize = os.path.getsize(destination_path)
    mimetype, _ = mimetypes.guess_type(destination_path)
    mimetype = mimetype or 'application/octet-stream'

    attachment_metadata = {
        "attachment_id": attachment_id,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "uploader_user_id": uploader_user_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "filesize": filesize,
        "mimetype": mimetype
    }

    tickets = _load_tickets()
    ticket_to_update: Optional[Ticket] = None
    ticket_index: int = -1
    for i, t in enumerate(tickets):
        if t.id == ticket_id:
            ticket_to_update = t
            ticket_index = i
            break

    if not ticket_to_update:
        try:
            if os.path.exists(destination_path): os.remove(destination_path)
        except OSError as e_del:
            print(f"Error cleaning up orphaned attachment file {destination_path}: {e_del}", file=sys.stderr)
        return None

    if not hasattr(ticket_to_update, 'attachments') or ticket_to_update.attachments is None:
         ticket_to_update.attachments = []

    ticket_to_update.attachments.append(attachment_metadata)
    ticket_to_update.updated_at = datetime.now(timezone.utc)

    tickets[ticket_index] = ticket_to_update
    try:
        _save_tickets(tickets)
    except Exception as e_save:
        print(f"Error saving ticket after adding attachment {attachment_id} to ticket {ticket_id}: {e_save}", file=sys.stderr)
        try:
            if os.path.exists(destination_path): os.remove(destination_path)
            print(f"Rolled back file copy for attachment {attachment_id} due to save error.", file=sys.stderr)
        except OSError as e_del_rollback:
            print(f"Error rolling back attachment file {destination_path}: {e_del_rollback}", file=sys.stderr)
        return None

    return ticket_to_update


def remove_attachment_from_ticket(ticket_id: str, attachment_id: str) -> Optional[Ticket]:
    """Removes attachment metadata from a ticket, deletes the file from storage, and saves the ticket."""
    if not ticket_id or not attachment_id:
        raise ValueError("Ticket ID and Attachment ID are required.")

    tickets = _load_tickets()
    ticket_to_update: Optional[Ticket] = None
    ticket_index: int = -1
    for i, t in enumerate(tickets):
        if t.id == ticket_id:
            ticket_to_update = t
            ticket_index = i
            break

    if not ticket_to_update:
        return None

    if not hasattr(ticket_to_update, 'attachments') or ticket_to_update.attachments is None:
        return ticket_to_update

    attachment_to_remove_metadata: Optional[Dict[str, Any]] = None

    new_attachments_list = []
    for att in ticket_to_update.attachments:
        if att.get("attachment_id") == attachment_id:
            attachment_to_remove_metadata = att
        else:
            new_attachments_list.append(att)

    if attachment_to_remove_metadata is None:
        return ticket_to_update

    ticket_to_update.attachments = new_attachments_list

    stored_filename = attachment_to_remove_metadata.get("stored_filename")
    if stored_filename:
        file_path_to_delete = os.path.join(ATTACHMENT_DIR, stored_filename)
        if os.path.exists(file_path_to_delete):
            try:
                os.remove(file_path_to_delete)
            except OSError as e:
                print(f"Error deleting attachment file {file_path_to_delete}: {e}", file=sys.stderr)
        else:
            print(f"Warning: Attachment file not found for deletion: {file_path_to_delete}", file=sys.stderr)

    ticket_to_update.updated_at = datetime.now(timezone.utc)
    tickets[ticket_index] = ticket_to_update

    try:
        _save_tickets(tickets)
    except Exception as e_save:
        print(f"Error saving ticket after removing attachment {attachment_id} from ticket {ticket_id}: {e_save}", file=sys.stderr)
        return None

    return ticket_to_update
