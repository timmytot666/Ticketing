# Advanced GUI Ticketing System

## Overview

This is a desktop application built with Python and PySide6 for managing IT and Facilities support tickets. It features a rich user interface with role-based access control, enabling different levels of interaction and functionality depending on the logged-in user. The system persists data using local JSON files.

## User Roles & Capabilities

The system defines several user roles, each with specific capabilities:

*   **EndUser:**
    *   Submit new support tickets.
    *   View and track the status of their own submitted tickets.
    *   Receive in-app notifications for updates to their tickets (e.g., status changes, new comments, assignments).
    *   View their notification inbox.
*   **Technician/Engineer:**
    *   View a comprehensive list of all tickets or filter to see tickets assigned to them.
    *   Access detailed views of individual tickets.
    *   Update ticket details, including status, priority, and assignment.
    *   Add comments and view the history of a ticket.
    *   Receive in-app notifications, particularly for new assignments or updates to tickets they are involved with.
    *   View their notification inbox.
*   **TechManager/EngManager:**
    *   All capabilities of Technicians/Engineers.
    *   Access to a dashboard providing an overview of ticket statistics and visualizations (e.g., ticket status distribution).
    *   Access to a reporting system to generate reports on ticket volumes, types, and user activity.
    *   View their notification inbox.

## Features

*   **User Authentication:** Secure user login and role-based access control determining UI and feature availability.
*   **Ticket Management:**
    *   **Creation:** Users can create new tickets, providing title, description, type (IT/Facilities), and priority.
    *   **Viewing:**
        *   EndUsers can view a list of their own submitted tickets (`MyTicketsView`).
        *   Technicians and Managers can view a filterable list of all tickets (`AllTicketsView`).
        *   A detailed view (`TicketDetailView`) shows all information for a selected ticket, including its comment history.
    *   **Updating:** Authorized users can update a ticket's status, priority, type, title, description, and assignee.
    *   **Commenting:** Users can add comments to tickets, which are displayed chronologically in the ticket detail view.
*   **Notification System:**
    *   **In-App Inbox (`InboxView`):** Users can view a list of notifications related to their activity or assignments.
    *   **Status Bar Indicator:** The main window displays a count of unread notifications.
    *   **Automated Notifications:** Generated for significant ticket events:
        *   Status changes on a ticket (notifies requester).
        *   New ticket assignments (notifies new assignee, old assignee, and requester).
        *   New comments on a ticket (notifies requester and current assignee, if different from commenter).
*   **Manager Dashboard (`DashboardView`):**
    *   Displays key metrics: counts of Open, In Progress, On Hold, and Resolved Today tickets.
    *   Includes a pie chart visualizing the distribution of active ticket statuses (Open, In Progress, On Hold).
*   **Reporting System (`ReportingView`):**
    *   Generate text-based reports for:
        *   Ticket Volume by Status
        *   Ticket Volume by Type
        *   User Activity (Top Requesters)
    *   Filter reports by a selectable date range (based on ticket creation date).
*   **Data Persistence:** User accounts, tickets, and notifications are stored in local JSON files (`users.json`, `tickets.json`, `notifications.json`).

## File Structure

Key files and directories in the project:

*   `main_gui.py`: Main entry point to launch the PySide6 GUI application.
*   `ui_login.py`: Defines the `LoginWindow` class for user authentication.
*   `ui_main_window.py`: Defines the `MainWindow` class, the main application shell which hosts other views.
*   **UI Views (`ui_*.py`):**
    *   `ui_create_ticket_view.py`: View for creating new tickets.
    *   `ui_my_tickets_view.py`: View for EndUsers to see their submitted tickets.
    *   `ui_all_tickets_view.py`: View for Technicians/Managers to see all tickets with filtering.
    *   `ui_ticket_detail_view.py`: View for displaying and editing details of a single ticket, including comments.
    *   `ui_inbox_view.py`: View for displaying user notifications.
    *   `ui_dashboard_view.py`: View for displaying ticket metrics and charts for Managers.
    *   `ui_reporting_view.py`: View for generating and displaying reports for Managers.
*   **Backend Logic & Data Models:**
    *   `models.py`: Defines data structures (`Ticket`, `User`, `Notification`).
    *   `ticket_manager.py`: Business logic for ticket operations and data persistence.
    *   `user_manager.py`: Business logic for user authentication and data persistence.
    *   `notification_manager.py`: Business logic for notification management and data persistence.
*   **Data Files (`*.json`):**
    *   `tickets.json`: Stores ticket data.
    *   `users.json`: Stores user accounts (including hashed passwords).
    *   `notifications.json`: Stores notification data.
*   **Dependencies:**
    *   `requirements.txt`: Lists project dependencies (PySide6, Werkzeug, matplotlib).
*   **Tests:**
    *   `tests/`: Directory containing unit tests for backend logic and non-GUI aspects of UI components.

## Prerequisites

*   Python 3.x (preferably 3.8 or newer for some typing features).
*   Dependencies as listed in `requirements.txt`.

## Setup & Installation

1.  **Clone the Repository:**
    ```bash
    # Replace with the actual repository URL if applicable
    # git clone <repository_url>
    # cd <repository_directory_name>
    ```
    (If downloaded as a ZIP, extract it and navigate to the project root directory).

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install Dependencies:**
    Navigate to the project root directory (where `requirements.txt` is located) and run:
    ```bash
    pip install -r requirements.txt
    ```

### Creating the First Administrator Account

If you are setting up the system for the first time, or if the `users.json` file is empty or does not have an administrator account, you can create an initial admin user using the provided script. This script helps ensure you have an administrative user to begin managing the system.

1.  **Run the script from the project root directory:**
    Make sure your virtual environment is activated (if you created one) and you are in the project's root directory.
    ```bash
    python create_initial_admin.py
    ```

2.  **Script Action:**
    *   The script will attempt to create an administrator account. By default, it uses:
        *   **Username:** `admin`
        *   **Password:** `password`
        *   **Role:** `TechManager` (This role typically has high privileges, including user management capabilities).
    *   If a user with the username `admin` already exists, the script will inform you and will not perform any action to avoid duplication.
    *   If the specified admin role (e.g., `TechManager`) is not valid as per `models.User.ROLES`, the script will print an error and exit.

3.  **Important - Password Reset:**
    *   The script creates this initial admin user with the `force_password_reset=True` flag.
    *   This means the administrator **will be required to change this default password immediately upon their first login** through the application's login screen. This is a security measure to ensure the default password is not retained.

After creating the admin user, you can proceed to the "Usage" section below to run the main application.

## Usage

1.  Ensure you are in the project's root directory and your virtual environment (if used) is activated.
2.  Run the application using:
    ```bash
    python main_gui.py
    ```
3.  Log in with a user account.
    *   *(Note: User creation is currently handled by manually editing `users.json` or via direct calls to `user_manager.create_user()`. For initial setup, you might need to create a user this way. Ensure passwords set via `user.set_password()` are properly hashed by Werkzeug.)*
    *   Example roles defined in `models.User.ROLES`: `EndUser`, `Technician`, `Engineer`, `TechManager`, `EngManager`.

## Running Tests

To run the automated unit tests, navigate to the project's root directory and execute:

```bash
python -m unittest discover tests
```
This command will automatically find and run all test cases within the `tests/` directory.