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
    QMessageBox
)
from PySide6.QtCore import QDate, Qt, Slot
from PySide6.QtGui import QFont

from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta, timezone # Ensure timedelta is here
from collections import Counter

try:
    from models import User, Ticket
    from ticket_manager import list_tickets
except ModuleNotFoundError:
    print("Error: models.py or ticket_manager.py not found. Ensure accessible.", file=sys.stderr)
    class User:
        ROLES = None; user_id: str
        def __init__(self, username: str, role: str, user_id_val: str = "fb_uid", *args, **kwargs):
            self.username=username; self.role=role; self.user_id=user_id_val
    class Ticket: # Fallback with all necessary fields for SLA report
        status: str; type: str; requester_user_id: Optional[str]; created_at: Optional[datetime]
        id: str = "fallback_id"; title: str = "Fallback Ticket"
        response_due_at: Optional[datetime] = None; resolution_due_at: Optional[datetime] = None
        responded_at: Optional[datetime] = None; sla_paused_at: Optional[datetime] = None
        total_paused_duration_seconds: float = 0.0; updated_at: Optional[datetime] = None
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            if not hasattr(self, 'created_at') or self.created_at is None: self.created_at = datetime.now(timezone.utc)
            if not hasattr(self, 'updated_at') or self.updated_at is None: self.updated_at = self.created_at
            if not hasattr(self, 'total_paused_duration_seconds'): self.total_paused_duration_seconds = 0.0

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
            "Ticket Volume by Status",
            "Ticket Volume by Type",
            "User Activity (Top Requesters)",
            "SLA Compliance Report" # Added new report type
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
        self.generate_report_button.clicked.connect(self.handle_generate_report)
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

            # Date filtering based on ticket creation date for general reports
            # For SLA Compliance, we might want to filter differently (e.g., tickets closed or due in range)
            # For now, using created_at for all reports as per current structure.
            filtered_tickets_by_creation = [
                t for t in all_tickets
                if hasattr(t, 'created_at') and t.created_at and
                   (start_datetime <= (t.created_at.astimezone(timezone.utc) if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc)) <= end_datetime)
            ]

            # For SLA compliance, it's often more relevant to consider tickets *resolved* or *due* within the range.
            # However, the prompt implies using the already `filtered_tickets` (by creation date).
            # We will proceed with `filtered_tickets_by_creation` for the SLA report as well for this iteration.
            # A more advanced implementation might allow choosing the date field for filtering.

            if not filtered_tickets_by_creation and report_type != "SLA Compliance Report": # SLA report has its own no tickets message
                report_content += "No tickets found in the selected date range for the criteria."
                self._display_report_data(report_content)
                return

            if report_type == "Ticket Volume by Status":
                report_content += self._generate_status_report(filtered_tickets_by_creation)
            elif report_type == "Ticket Volume by Type":
                report_content += self._generate_type_report(filtered_tickets_by_creation)
            elif report_type == "User Activity (Top Requesters)":
                report_content += self._generate_user_activity_report(filtered_tickets_by_creation)
            elif report_type == "SLA Compliance Report": # New condition
                report_content += self._generate_sla_compliance_report(filtered_tickets_by_creation)
            else:
                report_content += "Selected report type is not implemented yet."

        except Exception as e:
            report_content += f"Error generating report: {e}"
            print(f"Report generation error: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Report Error", f"Could not generate report: {e}")

        self._display_report_data(report_content)

    def _generate_status_report(self, tickets: List[Ticket]) -> str:
        status_counts = Counter(getattr(t, 'status', 'N/A') for t in tickets)
        content = "Ticket Volume by Status:\n"; hr_line = "-" * 30 + "\n"
        content += hr_line
        if not status_counts: content += "  No tickets with status information.\n"
        for status, count in sorted(status_counts.items()): content += f"  - {status:<15}: {count}\n"
        return content + hr_line

    def _generate_type_report(self, tickets: List[Ticket]) -> str:
        type_counts = Counter(getattr(t, 'type', 'N/A') for t in tickets)
        content = "Ticket Volume by Type (Department):\n"; hr_line = "-" * 40 + "\n"
        content += hr_line
        if not type_counts: content += "  No tickets with type information.\n"
        for ticket_type, count in sorted(type_counts.items()): content += f"  - {ticket_type:<15}: {count}\n"
        return content + hr_line

    def _generate_user_activity_report(self, tickets: List[Ticket], top_n=5) -> str:
        requester_ids = [getattr(t, 'requester_user_id', None) for t in tickets]
        valid_requester_ids = [uid for uid in requester_ids if uid]
        requester_counts = Counter(valid_requester_ids)
        content = f"User Activity (Top {top_n} Requesters):\n"; hr_line = "-" * 40 + "\n"
        content += hr_line
        if not requester_counts: content += "  No user activity found.\n"
        for user_id, count in requester_counts.most_common(top_n):
            content += f"  - User ID {str(user_id)[:8]}...: {count} tickets\n"
        return content + hr_line

    def _generate_sla_compliance_report(self, tickets: List[Ticket]) -> str:
        content = "SLA Compliance Report:\n"; hr_line = "-" * 50 + "\n"
        content += hr_line
        if not tickets:
            content += "  No tickets to analyze in the selected range (based on creation date).\n"
            return content + hr_line

        response_met, response_breached, response_pending_or_na = 0, 0, 0
        resolution_met, resolution_breached, resolution_pending_or_na = 0, 0, 0
        breached_ticket_details: List[str] = []

        for ticket in tickets:
            paused_duration = timedelta(seconds=getattr(ticket, 'total_paused_duration_seconds', 0.0))

            # Response SLA
            if hasattr(ticket, 'response_due_at') and ticket.response_due_at:
                effective_response_due = ticket.response_due_at + paused_duration
                if hasattr(ticket, 'responded_at') and ticket.responded_at:
                    if ticket.responded_at <= effective_response_due: response_met += 1
                    else:
                        response_breached += 1
                        breached_ticket_details.append(
                            f"  - Ticket {ticket.id[:8]} (Resp. Breach): Responded {ticket.responded_at.strftime('%y-%m-%d %H:%M')}, Due {effective_response_due.strftime('%y-%m-%d %H:%M')}")
                else: response_pending_or_na +=1 # Not yet responded
            else: response_pending_or_na += 1 # No response SLA

            # Resolution SLA
            if hasattr(ticket, 'resolution_due_at') and ticket.resolution_due_at:
                effective_resolution_due = ticket.resolution_due_at + paused_duration
                if getattr(ticket, 'status', '') == 'Closed' and hasattr(ticket, 'updated_at') and ticket.updated_at:
                    if ticket.updated_at <= effective_resolution_due: resolution_met += 1
                    else:
                        resolution_breached += 1
                        breached_ticket_details.append(
                            f"  - Ticket {ticket.id[:8]} (Reso. Breach): Closed {ticket.updated_at.strftime('%y-%m-%d %H:%M')}, Due {effective_resolution_due.strftime('%y-%m-%d %H:%M')}")
                else: resolution_pending_or_na +=1 # Not yet resolved
            else: resolution_pending_or_na += 1 # No resolution SLA

        total_resp_slas = response_met + response_breached
        resp_compliance = (response_met / total_resp_slas * 100) if total_resp_slas > 0 else 0
        total_reso_slas = resolution_met + resolution_breached
        reso_compliance = (resolution_met / total_reso_slas * 100) if total_reso_slas > 0 else 0

        content += f"Response SLA Compliance ({total_resp_slas} applicable tickets):\n"
        content += f"  - Met:             {response_met}\n"
        content += f"  - Breached:        {response_breached}\n"
        content += f"  - Pending / N/A:   {response_pending_or_na}\n"
        content += f"  - Compliance Rate: {resp_compliance:.2f}%\n{hr_line}"
        content += f"Resolution SLA Compliance ({total_reso_slas} applicable tickets):\n"
        content += f"  - Met:             {resolution_met}\n"
        content += f"  - Breached:        {resolution_breached}\n"
        content += f"  - Pending / N/A:   {resolution_pending_or_na}\n"
        content += f"  - Compliance Rate: {reso_compliance:.2f}%\n"

        if breached_ticket_details:
            content += f"{hr_line}Details of Breached SLAs (first {len(breached_ticket_details)} shown):\n"
            for detail in breached_ticket_details[:10]: # Limit details shown
                content += detail + "\n"
        content += hr_line
        return content

    def _display_report_data(self, report_content: str):
        self.report_display_area.setPlainText(report_content)

if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from models import User, Ticket; from ticket_manager import list_tickets
    except: pass

    app = QApplication(sys.argv)
    class DummyUserForReporting(User):
        def __init__(self, u="rep_user", r="EngManager", uid="rep_uid"):
            self.username=u; self.role=r; self.user_id=uid # type: ignore
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TR: __args__ = ('EngManager','EndUser'); User.ROLES=TR; self.ROLES=TR #type: ignore
        def set_password(self,p):pass
        def check_password(self,p):return False
    test_user = DummyUserForReporting()

    _og_list_tickets = ticket_manager.list_tickets
    def mock_list_tickets_for_sla_reports():
        print("MOCK: list_tickets() called for SLA reports")
        now = datetime.now(timezone.utc)
        return [
            # Met Response, Met Resolution
            Ticket(id="T001", title="SLA All Met", status='Closed', type='IT', requester_user_id='uA', created_at=now-timedelta(days=5), updated_at=now-timedelta(days=1),
                   responded_at=now-timedelta(days=4, hours=23), response_due_at=now-timedelta(days=4, hours=20),
                   resolution_due_at=now-timedelta(days=1, hours=1), total_paused_duration_seconds=3600*2), # 2hr pause
            # Breached Response, Met Resolution
            Ticket(id="T002", title="SLA Resp Breach", status='Closed', type='Facilities', requester_user_id='uB', created_at=now-timedelta(days=3), updated_at=now-timedelta(hours=1),
                   responded_at=now-timedelta(days=2, hours=10), response_due_at=now-timedelta(days=2, hours=12), # Breached
                   resolution_due_at=now, total_paused_duration_seconds=0),
            # Met Response, Breached Resolution
            Ticket(id="T003", title="SLA Reso Breach", status='Closed', type='IT', requester_user_id='uC', created_at=now-timedelta(days=10), updated_at=now-timedelta(hours=1),
                   responded_at=now-timedelta(days=9), response_due_at=now-timedelta(days=8),
                   resolution_due_at=now-timedelta(days=2), total_paused_duration_seconds=0), # Breached
            # Pending Response, Pending Resolution (Open)
            Ticket(id="T004", title="SLA Pending All", status='Open', type='IT', requester_user_id='uA', created_at=now-timedelta(hours=2),
                   response_due_at=now+timedelta(hours=2), resolution_due_at=now+timedelta(hours=22), total_paused_duration_seconds=0),
            # No SLA (no due dates)
            Ticket(id="T005", title="No SLA", status='Open', type='Facilities', requester_user_id='uD', created_at=now-timedelta(hours=1)),
            # Responded, Pending Resolution (In Progress)
            Ticket(id="T006", title="SLA Resp Met, Reso Pend", status='In Progress', type='IT', requester_user_id='uB', created_at=now-timedelta(days=1),
                   responded_at=now-timedelta(hours=20), response_due_at=now-timedelta(hours=18),
                   resolution_due_at=now+timedelta(days=2), total_paused_duration_seconds=0),
        ]
    ticket_manager.list_tickets = mock_list_tickets_for_sla_reports

    reporting_view = ReportingView(current_user=test_user)
    reporting_view.show()
    exit_code = app.exec()
    ticket_manager.list_tickets = _og_list_tickets
    sys.exit(exit_code)
