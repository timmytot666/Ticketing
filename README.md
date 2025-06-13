# Command-Line Ticketing System

## Overview

This is a simple command-line ticketing system designed to manage IT and Facilities support tickets. Users can create, view, list, and update tickets through a CLI interface. Ticket data is persisted in a JSON file.

## Features

*   **Create Tickets:** Generate new tickets with a title, description, type, requester email, and priority.
*   **View Tickets:** Display detailed information for a specific ticket by its ID.
*   **List Tickets:** Show all tickets or filter them by status, type, or priority.
*   **Update Tickets:** Modify existing tickets' attributes such as title, description, type, status, or priority.
*   **Ticket Types:** Supports two distinct types of tickets: 'IT' and 'Facilities'.
*   **Priority Management:** Assign 'Low', 'Medium', or 'High' priority to tickets.
*   **Status Tracking:** Tickets can be 'Open', 'In Progress', or 'Closed'.
*   **Data Persistence:** Ticket information is saved locally in a `tickets.json` file.

## File Structure

The project is organized into the following key files and directories:

*   `ticketing_cli.py`: The main entry point for the command-line interface. It parses arguments and calls the appropriate functions.
*   `ticket_manager.py`: Contains the core business logic for managing tickets, including creation, retrieval, updates, and filtering.
*   `models.py`: Defines the `Ticket` class, which represents the data structure for a single ticket.
*   `tickets.json`: The JSON file where all ticket data is stored. This file is automatically created and updated.
*   `tests/`: This directory holds all the unit tests for the system.
    *   `test_models.py`: Unit tests for the `Ticket` model.
    *   `test_ticket_manager.py`: Unit tests for the ticket management logic.

## Prerequisites

*   Python 3.x

## Setup/Installation

1.  Clone the repository to your local machine:
    ```bash
    # Replace with the actual URL if this were a real Git repo
    git clone <repository_url>
    cd <repository_directory>
    ```
2.  No external package installation is required beyond the standard Python library.

## Usage

All commands are run through `ticketing_cli.py`.

### Create a New Ticket

To create a new ticket, use the `create` command with the required arguments:

```bash
python ticketing_cli.py create --title "Network Outage" --description "The main office network is down." --type "IT" --requester_email "user@example.com" --priority "High"
```

**Arguments for `create`:**

*   `--title` (required): The title of the ticket.
*   `--description` (required): A detailed description of the issue.
*   `--type` (required): The type of ticket. Choices: `IT`, `Facilities`.
*   `--requester_email` (required): The email address of the person requesting assistance.
*   `--priority` (optional): The priority of the ticket. Choices: `Low`, `Medium`, `High`. Defaults to `Medium`.

### View a Ticket

To view the details of a specific ticket, use the `view` command followed by the ticket ID:

```bash
python ticketing_cli.py view <ticket_id>
```
Replace `<ticket_id>` with the actual ID of the ticket you want to view (e.g., `a1b2c3d4e5f67890a1b2c3d4e5f67890`).

### List Tickets

To list tickets, use the `list` command. You can list all tickets or apply filters.

*   **List all tickets:**
    ```bash
    python ticketing_cli.py list
    ```

*   **List tickets with filters:**
    You can filter by `--status`, `--type`, or `--priority`.
    ```bash
    python ticketing_cli.py list --status "Open"
    ```
    ```bash
    python ticketing_cli.py list --type "Facilities"
    ```
    ```bash
    python ticketing_cli.py list --priority "High"
    ```
    Filters can also be combined:
    ```bash
    python ticketing_cli.py list --type "IT" --status "Open" --priority "Medium"
    ```

### Update a Ticket

To update an existing ticket, use the `update` command followed by the ticket ID and the fields you want to change. At least one field to update must be provided.

```bash
python ticketing_cli.py update <ticket_id> --status "In Progress" --priority "High"
```
```bash
python ticketing_cli.py update <ticket_id> --title "Updated: Network Connectivity Issues" --description "The network outage seems to be intermittent."
```

**Optional arguments for `update`:**

*   `--title <new_title>`
*   `--description <new_description>`
*   `--type <new_type>` (Choices: `IT`, `Facilities`)
*   `--status <new_status>` (Choices: `Open`, `In Progress`, `Closed`)
*   `--priority <new_priority>` (Choices: `Low`, `Medium`, `High`)

## Running Tests

To run the automated unit tests, navigate to the project's root directory and execute:

```bash
python -m unittest discover tests
```

This command will discover and run all test cases defined in the `tests/` directory.