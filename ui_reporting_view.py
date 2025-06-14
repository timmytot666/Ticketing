import sys
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QComboBox,
    QDateEdit,
    QPushButton,
    QTextEdit,
    QCalendarWidget,
    QApplication,
    QMessageBox # Added
)
from PySide6.QtCore import QDate, Qt, Slot
from PySide6.QtGui import QFont

from typing import Optional, List, Dict, Any # Added List, Dict, Any
from datetime import datetime, date, timedelta, timezone # Added datetime, timedelta, timezone
from collections import Counter # Added Counter

try:
    from models import User, Ticket # Added Ticket
    from ticket_manager import list_tickets # Added list_tickets
except ModuleNotFoundError:
    print("Error: models.py or ticket_manager.py not found. Ensure accessible.", file=sys.stderr)
    class User:
        ROLES = None; user_id: str
        def __init__(self, username: str, role: str, user_id_val: str = "fb_uid", *args, **kwargs):
            self.username=username; self.role=role; self.user_id=user_id_val
    class Ticket: # Basic fallback for type hints
        status: str; type: str; requester_user_id: Optional[str]; created_at: Optional[datetime]
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            if not hasattr(self, 'created_at'): self.created_at = datetime.now(timezone.utc)
    def list_tickets() -> List[Ticket]: return []


class ReportingView(QWidget):
    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user

        self.setWindowTitle("Generate Reports")
        main_layout = QVBoxLayout(self)

        controls_layout = QGridLayout(); controls_layout.setSpacing(10)
        controls_layout.addWidget(QLabel("Report Type:"), 0, 0)
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems([
            "Ticket Volume by Status", "Ticket Volume by Type", "User Activity (Top Requesters)"
        ])
        controls_layout.addWidget(self.report_type_combo, 0, 1, 1, 3)
        controls_layout.addWidget(QLabel("Start Date:"), 1, 0)
        self.start_date_edit = QDateEdit(QDate.currentDate().addMonths(-1))
        self.start_date_edit.setCalendarPopup(True); self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        controls_layout.addWidget(self.start_date_edit, 1, 1)
        controls_layout.addWidget(QLabel("End Date:"), 1, 2)
        self.end_date_edit = QDateEdit(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True); self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        controls_layout.addWidget(self.end_date_edit, 1, 3)
        self.generate_report_button = QPushButton("Generate Report")
        self.generate_report_button.clicked.connect(self.handle_generate_report) # Connected
        controls_layout.addWidget(self.generate_report_button, 2, 0, 1, 4, alignment=Qt.AlignCenter)
        main_layout.addLayout(controls_layout); main_layout.addSpacing(10)

        report_display_title = QLabel("Report Output:")
        title_font = QFont(); title_font.setBold(True); title_font.setPointSize(12)
        report_display_title.setFont(title_font)
        main_layout.addWidget(report_display_title)
        self.report_display_area = QTextEdit()
        self.report_display_area.setReadOnly(True); self.report_display_area.setFontFamily("Monospace")
        self.report_display_area.setLineWrapMode(QTextEdit.NoWrap)
        main_layout.addWidget(self.report_display_area, 1)
        self.setLayout(main_layout)

    @Slot()
    def handle_generate_report(self):
        report_type = self.report_type_combo.currentText()
        # Convert QDate to datetime.date
        start_date_obj: date = self.start_date_edit.date().toPython()
        end_date_obj: date = self.end_date_edit.date().toPython()

        if start_date_obj > end_date_obj:
            QMessageBox.warning(self, "Date Error", "Start date cannot be after end date.")
            return

        report_content = f"Report Type: {report_type}\n"
        report_content += f"Date Range: {start_date_obj.isoformat()} to {end_date_obj.isoformat()}\n\n"

        try:
            all_tickets: List[Ticket] = list_tickets()

            start_datetime = datetime(start_date_obj.year, start_date_obj.month, start_date_obj.day, 0, 0, 0, tzinfo=timezone.utc)
            end_datetime = datetime(end_date_obj.year, end_date_obj.month, end_date_obj.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

            filtered_tickets = [
                t for t in all_tickets
                if hasattr(t, 'created_at') and t.created_at and
                   (start_datetime <= (t.created_at.astimezone(timezone.utc) if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc)) <= end_datetime)
            ]

            if not filtered_tickets:
                report_content += "No tickets found in the selected date range for the criteria."
                self._display_report_data(report_content)
                return

            if report_type == "Ticket Volume by Status":
                report_content += self._generate_status_report(filtered_tickets)
            elif report_type == "Ticket Volume by Type":
                report_content += self._generate_type_report(filtered_tickets)
            elif report_type == "User Activity (Top Requesters)":
                report_content += self._generate_user_activity_report(filtered_tickets)
            else:
                report_content += "Selected report type is not implemented yet."

        except Exception as e:
            report_content += f"Error generating report: {e}"
            print(f"Report generation error: {e}", file=sys.stderr) # Keep console log for dev
            QMessageBox.critical(self, "Report Error", f"Could not generate report: {e}")

        self._display_report_data(report_content)

    def _generate_status_report(self, tickets: List[Ticket]) -> str:
        status_counts = Counter(getattr(t, 'status', 'N/A') for t in tickets) # Use getattr for safety
        content = "Ticket Volume by Status:\n"
        if not status_counts: content += "  No tickets with status information.\n"
        for status, count in sorted(status_counts.items()):
            content += f"  - {status}: {count}\n"
        return content

    def _generate_type_report(self, tickets: List[Ticket]) -> str:
        type_counts = Counter(getattr(t, 'type', 'N/A') for t in tickets) # Use getattr
        content = "Ticket Volume by Type (Department):\n"
        if not type_counts: content += "  No tickets with type information.\n"
        for ticket_type, count in sorted(type_counts.items()):
            content += f"  - {ticket_type}: {count}\n"
        return content

    def _generate_user_activity_report(self, tickets: List[Ticket], top_n=5) -> str:
        # Ensure requester_user_id exists and is not None before counting
        requester_ids = [getattr(t, 'requester_user_id', None) for t in tickets]
        valid_requester_ids = [uid for uid in requester_ids if uid]
        requester_counts = Counter(valid_requester_ids)

        content = f"User Activity (Top {top_n} Requesters):\n"
        if not requester_counts: content += "  No user activity found (no tickets with requester IDs).\n"
        for user_id, count in requester_counts.most_common(top_n):
            content += f"  - User ID {str(user_id)[:8]}...: {count} tickets\n"
        return content

    def _display_report_data(self, report_content: str):
        self.report_display_area.setPlainText(report_content)


if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    try:
        from models import User, Ticket
        from ticket_manager import list_tickets # For mocking
    except: pass

    app = QApplication(sys.argv)

    class DummyUserForReporting(User):
        def __init__(self, username="report_user", role="EngManager", user_id_val="report_uid_001"):
            self.username = username; self.role = role # type: ignore
            self.user_id = user_id_val
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempRoles: __args__ = ('EngManager', 'EndUser')
                 User.ROLES = TempRoles; self.ROLES = TempRoles # type: ignore
        def set_password(self,p):pass; def check_password(self,p):return False

    test_user = DummyUserForReporting()

    # Mock ticket_manager.list_tickets for direct testing
    _original_list_tickets = ticket_manager.list_tickets
    def mock_list_tickets_for_reports():
        print("MOCK: list_tickets() called for reports")
        # Create dummy Ticket objects with necessary attributes for reports
        now = datetime.now(timezone.utc)
        return [
            Ticket(status='Open', type='IT', requester_user_id='userA', created_at=now - timedelta(days=1)),
            Ticket(status='Open', type='IT', requester_user_id='userB', created_at=now - timedelta(days=2)),
            Ticket(status='In Progress', type='Facilities', requester_user_id='userA', created_at=now - timedelta(days=3)),
            Ticket(status='Closed', type='IT', requester_user_id='userC', created_at=now - timedelta(days=4)),
            Ticket(status='Open', type='Facilities', requester_user_id='userB', created_at=now - timedelta(days=5)),
             # Add a ticket outside default date range to test filtering
            Ticket(status='Open', type='IT', requester_user_id='userA', created_at=now - timedelta(days=40)),
        ]
    ticket_manager.list_tickets = mock_list_tickets_for_reports

    reporting_view = ReportingView(current_user=test_user)
    reporting_view.show()

    exit_code = app.exec()
    ticket_manager.list_tickets = _original_list_tickets # Restore
    sys.exit(exit_code)
