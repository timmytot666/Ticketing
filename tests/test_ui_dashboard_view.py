import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional

# Adjust path to import from parent directory if necessary
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import User, Ticket # Assuming User.ROLES is set up correctly in models.py
from ui_dashboard_view import DashboardView

# PySide6 imports for type checking if needed, but mostly for MagicMock spec
from PySide6.QtWidgets import QLabel

# Helper to create dummy tickets with required fields for testing
def _create_dummy_ticket(
    status: str,
    updated_at: datetime,
    title: str = "Test Ticket",
    ticket_id: str = "dummy_id",
    requester_user_id: str = "req_uid",
    created_by_user_id: str = "creator_uid",
    ticket_type: str = "IT", # 'type' is a reserved keyword, so use ticket_type for param
    priority: str = "Medium"
) -> Ticket:
    return Ticket(
        id=ticket_id, # Pass id directly if Ticket model allows it, else it's auto-generated
        title=title,
        description="Dummy description",
        type=ticket_type,
        status=status,
        priority=priority,
        requester_user_id=requester_user_id,
        created_by_user_id=created_by_user_id,
        # assignee_user_id can be None by default in Ticket model
        # comments will be [] by default
        created_at=updated_at - timedelta(days=1), # Ensure created_at is before updated_at
        updated_at=updated_at
    )


class DummyUserForDashboardTest(User):
    def __init__(self, username: str, role: User.ROLES, user_id_val: str = "test_dash_uid"): # type: ignore
        # Simplified init, assumes User.ROLES is available from the imported models.User
        if User.ROLES is None or not hasattr(User.ROLES, '__args__') or role not in User.ROLES.__args__: # type: ignore
             # Define a simple ROLES if models.User fallback was used and ROLES is None
            class TempRoles: __args__ = ('EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager')
            User.ROLES = TempRoles #type: ignore
            if role not in User.ROLES.__args__: # type: ignore
                raise ValueError(f"Invalid role '{role}' for DummyUser. Must be one of {User.ROLES.__args__}") # type: ignore

        self.user_id = user_id_val
        self.username = username
        self.role: User.ROLES = role # type: ignore
        self._password_hash: Optional[str] = None # Not needed for these tests

    def set_password(self, password): self._password_hash = f"dummy_{password}"
    def check_password(self, password): return self._password_hash == f"dummy_{password}"


class TestDashboardViewLogic(unittest.TestCase):

    @patch('ui_dashboard_view.FigureCanvas', MagicMock()) # Mock canvas to avoid GUI requirements
    @patch('ui_dashboard_view.Figure', MagicMock())       # Mock figure
    def setUp(self):
        # Ensure User.ROLES is populated for DummyUserForDashboardTest
        if User.ROLES is None:
            class TempRoles: __args__ = ('EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager')
            User.ROLES = TempRoles #type: ignore

        self.dummy_user = DummyUserForDashboardTest("manager", "TechManager")

        # We need to prevent MainWindow's __init__ from running fully if it requires QApplication
        # However, DashboardView itself is a QWidget, and its __init__ does QWidget things.
        # For pure logic tests of _update_metrics_display, we can isolate it.
        # But since DashboardView creates QLabels, it's safer to have a QApplication instance for tests.
        # This is a common pattern if not using a dedicated Qt test runner.
        # app = QApplication.instance() # Get existing instance
        # if not app: app = QApplication(sys.argv) # Create if does not exist
        # self.app = app

        # To test _update_metrics_display, we need an instance of DashboardView
        # Its __init__ creates QLabels. We will mock these QLabels.
        with patch.object(DashboardView, 'setLayout', MagicMock()): # Prevent actual layouting
            self.dashboard_view = DashboardView(current_user=self.dummy_user)

        # Mock the UI labels that _update_metrics_display tries to set text on
        self.dashboard_view.open_tickets_label = MagicMock(spec=QLabel)
        self.dashboard_view.in_progress_tickets_label = MagicMock(spec=QLabel)
        self.dashboard_view.resolved_today_label = MagicMock(spec=QLabel)
        self.dashboard_view.on_hold_tickets_label = MagicMock(spec=QLabel)


    @patch('ui_dashboard_view.list_tickets')
    def test_update_metrics_display_counts_and_labels(self, mock_list_tickets: MagicMock):
        today = date.today()
        yesterday = today - timedelta(days=1)

        mock_tickets = [
            _create_dummy_ticket(status="Open", updated_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Open", updated_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="In Progress", updated_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="On Hold", updated_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Closed", updated_at=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)),
            _create_dummy_ticket(status="Closed", updated_at=datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)),
            _create_dummy_ticket(status="Closed", updated_at=datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc))
        ]
        mock_list_tickets.return_value = mock_tickets

        self.dashboard_view._update_metrics_display()

        self.dashboard_view.open_tickets_label.setText.assert_called_with("Open Tickets: 2")
        self.dashboard_view.in_progress_tickets_label.setText.assert_called_with("In Progress Tickets: 1")
        self.dashboard_view.on_hold_tickets_label.setText.assert_called_with("On Hold Tickets: 1")
        self.dashboard_view.resolved_today_label.setText.assert_called_with("Resolved Today: 2")

        # Assert internal counts for pie chart data (active statuses)
        self.assertEqual(self.dashboard_view.active_status_counts.get('Open', 0), 2)
        self.assertEqual(self.dashboard_view.active_status_counts.get('In Progress', 0), 1)
        self.assertEqual(self.dashboard_view.active_status_counts.get('On Hold', 0), 1)

        # Assert general status counts (includes all closed)
        self.assertEqual(self.dashboard_view.status_counts.get('Closed', 0), 3)


    @patch('ui_dashboard_view.list_tickets')
    def test_update_metrics_display_no_tickets(self, mock_list_tickets: MagicMock):
        mock_list_tickets.return_value = []
        self.dashboard_view._update_metrics_display()

        self.dashboard_view.open_tickets_label.setText.assert_called_with("Open Tickets: 0")
        self.dashboard_view.in_progress_tickets_label.setText.assert_called_with("In Progress Tickets: 0")
        self.dashboard_view.on_hold_tickets_label.setText.assert_called_with("On Hold Tickets: 0")
        self.dashboard_view.resolved_today_label.setText.assert_called_with("Resolved Today: 0")

        self.assertEqual(self.dashboard_view.active_status_counts.get('Open', 0), 0)
        self.assertEqual(self.dashboard_view.status_counts.get('Closed', 0), 0)


    @patch('ui_dashboard_view.list_tickets')
    def test_update_metrics_display_handles_fetch_error(self, mock_list_tickets: MagicMock):
        mock_list_tickets.side_effect = Exception("Database connection error")

        # Patch builtins.print to check stderr output for the error message
        with patch('builtins.print') as mock_print:
            self.dashboard_view._update_metrics_display()

        self.dashboard_view.open_tickets_label.setText.assert_called_with("Open Tickets: Error")
        self.dashboard_view.in_progress_tickets_label.setText.assert_called_with("In Progress Tickets: Error")
        self.dashboard_view.on_hold_tickets_label.setText.assert_called_with("On Hold Tickets: Error")
        self.dashboard_view.resolved_today_label.setText.assert_called_with("Resolved Today: Error")

        self.assertEqual(self.dashboard_view.status_counts, {}) # Should be cleared or empty

        # Check if the error was printed
        printed_error = False
        for call_args in mock_print.call_args_list:
            if "Error fetching tickets for dashboard: Database connection error" in call_args[0][0]:
                printed_error = True
                break
        self.assertTrue(printed_error, "Error message for ticket fetching failure was not printed to stderr.")

if __name__ == '__main__':
    # Ensure QApplication instance exists for QWidget-based tests if DashboardView constructor needs it.
    # However, by mocking FigureCanvas and Figure, and QLabels, we might avoid it.
    # Let's try without explicit QApplication init here for pure logic tests.
    unittest.main()
