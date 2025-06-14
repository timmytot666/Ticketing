import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from models import Ticket
try:
    from notification_manager import create_notification
except ModuleNotFoundError:
    # Fallback if notification_manager is not available, e.g. during isolated tests
    # This allows ticket_manager to still be imported, but notifications won't be created.
    def create_notification(user_id: str, message: str, ticket_id: Optional[str] = None): # type: ignore
        print(f"Warning: create_notification fallback used for user {user_id}, message: {message[:30]}...")
        pass # In a real scenario, might log this to a more persistent system.

TICKETS_FILE = "tickets.json"

def _load_tickets() -> List[Ticket]:
    """
    Reads tickets from tickets.json.
    If the file doesn't exist or is empty, returns an empty list.
    Otherwise, parses the JSON content and returns a list of Ticket objects.
    Handles potential FileNotFoundError and json.JSONDecodeError.
    """
    try:
        with open(TICKETS_FILE, 'r') as f:
            # Check if file is empty
            if os.fstat(f.fileno()).st_size == 0:
                return []
            data = json.load(f)
            return [Ticket.from_dict(ticket_data) for ticket_data in data]
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        # Consider logging this error instead of just printing
        print(f"Error: Could not decode JSON from {TICKETS_FILE}. Returning empty list.")
        return []

def _save_tickets(tickets: List[Ticket]) -> None:
    """
    Takes a list of Ticket objects.
    Converts each Ticket object to its dictionary representation.
    Writes the list of dictionaries to tickets.json as JSON.
    """
    with open(TICKETS_FILE, 'w') as f:
        json.dump([ticket.to_dict() for ticket in tickets], f, indent=4)

def create_ticket(
    title: str,
    description: str,
    type: str,
    requester_user_id: str, # Changed from requester_email
    priority: str = 'Medium',
    assignee_user_id: Optional[str] = None # Added
) -> Ticket:
    """
    Loads existing tickets.
    Creates a new Ticket instance after validating inputs.
    Appends the new ticket to the list.
    Saves the updated list of tickets.
    Returns the newly created Ticket object.
    Raises ValueError for invalid inputs.
    """
    # Manager level validation for presence and basic type
    if not title or not isinstance(title, str):
        raise ValueError("Title is required and must be a non-empty string.")
    if not description or not isinstance(description, str):
        raise ValueError("Description is required and must be a non-empty string.")
    if not type or not isinstance(type, str):
        raise ValueError("Type is required and must be a non-empty string.")
    # Changed: requester_email validation removed, requester_user_id validation will be handled by Ticket model
    if not requester_user_id or not isinstance(requester_user_id, str):
        raise ValueError("Requester User ID is required and must be a non-empty string.")
    if assignee_user_id is not None and not isinstance(assignee_user_id, str):
        raise ValueError("Assignee User ID must be a string if provided.")


    tickets = _load_tickets()
    try:
        # Ticket class __init__ will perform its own validation
        new_ticket = Ticket(
            title=title,
            description=description,
            type=type,
            priority=priority,
            requester_user_id=requester_user_id,    # For Ticket's requester_user_id
            created_by_user_id=requester_user_id, # For Ticket's created_by_user_id
            assignee_user_id=assignee_user_id     # For Ticket's assignee_user_id
        )
    except ValueError: # Catch ValueError from Ticket instantiation
        raise  # Re-raise to be handled by the CLI

    tickets.append(new_ticket)
    _save_tickets(tickets)
    return new_ticket

def get_ticket(ticket_id: str) -> Optional[Ticket]:
    """
    Loads tickets.
    Searches for a ticket with the given ticket_id.
    Returns the Ticket object if found, otherwise returns None.
    """
    tickets = _load_tickets()
    for ticket in tickets:
        if ticket.id == ticket_id:
            return ticket
    return None

def update_ticket(ticket_id: str, **kwargs: Any) -> Optional[Ticket]:
    """
    Loads tickets.
    Finds the ticket with the given ticket_id.
    If found, updates the ticket's attributes based on the kwargs provided,
    after validating them.
    Updates the updated_at timestamp.
    Saves the updated list of tickets.
    Returns the updated Ticket object if found and updated, otherwise None.
    Raises ValueError for invalid inputs.
    """
    tickets = _load_tickets()
    ticket_to_update = None
    ticket_index = -1

    for i, t in enumerate(tickets):
        if t.id == ticket_id:
            ticket_to_update = t
            ticket_index = i
            break

    if not ticket_to_update:
        return None

    updated = False
    # Updated valid_fields: removed requester_email, added assignee_user_id
    valid_fields = ['title', 'description', 'type', 'status', 'priority', 'assignee_user_id']

    # Store original values of fields relevant for notifications *before* any updates
    original_ticket_data_for_notification = {
        'status': ticket_to_update.status,
        'assignee_user_id': ticket_to_update.assignee_user_id # Added for assignee notifications
    }

    try:
        for key, value in kwargs.items():
            if key in valid_fields:
                # Before setting attribute, capture original value if it's a field we notify on
                # (already done above for status, could be done for assignee_user_id here if needed for complex logic)

                # Validate common string fields for type and non-emptiness (if not None for optional fields)
                if key in ['title', 'description']:
                    if not isinstance(value, str):
                        raise ValueError(f"{key.capitalize()} must be a string.")
                    if not value: # title and description cannot be empty
                        raise ValueError(f"{key.capitalize()} cannot be empty.")
                elif key == 'assignee_user_id':
                    if value is not None and not isinstance(value, str): # Can be None or a non-empty string
                        raise ValueError(f"{key.capitalize()} must be a string or None.")
                    if isinstance(value, str) and not value: # if string, cannot be empty
                         raise ValueError(f"{key.capitalize()} cannot be an empty string if provided; use None to clear.")

                # Validate specific choices for type, status, priority
                if key == 'type': # type is not optional, must be string
                    if not isinstance(value, str) or value not in ('IT', 'Facilities'):
                        raise ValueError("Type must be a string and 'IT' or 'Facilities'.")
                elif key == 'status':
                    if not isinstance(value, str) or value not in ('Open', 'In Progress', 'Closed'):
                        raise ValueError("Status must be a string and 'Open', 'In Progress', or 'Closed'.")
                elif key == 'priority':
                    if not isinstance(value, str) or value not in ('Low', 'Medium', 'High'):
                        raise ValueError("Priority must be a string and 'Low', 'Medium', or 'High'.")

                setattr(ticket_to_update, key, value)
                updated = True
            # else:
                # Optionally, handle unknown keys in kwargs, e.g., raise ValueError or log a warning
                # print(f"Warning: Unknown field '{key}' in update_ticket.")

    except ValueError: # Catch any ValueError raised by the checks above
        raise # Re-raise to be handled by the CLI

    if updated:
        ticket_to_update.updated_at = datetime.now(timezone.utc)
        tickets[ticket_index] = ticket_to_update # Update the ticket in the list

        # After all attributes are updated and timestamp is set, check for notifications
        # 1. Status Change Notification
        if 'status' in kwargs and ticket_to_update.status != original_ticket_data_for_notification.get('status'):
            try:
                message = (
                    f"Ticket '{ticket_to_update.title}' (ID: {ticket_to_update.id[:8]}) "
                    f"status changed from '{original_ticket_data_for_notification['status']}' "
                    f"to '{ticket_to_update.status}'."
                )
                if ticket_to_update.requester_user_id:
                    create_notification(
                        user_id=ticket_to_update.requester_user_id,
                        message=message,
                        ticket_id=ticket_to_update.id
                    )
                else:
                    print(f"Warning: Ticket {ticket_to_update.id} has no requester_user_id. Cannot send status update notification.")
            except Exception as e:
                print(f"Error creating status update notification for ticket {ticket_to_update.id}: {e}")

        # New: Assignment Change Notification
        new_assignee_id = ticket_to_update.assignee_user_id
        old_assignee_id = original_ticket_data_for_notification.get('assignee_user_id')

        if 'assignee_user_id' in kwargs and new_assignee_id != old_assignee_id:
            ticket_title_short = ticket_to_update.title[:30] + "..." if len(ticket_to_update.title) > 30 else ticket_to_update.title
            ticket_ref = f"'{ticket_title_short}' (ID: {ticket_to_update.id[:8]})"

            # 1. Notify New Assignee
            if new_assignee_id: # If there's a new assignee
                try:
                    message_for_new_assignee = f"You have been assigned Ticket {ticket_ref}."
                    create_notification(
                        user_id=new_assignee_id,
                        message=message_for_new_assignee,
                        ticket_id=ticket_to_update.id
                    )
                except Exception as e:
                    print(f"Error creating new assignee notification for ticket {ticket_to_update.id}: {e}")

            # 2. Notify Old Assignee (if they existed and are different from new one)
            if old_assignee_id and old_assignee_id != new_assignee_id:
                try:
                    message_for_old_assignee = f"You have been unassigned from Ticket {ticket_ref}."
                    create_notification(
                        user_id=old_assignee_id,
                        message=message_for_old_assignee,
                        ticket_id=ticket_to_update.id
                    )
                except Exception as e:
                    print(f"Error creating old assignee notification for ticket {ticket_to_update.id}: {e}")

            # 3. Notify Requester about assignment change (unless they are the new assignee or old assignee to avoid duplicate if they were self-assigned then unassigned)
            # Check if requester is not the new assignee AND requester is not the old assignee (in case of self-unassignment)
            # More simply: notify if requester is not involved in the assignment change as an assignee themselves.
            notify_requester_of_assignment_change = True
            if ticket_to_update.requester_user_id == new_assignee_id:
                 notify_requester_of_assignment_change = False
            # If old_assignee_id was the requester and it's now unassigned, they already know implicitly or might get the "unassigned from you" notification if that's implemented.
            # The main goal is to inform the requester if someone *else* is now handling their ticket, or if it's now unassigned from someone else.

            if ticket_to_update.requester_user_id and notify_requester_of_assignment_change :
                 # Avoid notifying requester if they are the old assignee and the ticket is now unassigned (they'd get the "unassigned from you" notification if that was for them)
                if not (ticket_to_update.requester_user_id == old_assignee_id and new_assignee_id is None):
                    try:
                        if new_assignee_id:
                            message_for_requester = f"Your Ticket {ticket_ref} has been assigned to a technician."
                        else: # Ticket became unassigned from someone else
                            message_for_requester = f"Your Ticket {ticket_ref} is now unassigned."
                        create_notification(
                            user_id=ticket_to_update.requester_user_id,
                            message=message_for_requester,
                            ticket_id=ticket_to_update.id
                        )
                    except Exception as e:
                        print(f"Error creating requester assignment notification for ticket {ticket_to_update.id}: {e}")

        _save_tickets(tickets) # Save after all processing including notifications

    return ticket_to_update

def list_tickets(filters: Optional[Dict[str, Any]] = None) -> List[Ticket]:
    """
    Loads tickets.
    If filters is provided, filters the tickets based on the key-value pairs.
    Returns the list of (filtered) Ticket objects.
    """
    tickets = _load_tickets()
    if not filters:
        return tickets

    filtered_tickets = []
    for ticket in tickets:
        match = True
        for key, value in filters.items():
            if not hasattr(ticket, key) or getattr(ticket, key) != value:
                match = False
                break
        if match:
            filtered_tickets.append(ticket)
    return filtered_tickets


def add_comment_to_ticket(ticket_id: str, user_id: str, comment_text: str) -> Optional[Ticket]:
    """Adds a comment to a ticket and saves it."""
    if not comment_text.strip():
        raise ValueError("Comment text cannot be empty.")
    if not user_id.strip(): # Basic check for user_id
        raise ValueError("User ID for comment cannot be empty.")

    tickets = _load_tickets()
    ticket_to_update = None
    ticket_index = -1

    for i, t in enumerate(tickets):
        if t.id == ticket_id:
            ticket_to_update = t
            ticket_index = i
            break

    if not ticket_to_update:
        return None # Ticket not found

    try:
        # The Ticket.add_comment method handles creating the comment dictionary,
        # appending it, and updating its own updated_at timestamp.
        ticket_to_update.add_comment(user_id=user_id, text=comment_text)
    except ValueError as ve: # Catch validation errors from Ticket.add_comment
        raise ve
    except Exception as e:
        # This might catch unexpected errors within Ticket.add_comment
        print(f"Error calling Ticket.add_comment method for ticket {ticket_id}: {e}")
        raise ValueError(f"Failed to add comment object to ticket: {e}")


    # Replace the old ticket object with the updated one in the list
    tickets[ticket_index] = ticket_to_update

    try:
        _save_tickets(tickets)
    except Exception as e:
        # Handle saving error. _save_tickets should ideally have its own robust error handling.
        print(f"Error saving tickets after adding comment to ticket {ticket_id}: {e}")
        # If save fails, the in-memory update happened but isn't persisted.
        # Depending on desired atomicity, this might warrant more complex error handling or rollback.
        # For now, returning None indicates the overall operation did not reliably complete.
        return None

    # Potentially create a notification for the new comment
    # This is similar to status change notifications and might be desired.
    # For example, notify the requester or assignee (if different from commenter).
    try:
        if ticket_to_update.requester_user_id != user_id: # Don't notify if commenter is the requester
            message = (
                f"Ticket '{ticket_to_update.title}' (ID: {ticket_to_update.id[:8]}) "
                f"has a new comment from user {user_id}."
            )
            if ticket_to_update.requester_user_id: # Check if requester_user_id exists
                create_notification(
                    user_id=ticket_to_update.requester_user_id,
                    message=message,
                    ticket_id=ticket_to_update.id
                )
        # Also notify assignee if they are not the commenter and not the requester (to avoid double notification if requester is assignee)
        if ticket_to_update.assignee_user_id and \
           ticket_to_update.assignee_user_id != user_id and \
           ticket_to_update.assignee_user_id != ticket_to_update.requester_user_id:
            message_assignee = (
                f"Ticket '{ticket_to_update.title}' (ID: {ticket_to_update.id[:8]}), assigned to you, "
                f"has a new comment from user {user_id}."
            )
            create_notification(
                user_id=ticket_to_update.assignee_user_id,
                message=message_assignee,
                ticket_id=ticket_to_update.id
            )
    except Exception as e:
        print(f"Error creating new comment notification for ticket {ticket_id}: {e}")
        # Continue, as comment was already added and saved. Notification is secondary here.

    return ticket_to_update
