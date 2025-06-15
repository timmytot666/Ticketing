import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QComboBox, QLabel,
    QApplication, QMessageBox
)
from PySide6.QtCore import Slot, Qt, Signal
from PySide6.QtGui import QFont, QColor, QShowEvent # Moved QShowEvent

from datetime import datetime, timedelta, timezone # Added timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple # Added Tuple

try:
    from models import User, Ticket
    from ticket_manager import list_tickets
except ModuleNotFoundError:
    print("Error: Critical modules (models, ticket_manager) not found.", file=sys.stderr)
    class User: user_id: str = "fallback_user"
    class Ticket:
        id: str; title: str; requester_user_id: str; type: str; status: str; priority: str;
        assignee_user_id: Optional[str]; updated_at: Optional[datetime]; response_due_at: Optional[datetime];
        resolution_due_at: Optional[datetime]; responded_at: Optional[datetime]; sla_paused_at: Optional[datetime]
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            if not hasattr(self, 'updated_at'): self.updated_at = datetime.now(timezone.utc)
    def list_tickets(filters=None) -> list: return []

class AllTicketsView(QWidget):
    ticket_selected = Signal(str)

    # Column definitions
    COLUMN_ID = 0
    COLUMN_TITLE = 1
    COLUMN_REQUESTER_ID = 2
    COLUMN_TYPE = 3
    COLUMN_STATUS = 4
    COLUMN_PRIORITY = 5
    COLUMN_ASSIGNEE_ID = 6
    COLUMN_RESPONSE_DUE = 7 # New
    COLUMN_RESOLUTION_DUE = 8 # New
    COLUMN_SLA_STATUS = 9 # New
    COLUMN_LAST_UPDATED = 10 # Shifted

    DATE_FORMAT = "%Y-%m-%d %H:%M" # Shortened format for table

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.setWindowTitle("All Tickets")
        main_layout = QVBoxLayout(self)

        # Filter Area (remains largely the same)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Status:")); self.status_filter_combo = QComboBox(); self.status_filter_combo.addItems(["All", "Open", "In Progress", "On Hold", "Closed"]); filter_layout.addWidget(self.status_filter_combo)
        filter_layout.addWidget(QLabel("Type:")); self.type_filter_combo = QComboBox(); self.type_filter_combo.addItems(["All", "IT", "Facilities"]); filter_layout.addWidget(self.type_filter_combo)
        filter_layout.addWidget(QLabel("Priority:")); self.priority_filter_combo = QComboBox(); self.priority_filter_combo.addItems(["All", "Low", "Medium", "High"]); filter_layout.addWidget(self.priority_filter_combo)
        filter_layout.addStretch()
        self.apply_filters_button = QPushButton("Apply Filters"); self.apply_filters_button.clicked.connect(self.apply_filters); filter_layout.addWidget(self.apply_filters_button)
        self.refresh_button = QPushButton("Refresh List"); self.refresh_button.clicked.connect(self.load_and_display_tickets); filter_layout.addWidget(self.refresh_button)
        main_layout.addLayout(filter_layout)

        # Tickets Table - Updated columns
        self.tickets_table = QTableWidget()
        self.tickets_table.setColumnCount(11) # Increased column count
        self.tickets_table.setHorizontalHeaderLabels([
            "ID", "Title", "Requester", "Type", "Status", "Priority",
            "Assigned", "Response Due", "Resolve Due", "SLA Status", "Last Updated"
        ])
        self.tickets_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tickets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tickets_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tickets_table.verticalHeader().setVisible(False)

        self.tickets_table.horizontalHeader().setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.Stretch)
        for col in [self.COLUMN_ID, self.COLUMN_REQUESTER_ID, self.COLUMN_TYPE, self.COLUMN_STATUS,
                    self.COLUMN_PRIORITY, self.COLUMN_ASSIGNEE_ID, self.COLUMN_RESPONSE_DUE,
                    self.COLUMN_RESOLUTION_DUE, self.COLUMN_SLA_STATUS, self.COLUMN_LAST_UPDATED]:
            self.tickets_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.tickets_table.itemDoubleClicked.connect(self.handle_ticket_double_clicked)
        main_layout.addWidget(self.tickets_table)
        self.setLayout(main_layout)

    def _get_ticket_sla_summary_and_color(self, ticket: Ticket, now: datetime) -> Tuple[str, Optional[QColor]]:
        if not hasattr(ticket, 'status'): return "N/A", None # Guard for fallback Ticket

        sla_color: Optional[QColor] = None

        if getattr(ticket, 'sla_paused_at', None):
            return "Paused", QColor("lightgray")

        response_status_str = "Resp: N/A"
        responded_at = getattr(ticket, 'responded_at', None)
        response_due_at = getattr(ticket, 'response_due_at', None)

        if responded_at:
            response_status_str = "Responded"
            if response_due_at and responded_at > response_due_at:
                response_status_str += " (Late)"
                sla_color = QColor("#FFC0CB") # Light Pink for late response
        elif response_due_at:
            if now > response_due_at:
                response_status_str = "Resp: OVERDUE"
                sla_color = QColor("#FF6347") # Tomato Red for overdue
            else:
                response_status_str = "Resp: Pending"
                if (response_due_at - now) < timedelta(hours=1): # Example: Nearing breach if <1h left
                     if sla_color is None: sla_color = QColor("#FFFFE0") # Light Yellow

        resolution_status_str = "Reso: N/A"
        resolution_due_at = getattr(ticket, 'resolution_due_at', None)
        ticket_status = ticket.status
        ticket_updated_at = getattr(ticket, 'updated_at', None)

        if ticket_status == 'Closed':
            resolution_status_str = "Resolved"
            if resolution_due_at and ticket_updated_at and ticket_updated_at > resolution_due_at:
                resolution_status_str += " (Late)"
                if sla_color is None or sla_color not in [QColor("#FF6347")]: # Don't override stronger color
                    sla_color = QColor("#FFC0CB") # Light Pink for late resolution
        elif resolution_due_at:
            if now > resolution_due_at:
                resolution_status_str = "Reso: OVERDUE"
                sla_color = QColor("#FF6347") # Tomato Red, highest precedence
            else:
                resolution_status_str = "Reso: Pending"
                if (resolution_due_at - now) < timedelta(hours=4): # Example: Nearing breach if <4h left
                    if sla_color is None: sla_color = QColor("#FFFFE0") # Light Yellow

        summary_status = f"{response_status_str} | {resolution_status_str}"
        return summary_status, sla_color

    def _populate_table(self, filters: Optional[Dict[str, Any]] = None):
        self.tickets_table.setRowCount(0)
        try:
            effective_filters = filters if filters else {}
            tickets: List[Ticket] = list_tickets(filters=effective_filters)
        except Exception as e:
            print(f"Error fetching tickets: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"Could not load tickets: {e}")
            return

        if tickets: tickets.sort(key=lambda t: getattr(t, 'updated_at', datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

        self.tickets_table.setRowCount(len(tickets))
        now = datetime.now(timezone.utc) # Get current time once for all rows

        for row_num, ticket in enumerate(tickets):
            items: List[QTableWidgetItem] = []

            id_item = QTableWidgetItem(ticket.id); id_item.setData(Qt.UserRole, ticket.id); items.append(id_item)
            items.append(QTableWidgetItem(getattr(ticket, 'title', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'requester_user_id', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'type', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'status', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'priority', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'assignee_user_id', None) or "N/A"))

            response_due = getattr(ticket, 'response_due_at', None)
            items.append(QTableWidgetItem(response_due.strftime(self.DATE_FORMAT) if response_due else "N/A"))

            resolution_due = getattr(ticket, 'resolution_due_at', None)
            items.append(QTableWidgetItem(resolution_due.strftime(self.DATE_FORMAT) if resolution_due else "N/A"))

            sla_summary, sla_color = self._get_ticket_sla_summary_and_color(ticket, now)
            items.append(QTableWidgetItem(sla_summary))

            updated_at = getattr(ticket, 'updated_at', None)
            items.append(QTableWidgetItem(updated_at.strftime(self.DATE_FORMAT) if updated_at else "N/A"))

            for col_num, item in enumerate(items):
                if sla_color: item.setBackground(sla_color)
                self.tickets_table.setItem(row_num, col_num, item)

    # apply_filters, load_and_display_tickets, handle_ticket_double_clicked, showEvent remain same
    @Slot()
    def apply_filters(self): self.load_and_display_tickets(use_filters=True)
    @Slot()
    def load_and_display_tickets(self, use_filters: bool = False):
        filters_dict: Dict[str, Any] = {}
        if use_filters:
            status = self.status_filter_combo.currentText(); ticket_type = self.type_filter_combo.currentText(); priority = self.priority_filter_combo.currentText()
            if status != "All": filters_dict['status'] = status
            if ticket_type != "All": filters_dict['type'] = ticket_type
            if priority != "All": filters_dict['priority'] = priority
        self._populate_table(filters=filters_dict if filters_dict else None)

    @Slot(QTableWidgetItem)
    def handle_ticket_double_clicked(self, item: QTableWidgetItem):
        row = item.row(); id_cell_item = self.tickets_table.item(row, self.COLUMN_ID)
        if id_cell_item: ticket_id = id_cell_item.data(Qt.UserRole)
        if ticket_id: self.ticket_selected.emit(ticket_id); print(f"Ticket {ticket_id} selected.")

    def showEvent(self, event: QShowEvent):
        super().showEvent(event);
        if event.isAccepted(): self.load_and_display_tickets(use_filters=self.status_filter_combo.currentText() != "All" or self.type_filter_combo.currentText() != "All" or self.priority_filter_combo.currentText() != "All")


if __name__ == '__main__':
    # ... (existing __main__ block, ensure Ticket has new SLA fields for mock data)
    import os; from datetime import timedelta, timezone
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from models import User, Ticket; from ticket_manager import list_tickets
    except: pass

    app = QApplication(sys.argv)
    class DummyUserForAllTickets(User):
        def __init__(self, u="viewer", r="Technician", uid="tech_uid"):
            self.username = u
            self.role = r
            self.user_id = uid # type: ignore

        def set_password(self,p):
            pass

        def check_password(self,p):
            return False
    test_user = DummyUserForAllTickets()

    _og_list_tickets = ticket_manager.list_tickets
    def mock_lt(filters=None):
        print(f"MOCK list_tickets called with: {filters}")
        now = datetime.now(timezone.utc)
        all_mock_tickets = [
            Ticket(id="T001", title="SLA OK", requester_user_id="u1", type="IT", status="Open", priority="High", assignee_user_id="tech1", updated_at=now-timedelta(hours=1), response_due_at=now+timedelta(hours=3), resolution_due_at=now+timedelta(hours=23)),
            Ticket(id="T002", title="SLA Resp Late", requester_user_id="u2", type="Facilities", status="Open", priority="Medium", assignee_user_id="tech2", updated_at=now-timedelta(hours=10), responded_at=now-timedelta(hours=1), response_due_at=now-timedelta(hours=2), resolution_due_at=now+timedelta(hours=100)),
            Ticket(id="T003", title="SLA Reso Overdue", requester_user_id="u3", type="IT", status="In Progress", priority="Low", assignee_user_id=None, updated_at=now-timedelta(days=6), response_due_at=now-timedelta(days=5, hours=20), responded_at=now-timedelta(days=5, hours=22), resolution_due_at=now-timedelta(hours=1)),
            Ticket(id="T004", title="SLA Paused", requester_user_id="u1", type="Facilities", status="On Hold", priority="High", assignee_user_id="tech1", updated_at=now-timedelta(days=2), sla_paused_at=now-timedelta(hours=2)),
            Ticket(id="T005", title="SLA Resolved Late", requester_user_id="u4", type="IT", status="Closed", priority="Medium", assignee_user_id="tech2", updated_at=now-timedelta(hours=1), response_due_at=now-timedelta(days=2, hours=4), responded_at=now-timedelta(days=2, hours=3), resolution_due_at=now-timedelta(days=1))
        ]
        if not filters: return all_mock_tickets
        ft = all_mock_tickets
        if 'status' in filters: ft = [t for t in ft if t.status == filters['status']]
        if 'type' in filters: ft = [t for t in ft if t.type == filters['type']]
        if 'priority' in filters: ft = [t for t in ft if t.priority == filters['priority']]
        return ft
    ticket_manager.list_tickets = mock_lt

    view = AllTicketsView(current_user=test_user)
    view.ticket_selected.connect(lambda tid: QMessageBox.information(view, "Selected", tid))
    view.show()
    app.exec()
    ticket_manager.list_tickets = _og_list_tickets
