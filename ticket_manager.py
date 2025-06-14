import json
import os
from datetime import datetime, timezone, date # Added date for type hint
from typing import List, Dict, Any, Optional, Tuple # Added Tuple for type hint

from models import Ticket

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
    updated_fields = False

    valid_fields = ['title', 'description', 'type', 'status', 'priority', 'assignee_user_id']
    for key, value in kwargs.items():
        if key in valid_fields:
            # Basic validation (can be more granular)
            if key in ['title', 'description'] and (not isinstance(value, str) or not value):
                raise ValueError(f"{key.capitalize()} cannot be empty.")
            if key == 'assignee_user_id' and value is not None and (not isinstance(value, str) or not value.strip()):
                # Allow None or non-empty string. Empty string "" means unassign.
                value = None if isinstance(value, str) and not value.strip() else value
                if value is not None and not isinstance(value, str): # After "" -> None, check type if not None
                     raise ValueError("Assignee User ID must be a string or None.")

            # Actual update
            if getattr(ticket_to_update, key) != value:
                setattr(ticket_to_update, key, value)
                updated_fields = True

    if not updated_fields: return ticket_to_update # No actual changes to attributes

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
