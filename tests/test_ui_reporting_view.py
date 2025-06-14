import unittest
from unittest.mock import patch, MagicMock, call # Added call
import sys
import os
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Any, Dict # Added Dict, Any
from collections import Counter

# Adjust path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import User, Ticket
from ui_reporting_view import ReportingView # The class to test

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QLabel, QComboBox, QDateEdit, QTextEdit, QMessageBox # For MagicMock spec

# Helper to create dummy tickets
def _create_dummy_ticket(
    status: str, created_at: datetime, ticket_type: str = "IT",
    requester_user_id: Optional[str] = "req_uid",
    title: str = "Test Ticket", ticket_id: str = "dummy_id",
    created_by_user_id: str = "creator_uid", priority: str = "Medium"
) -> Ticket:
    # Ensure created_at is timezone-aware if it's not already
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return Ticket(
        id=ticket_id, title=title, description="Dummy desc", type=ticket_type,
        status=status, priority=priority, requester_user_id=requester_user_id,
        created_by_user_id=created_by_user_id, created_at=created_at,
        updated_at=created_at # For simplicity, updated_at = created_at
    )

class DummyUserForReportingTest(User):
    def __init__(self, username: str, role: User.ROLES, user_id_val: str = "test_report_uid"): # type: ignore
        if User.ROLES is None or not hasattr(User.ROLES, '__args__') or role not in User.ROLES.__args__: # type: ignore
            class TempRoles: __args__ = ('EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager')
            User.ROLES = TempRoles #type: ignore
            if role not in User.ROLES.__args__: # type: ignore
                raise ValueError(f"Invalid role '{role}'. Must be one of {User.ROLES.__args__}") # type: ignore
        self.user_id = user_id_val; self.username = username; self.role: User.ROLES = role # type: ignore
        self._password_hash: Optional[str] = None
    def set_password(self, password): self._password_hash = f"dummy_{password}"
    def check_password(self, password): return self._password_hash == f"dummy_{password}"


class TestReportingViewLogic(unittest.TestCase):
    @patch('ui_reporting_view.QApplication.instance') # Avoids "QApplication instance not found"
    def setUp(self, mock_qapp_instance): # mock_qapp_instance is unused but required by patch
        # Ensure User.ROLES is populated
        if User.ROLES is None:
            class TempRoles: __args__ = ('EngManager', 'TechManager', 'EndUser') # Ensure EngManager is valid
            User.ROLES = TempRoles #type: ignore

        self.dummy_user = DummyUserForReportingTest("reporter", "EngManager")

        # Since ReportingView's __init__ creates QWidgets, we need to be careful.
        # We can patch away the QWidget part of the inheritance for logic tests,
        # or mock the specific UI elements it tries to create/access.
        # For this test, we'll mock the UI elements that _display_report_data and handle_generate_report use.
        with patch.object(ReportingView, 'setLayout', MagicMock()): # Prevent actual layouting
             self.reporting_view = ReportingView(current_user=self.dummy_user)

        self.reporting_view.report_type_combo = MagicMock(spec=QComboBox)
        self.reporting_view.start_date_edit = MagicMock(spec=QDateEdit)
        self.reporting_view.end_date_edit = MagicMock(spec=QDateEdit)
        self.reporting_view.report_display_area = MagicMock(spec=QTextEdit)

    def test_generate_status_report(self):
        mock_tickets = [
            _create_dummy_ticket(status="Open", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Open", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Closed", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="In Progress", created_at=datetime.now(timezone.utc)),
        ]
        report_str = self.reporting_view._generate_status_report(mock_tickets)
        self.assertIn("Ticket Volume by Status:", report_str)
        self.assertIn("  - Open: 2\n", report_str)
        self.assertIn("  - Closed: 1\n", report_str)
        self.assertIn("  - In Progress: 1\n", report_str)

    def test_generate_type_report(self):
        mock_tickets = [
            _create_dummy_ticket(status="Open", ticket_type="IT", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Open", ticket_type="IT", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Closed", ticket_type="Facilities", created_at=datetime.now(timezone.utc)),
        ]
        report_str = self.reporting_view._generate_type_report(mock_tickets)
        self.assertIn("Ticket Volume by Type (Department):", report_str)
        self.assertIn("  - IT: 2\n", report_str)
        self.assertIn("  - Facilities: 1\n", report_str)

    def test_generate_user_activity_report(self):
        mock_tickets = [
            _create_dummy_ticket(status="Open", requester_user_id="userA", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Closed", requester_user_id="userB", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Open", requester_user_id="userA", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="In Progress", requester_user_id="userC", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Open", requester_user_id="userA", created_at=datetime.now(timezone.utc)),
            _create_dummy_ticket(status="Open", requester_user_id="userB", created_at=datetime.now(timezone.utc)),
        ]
        report_str = self.reporting_view._generate_user_activity_report(mock_tickets, top_n=2)
        self.assertIn("User Activity (Top 2 Requesters):", report_str)
        self.assertIn(f"  - User ID {('userA')[:8]}...: 3 tickets\n", report_str)
        self.assertIn(f"  - User ID {('userB')[:8]}...: 2 tickets\n", report_str)
        self.assertNotIn("userC", report_str) # Check top_n is applied

    @patch('ui_reporting_view.list_tickets')
    @patch.object(ReportingView, '_generate_status_report', return_value="Status Report Content")
    @patch.object(ReportingView, '_generate_type_report', return_value="Type Report Content")
    @patch.object(ReportingView, '_generate_user_activity_report', return_value="User Activity Report Content")
    def test_handle_generate_report_routing_and_date_filtering(
        self, mock_user_report: MagicMock, mock_type_report: MagicMock,
        mock_status_report: MagicMock, mock_list_tickets: MagicMock
    ):
        today_date = date.today()
        start_date_obj = today_date - timedelta(days=7)

        self.reporting_view.start_date_edit.date.return_value = QDate(start_date_obj.year, start_date_obj.month, start_date_obj.day)
        self.reporting_view.end_date_edit.date.return_value = QDate(today_date.year, today_date.month, today_date.day)

        # Datetimes for ticket creation
        # Note: datetime.combine needs date and time. Using min.time() for start of day.
        dt_in_range = datetime.combine(start_date_obj + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        dt_before_range = datetime.combine(start_date_obj - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        dt_after_range = datetime.combine(today_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc) # This will be outside end_datetime

        ticket_in_range = _create_dummy_ticket(status="Open", created_at=dt_in_range, ticket_id="T_IN")
        ticket_before_range = _create_dummy_ticket(status="Open", created_at=dt_before_range, ticket_id="T_BEFORE")
        ticket_after_range = _create_dummy_ticket(status="Open", created_at=dt_after_range, ticket_id="T_AFTER")

        mock_list_tickets.return_value = [ticket_in_range, ticket_before_range, ticket_after_range]

        # Test Status Report routing
        self.reporting_view.report_type_combo.currentText.return_value = "Ticket Volume by Status"
        self.reporting_view.handle_generate_report()
        mock_status_report.assert_called_once()
        filtered_list_arg = mock_status_report.call_args[0][0]
        self.assertEqual(len(filtered_list_arg), 1)
        self.assertIn(ticket_in_range, filtered_list_arg)
        self.reporting_view.report_display_area.setPlainText.assert_called_with(unittest.mock.string_containing("Status Report Content"))

        # Reset mocks for next test
        mock_list_tickets.reset_mock(); mock_status_report.reset_mock(); mock_type_report.reset_mock(); mock_user_report.reset_mock()
        self.reporting_view.report_display_area.setPlainText.reset_mock()
        mock_list_tickets.return_value = [ticket_in_range, ticket_before_range, ticket_after_range] # Re-assign fixed return value


        # Test Type Report routing
        self.reporting_view.report_type_combo.currentText.return_value = "Ticket Volume by Type"
        self.reporting_view.handle_generate_report()
        mock_type_report.assert_called_once()
        filtered_list_arg_type = mock_type_report.call_args[0][0]
        self.assertEqual(len(filtered_list_arg_type), 1)
        self.assertIn(ticket_in_range, filtered_list_arg_type)
        self.reporting_view.report_display_area.setPlainText.assert_called_with(unittest.mock.string_containing("Type Report Content"))

        mock_list_tickets.reset_mock(); mock_status_report.reset_mock(); mock_type_report.reset_mock(); mock_user_report.reset_mock()
        self.reporting_view.report_display_area.setPlainText.reset_mock()
        mock_list_tickets.return_value = [ticket_in_range, ticket_before_range, ticket_after_range]

        # Test User Activity Report routing
        self.reporting_view.report_type_combo.currentText.return_value = "User Activity (Top Requesters)"
        self.reporting_view.handle_generate_report()
        mock_user_report.assert_called_once()
        filtered_list_arg_user = mock_user_report.call_args[0][0]
        self.assertEqual(len(filtered_list_arg_user), 1)
        self.assertIn(ticket_in_range, filtered_list_arg_user)
        self.reporting_view.report_display_area.setPlainText.assert_called_with(unittest.mock.string_containing("User Activity Report Content"))

    @patch('ui_reporting_view.QMessageBox.warning') # Patch QMessageBox directly
    def test_handle_generate_report_date_error(self, mock_msg_box: MagicMock):
        today = date.today()
        start_date_obj = today
        end_date_obj = today - timedelta(days=1) # Start date is after end date

        self.reporting_view.start_date_edit.date.return_value = QDate(start_date_obj.year, start_date_obj.month, start_date_obj.day)
        self.reporting_view.end_date_edit.date.return_value = QDate(end_date_obj.year, end_date_obj.month, end_date_obj.day)

        self.reporting_view.handle_generate_report()
        mock_msg_box.assert_called_once_with(self.reporting_view, "Date Error", "Start date cannot be after end date.")


if __name__ == '__main__':
    unittest.main()
