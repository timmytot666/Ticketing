import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from models import Ticket

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
    requester_email: str,
    priority: str = 'Medium'
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
    if not requester_email or not isinstance(requester_email, str):
        raise ValueError("Requester email is required and must be a non-empty string.")
    if "@" not in requester_email: # Basic email check
        raise ValueError("Requester email must contain an '@' symbol.")

    tickets = _load_tickets()
    try:
        # Ticket class __init__ will perform its own validation
        # (e.g., specific choices for type, status, priority, and re-validates non-empty, email format)
        new_ticket = Ticket(
            title=title,
            description=description,
            type=type,
            requester_email=requester_email,
            priority=priority
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
    valid_fields = ['title', 'description', 'type', 'status', 'priority', 'requester_email']

    try:
        for key, value in kwargs.items():
            if key in valid_fields: # No need for hasattr check if we trust valid_fields
                # Validate common string fields for type and non-emptiness
                if key in ['title', 'description', 'requester_email']:
                    if not isinstance(value, str):
                        raise ValueError(f"{key.capitalize()} must be a string.")
                    if not value: # Check for empty string
                        raise ValueError(f"{key.capitalize()} cannot be empty.")
                    if key == 'requester_email' and "@" not in value:
                        raise ValueError("Requester email must contain an '@' symbol.")

                # Validate specific choices for type, status, priority
                elif key == 'type':
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
        tickets[ticket_index] = ticket_to_update
        _save_tickets(tickets)

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
