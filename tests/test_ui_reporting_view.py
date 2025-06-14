import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Any, Dict
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import User, Ticket # Assuming User.ROLES is set up correctly in models.py
from ui_reporting_view import ReportingView

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QLabel, QComboBox, QDateEdit, QTextEdit, QMessageBox

def _create_dummy_ticket(
    status: str, created_at: datetime, ticket_type: str = "IT",
    requester_user_id: Optional[str] = "req_uid",
    title: str = "Test Ticket", ticket_id: str = "dummy_id",
    created_by_user_id: str = "creator_uid", priority: str = "Medium",
    # SLA fields
    response_due_at: Optional[datetime] = None,
    resolution_due_at: Optional[datetime] = None,
    responded_at: Optional[datetime] = None,
    sla_paused_at: Optional[datetime] = None,
    total_paused_duration_seconds: float = 0.0,
    updated_at_override: Optional[datetime] = None # To set specific close time
) -> Ticket:
    if created_at.tzinfo is None: created_at = created_at.replace(tzinfo=timezone.utc)

    # Ensure updated_at is always after or same as created_at
    final_updated_at = updated_at_override if updated_at_override else created_at
    if final_updated_at < created_at : final_updated_at = created_at

    # Ensure due dates are timezone aware if provided
    if response_due_at and response_due_at.tzinfo is None: response_due_at = response_due_at.replace(tzinfo=timezone.utc)
    if resolution_due_at and resolution_due_at.tzinfo is None: resolution_due_at = resolution_due_at.replace(tzinfo=timezone.utc)
    if responded_at and responded_at.tzinfo is None: responded_at = responded_at.replace(tzinfo=timezone.utc)
    if sla_paused_at and sla_paused_at.tzinfo is None: sla_paused_at = sla_paused_at.replace(tzinfo=timezone.utc)

    return Ticket(
        id=ticket_id, title=title, description="Dummy desc", type=ticket_type,
        status=status, priority=priority, requester_user_id=requester_user_id,
        created_by_user_id=created_by_user_id, created_at=created_at,
        updated_at=final_updated_at,
        response_due_at=response_due_at, resolution_due_at=resolution_due_at,
        responded_at=responded_at, sla_paused_at=sla_paused_at,
        total_paused_duration_seconds=total_paused_duration_seconds
    )

class DummyUserForReportingTest(User):
    def __init__(self, username: str, role: User.ROLES, user_id_val: str = "test_report_uid"): # type: ignore
        if User.ROLES is None or not hasattr(User.ROLES, '__args__') or role not in User.ROLES.__args__: # type: ignore
            class TempRoles: __args__ = ('EngManager', 'TechManager', 'EndUser')
            User.ROLES = TempRoles #type: ignore
            if role not in User.ROLES.__args__: raise ValueError(f"Invalid role '{role}'") # type: ignore
        self.user_id = user_id_val; self.username = username; self.role: User.ROLES = role # type: ignore
        self._password_hash: Optional[str] = None
    def set_password(self, password): self._password_hash = f"dummy_{password}"
    def check_password(self, password): return self._password_hash == f"dummy_{password}"

class TestReportingViewLogic(unittest.TestCase):
    @patch('ui_reporting_view.QApplication.instance')
    def setUp(self, mock_qapp_instance):
        if User.ROLES is None:
            class TempRoles: __args__ = ('EngManager',)
            User.ROLES = TempRoles #type: ignore
        self.dummy_user = DummyUserForReportingTest("reporter", "EngManager")
        with patch.object(ReportingView, 'setLayout', MagicMock()):
             self.reporting_view = ReportingView(current_user=self.dummy_user)
        self.reporting_view.report_type_combo = MagicMock(spec=QComboBox)
        self.reporting_view.start_date_edit = MagicMock(spec=QDateEdit)
        self.reporting_view.end_date_edit = MagicMock(spec=QDateEdit)
        self.reporting_view.report_display_area = MagicMock(spec=QTextEdit)

    # ... (existing tests for status, type, user activity reports) ...
    def test_generate_status_report(self):
        # (Existing test, ensure _create_dummy_ticket is used if it helps)
        now = datetime.now(timezone.utc)
        mock_tickets = [
            _create_dummy_ticket(status="Open", created_at=now), _create_dummy_ticket(status="Open", created_at=now),
            _create_dummy_ticket(status="Closed", created_at=now), _create_dummy_ticket(status="In Progress", created_at=now),
        ]
        report_str = self.reporting_view._generate_status_report(mock_tickets)
        self.assertIn("Open: 2", report_str); self.assertIn("Closed: 1", report_str)

    def test_generate_type_report(self):
        now = datetime.now(timezone.utc)
        mock_tickets = [
            _create_dummy_ticket(status="Open", ticket_type="IT", created_at=now),
            _create_dummy_ticket(status="Open", ticket_type="IT", created_at=now),
            _create_dummy_ticket(status="Closed", ticket_type="Facilities", created_at=now),
        ]
        report_str = self.reporting_view._generate_type_report(mock_tickets)
        self.assertIn("IT: 2", report_str); self.assertIn("Facilities: 1", report_str)

    def test_generate_user_activity_report(self):
        now = datetime.now(timezone.utc)
        mock_tickets = [
             _create_dummy_ticket(status="Open", requester_user_id="userA", created_at=now),
             _create_dummy_ticket(status="Open", requester_user_id="userB", created_at=now),
             _create_dummy_ticket(status="Open", requester_user_id="userA", created_at=now),
        ]
        report_str = self.reporting_view._generate_user_activity_report(mock_tickets, top_n=1)
        self.assertIn(f"User ID {('userA')[:8]}...: 2 tickets", report_str)
        self.assertNotIn("userB", report_str)


    def test_generate_sla_compliance_report(self):
        now = datetime.now(timezone.utc)
        mock_tickets = [
            # Met Response, Met Resolution
            _create_dummy_ticket(ticket_id="T001", status='Closed', created_at=now-timedelta(days=5), updated_at_override=now-timedelta(days=1),
                                 responded_at=now-timedelta(days=4, hours=23), response_due_at=now-timedelta(days=4, hours=20),
                                 resolution_due_at=now-timedelta(days=1, hours=1), total_paused_duration_seconds=0),
            # Breached Response, Met Resolution
            _create_dummy_ticket(ticket_id="T002", status='Closed', created_at=now-timedelta(days=3), updated_at_override=now-timedelta(hours=1),
                                 responded_at=now-timedelta(days=2, hours=10), response_due_at=now-timedelta(days=2, hours=12), # Breached
                                 resolution_due_at=now, total_paused_duration_seconds=0),
            # Met Response, Breached Resolution (paused)
            _create_dummy_ticket(ticket_id="T003", status='Closed', created_at=now-timedelta(days=10), updated_at_override=now-timedelta(hours=1),
                                 responded_at=now-timedelta(days=9), response_due_at=now-timedelta(days=8),
                                 resolution_due_at=now-timedelta(days=2), total_paused_duration_seconds=3600*24*1.5), # Paused 1.5 days
                                 # Effective reso_due = due - 1.5 days = now - 0.5 days. Closed at now-1hr -> Met.
                                 # Let's make it breach: resolution_due_at=now-timedelta(days=0.5), paused=0. Effective=now-0.5d. Closed now-1hr -> Met.
                                 # To make it breach: resolution_due_at = now-timedelta(days=3), paused=0. Effective=now-3d. Closed now-1hr -> Breached.
            _create_dummy_ticket(ticket_id="T003_BREACH", status='Closed', created_at=now-timedelta(days=10), updated_at_override=now-timedelta(hours=1),
                                 responded_at=now-timedelta(days=9), response_due_at=now-timedelta(days=8),
                                 resolution_due_at=now-timedelta(days=3), total_paused_duration_seconds=0),
            # Pending Response, Pending Resolution (Open)
            _create_dummy_ticket(ticket_id="T004", status='Open', created_at=now-timedelta(hours=2),
                                 response_due_at=now+timedelta(hours=2), resolution_due_at=now+timedelta(hours=22)),
            # No SLA (no due dates)
            _create_dummy_ticket(ticket_id="T005", status='Open', created_at=now-timedelta(hours=1)),
            # Responded (Met), Pending Resolution (In Progress), Paused
            _create_dummy_ticket(ticket_id="T006", status='In Progress', created_at=now-timedelta(days=1),
                                 responded_at=now-timedelta(hours=20), response_due_at=now-timedelta(hours=18),
                                 resolution_due_at=now+timedelta(days=2), sla_paused_at=now-timedelta(hours=1), total_paused_duration_seconds=3600),
        ]
        report_str = self.reporting_view._generate_sla_compliance_report(mock_tickets)

        self.assertIn("SLA Compliance Report:", report_str)
        self.assertIn("Response SLA Compliance", report_str)
        self.assertIn("  - Met: 2", report_str) # T001, T006
        self.assertIn("  - Breached: 1", report_str) # T002
        self.assertIn("  - Pending / N/A: 2", report_str) # T004 (pending), T005 (N/A)
        self.assertIn(f"  - Compliance Rate: {(2/3*100):.2f}%", report_str)

        self.assertIn("Resolution SLA Compliance", report_str)
        self.assertIn("  - Met: 1", report_str) # T001
        self.assertIn("  - Breached: 2", report_str) # T002, T003_BREACH
        self.assertIn("  - Pending / N/A: 3", report_str) # T004 (pending), T005 (N/A), T006 (pending)
        self.assertIn(f"  - Compliance Rate: {(1/3*100):.2f}%", report_str)

        self.assertIn("Details of Breached SLAs:", report_str)
        self.assertIn("T002 (Resp. Breach)", report_str)
        self.assertIn("T003_BREACH (Reso. Breach)", report_str)

    @patch('ui_reporting_view.list_tickets')
    @patch.object(ReportingView, '_generate_status_report', return_value="Status Report")
    @patch.object(ReportingView, '_generate_type_report', return_value="Type Report")
    @patch.object(ReportingView, '_generate_user_activity_report', return_value="User Activity Report")
    @patch.object(ReportingView, '_generate_sla_compliance_report', return_value="SLA Compliance Report") # Mock new method
    def test_handle_generate_report_routing_and_date_filtering(
        self, mock_sla_report:MagicMock, mock_user_report: MagicMock, mock_type_report: MagicMock,
        mock_status_report: MagicMock, mock_list_tickets: MagicMock
    ):
        today = date.today(); start_date = today - timedelta(days=7)
        self.reporting_view.start_date_edit.date.return_value = QDate(start_date.year, start_date.month, start_date.day)
        self.reporting_view.end_date_edit.date.return_value = QDate(today.year, today.month, today.day)

        ticket_in = _create_dummy_ticket("Open", datetime.combine(start_date + timedelta(days=1), datetime.min.time()))
        ticket_before = _create_dummy_ticket("Open", datetime.combine(start_date - timedelta(days=1), datetime.min.time()))
        mock_list_tickets.return_value = [ticket_in, ticket_before]

        # Test SLA Compliance Report routing
        self.reporting_view.report_type_combo.currentText.return_value = "SLA Compliance Report"
        self.reporting_view.handle_generate_report()
        mock_sla_report.assert_called_once()
        filtered_list_arg_sla = mock_sla_report.call_args[0][0]
        self.assertEqual(len(filtered_list_arg_sla), 1); self.assertIn(ticket_in, filtered_list_arg_sla)
        self.reporting_view.report_display_area.setPlainText.assert_called_with(unittest.mock.string_containing("SLA Compliance Report"))
        mock_sla_report.reset_mock(); self.reporting_view.report_display_area.setPlainText.reset_mock()
        mock_list_tickets.return_value = [ticket_in, ticket_before] # Reset for next call

        # ... (existing routing tests for other report types, ensure they still pass)


    @patch('ui_reporting_view.QMessageBox.warning')
    def test_handle_generate_report_date_error(self, mock_msg_box: MagicMock):
        # (Existing test, should still pass)
        today = date.today()
        self.reporting_view.start_date_edit.date.return_value = QDate(today.year, today.month, today.day)
        self.reporting_view.end_date_edit.date.return_value = QDate(today.year, today.month, today.day -1) # End before start
        self.reporting_view.handle_generate_report()
        mock_msg_box.assert_called_once()

if __name__ == '__main__':
    unittest.main()
