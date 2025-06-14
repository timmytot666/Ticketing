import argparse
from typing import Dict, Any, Optional

from models import Ticket
from ticket_manager import (
    create_ticket,
    get_ticket,
    update_ticket,
    list_tickets,
)

def print_ticket_details(ticket: Ticket) -> None:
    """Prints the details of a ticket in a readable format."""
    print(f"Ticket ID: {ticket.id}")
    print(f"  Title: {ticket.title}")
    print(f"  Description: {ticket.description}")
    print(f"  Type: {ticket.type}")
    print(f"  Status: {ticket.status}")
    print(f"  Priority: {ticket.priority}")
    print(f"  Requester: {ticket.requester_email}")
    print(f"  Created At: {ticket.created_at.isoformat()}")
    print(f"  Updated At: {ticket.updated_at.isoformat()}")

def handle_create(args: argparse.Namespace) -> None:
    """Handles the 'create' command."""
    try:
        ticket = create_ticket(
            title=args.title,
            description=args.description,
            type=args.type,
            requester_email=args.requester_email,
            priority=args.priority,
        )
        print(f"Ticket created successfully with ID: {ticket.id}")
        print_ticket_details(ticket)
    except ValueError as e:
        print(f"Error creating ticket: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def handle_view(args: argparse.Namespace) -> None:
    """Handles the 'view' command."""
    ticket = get_ticket(args.ticket_id)
    if ticket:
        print_ticket_details(ticket)
    else:
        print(f"Error: Ticket with ID '{args.ticket_id}' not found.")

def handle_list(args: argparse.Namespace) -> None:
    """Handles the 'list' command."""
    filters: Dict[str, Any] = {}
    if args.status:
        filters['status'] = args.status
    if args.type:
        filters['type'] = args.type
    if args.priority:
        filters['priority'] = args.priority

    tickets = list_tickets(filters=filters if filters else None)
    if tickets:
        print(f"Found {len(tickets)} ticket(s):")
        for ticket in tickets:
            print(
                f"- ID: {ticket.id}, Title: {ticket.title}, Type: {ticket.type}, "
                f"Status: {ticket.status}, Priority: {ticket.priority}"
            )
    else:
        print("No tickets found matching your criteria.")

def handle_update(args: argparse.Namespace) -> None:
    """Handles the 'update' command."""
    update_args: Dict[str, Any] = {}
    if args.title is not None:
        update_args['title'] = args.title
    if args.description is not None:
        update_args['description'] = args.description
    if args.type is not None:
        update_args['type'] = args.type
    if args.status is not None:
        update_args['status'] = args.status
    if args.priority is not None:
        update_args['priority'] = args.priority

    if not update_args:
        print("Error: At least one field to update must be provided (--title, --description, --type, --status, --priority).")
        return

    try:
        ticket = update_ticket(args.ticket_id, **update_args)
        if ticket:
            print(f"Ticket ID '{args.ticket_id}' updated successfully.")
            print_ticket_details(ticket)
        else:
            # update_ticket might return None if ticket_id not found OR if validation failed (already printed by update_ticket)
            # We check if it was a not found error specifically.
            if get_ticket(args.ticket_id) is None: # Check if ticket originally existed
                 print(f"Error: Ticket with ID '{args.ticket_id}' not found.")
            # If it existed, the error message from update_ticket (ValueError) would have been printed already
    except ValueError as e: # This might be redundant if update_ticket prints and returns None
        print(f"Error updating ticket '{args.ticket_id}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def main():
    parser = argparse.ArgumentParser(description="Simple Ticketing System CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new ticket")
    create_parser.add_argument("--title", required=True, help="Title of the ticket")
    create_parser.add_argument("--description", required=True, help="Description of the ticket")
    create_parser.add_argument(
        "--type", required=True, choices=['IT', 'Facilities'], help="Type of the ticket"
    )
    create_parser.add_argument(
        "--requester_email", required=True, help="Email of the requester"
    )
    create_parser.add_argument(
        "--priority", default='Medium', choices=['Low', 'Medium', 'High'], help="Priority of the ticket"
    )
    create_parser.set_defaults(func=handle_create)

    # View command
    view_parser = subparsers.add_parser("view", help="View details of a specific ticket")
    view_parser.add_argument("ticket_id", help="ID of the ticket to view")
    view_parser.set_defaults(func=handle_view)

    # List command
    list_parser = subparsers.add_parser("list", help="List tickets, optionally filtered")
    list_parser.add_argument(
        "--status", choices=['Open', 'In Progress', 'Closed'], help="Filter by status"
    )
    list_parser.add_argument(
        "--type", choices=['IT', 'Facilities'], help="Filter by type"
    )
    list_parser.add_argument(
        "--priority", choices=['Low', 'Medium', 'High'], help="Filter by priority"
    )
    list_parser.set_defaults(func=handle_list)

    # Update command
    update_parser = subparsers.add_parser("update", help="Update an existing ticket")
    update_parser.add_argument("ticket_id", help="ID of the ticket to update")
    update_parser.add_argument("--title", help="New title for the ticket")
    update_parser.add_argument("--description", help="New description for the ticket")
    update_parser.add_argument(
        "--type", choices=['IT', 'Facilities'], help="New type for the ticket"
    )
    update_parser.add_argument(
        "--status", choices=['Open', 'In Progress', 'Closed'], help="New status for the ticket"
    )
    update_parser.add_argument(
        "--priority", choices=['Low', 'Medium', 'High'], help="New priority for the ticket"
    )
    update_parser.set_defaults(func=handle_update)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
