import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QMessageBox, QApplication
)
from PySide6.QtCore import Slot, Qt, Signal # Added Signal
from PySide6.QtGui import QColor, QFont, QShowEvent # Moved QShowEvent

from datetime import datetime, timedelta, timezone # Added timedelta, timezone
from typing import Optional, List, Tuple, Dict, Any # Added Tuple, Dict, Any

try:
    from models import User, Ticket
    from ticket_manager import list_tickets
except ModuleNotFoundError:
    print("Error: models.py or ticket_manager.py not found.", file=sys.stderr)
    class User: user_id: str = "fallback_user"
    class Ticket:
        id: str; title: str; type: str; status: str; priority: str; updated_at: Optional[datetime];
        requester_user_id: str; created_by_user_id: str; # For list_tickets filter
        response_due_at: Optional[datetime]; resolution_due_at: Optional[datetime];
        responded_at: Optional[datetime]; sla_paused_at: Optional[datetime]
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            if not hasattr(self, 'updated_at'): self.updated_at = datetime.now(timezone.utc)
    def list_tickets(filters=None) -> list: return []

class MyTicketsView(QWidget):
    open_ticket_requested = Signal(str) # Added signal

    # Column definitions
    COLUMN_ID = 0
    COLUMN_TITLE = 1
    COLUMN_TYPE = 2
    COLUMN_STATUS = 3
    COLUMN_PRIORITY = 4
    COLUMN_RESPONSE_DUE = 5 # New
    COLUMN_RESOLUTION_DUE = 6 # New
    COLUMN_SLA_STATUS = 7 # New
    COLUMN_LAST_UPDATED = 8 # Shifted

    DATE_FORMAT = "%Y-%m-%d %H:%M" # Shortened format for table

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.setWindowTitle("My Tickets") # Changed
        main_layout = QVBoxLayout(self)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.refresh_button = QPushButton("Refresh Tickets")
        self.refresh_button.clicked.connect(self.load_my_tickets_data)
        button_layout.addWidget(self.refresh_button)
        main_layout.addLayout(button_layout)

        self.tickets_table = QTableWidget()
        self.tickets_table.setColumnCount(9) # Increased column count
        self.tickets_table.setHorizontalHeaderLabels([
            "ID", "Title", "Type", "Status", "Priority",
            "Response Due", "Resolve Due", "SLA Status", "Last Updated"
        ])
        self.tickets_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tickets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tickets_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tickets_table.verticalHeader().setVisible(False)

        self.tickets_table.horizontalHeader().setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.Stretch)
        for col in [self.COLUMN_ID, self.COLUMN_TYPE, self.COLUMN_STATUS, self.COLUMN_PRIORITY,
                    self.COLUMN_RESPONSE_DUE, self.COLUMN_RESOLUTION_DUE,
                    self.COLUMN_SLA_STATUS, self.COLUMN_LAST_UPDATED]:
            self.tickets_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.tickets_table.itemDoubleClicked.connect(self.handle_ticket_double_clicked) # Added connection
        main_layout.addWidget(self.tickets_table)
        self.setLayout(main_layout)

    def _get_ticket_sla_summary_and_color(self, ticket: Ticket, now: datetime) -> Tuple[str, Optional[QColor]]:
        # This helper is identical to the one in AllTicketsView. Could be refactored to a utility module.
        if not hasattr(ticket, 'status'): return "N/A", None

        sla_color: Optional[QColor] = None
        if getattr(ticket, 'sla_paused_at', None): return "Paused", QColor("lightgray")

        response_status_str = "Resp: N/A"
        responded_at = getattr(ticket, 'responded_at', None)
        response_due_at = getattr(ticket, 'response_due_at', None)

        if responded_at:
            response_status_str = "Responded"
            if response_due_at and responded_at > response_due_at:
                response_status_str += " (Late)"; sla_color = QColor("#FFC0CB") # Light Pink
        elif response_due_at:
            if now > response_due_at: response_status_str = "Resp: OVERDUE"; sla_color = QColor("#FF6347") # Tomato Red
            else:
                response_status_str = "Resp: Pending"
                if (response_due_at - now) < timedelta(hours=1) and sla_color is None: sla_color = QColor("#FFFFE0") # Light Yellow

        resolution_status_str = "Reso: N/A"
        resolution_due_at = getattr(ticket, 'resolution_due_at', None)
        ticket_status = ticket.status
        ticket_updated_at = getattr(ticket, 'updated_at', None)

        if ticket_status == 'Closed':
            resolution_status_str = "Resolved"
            if resolution_due_at and ticket_updated_at and ticket_updated_at > resolution_due_at:
                resolution_status_str += " (Late)"
                if sla_color is None or sla_color != QColor("#FF6347"): sla_color = QColor("#FFC0CB")
        elif resolution_due_at:
            if now > resolution_due_at:
                resolution_status_str = "Reso: OVERDUE"; sla_color = QColor("#FF6347")
            else:
                resolution_status_str = "Reso: Pending"
                if (resolution_due_at - now) < timedelta(hours=4) and sla_color is None: sla_color = QColor("#FFFFE0")

        return f"{response_status_str} | {resolution_status_str}", sla_color

    @Slot()
    def load_my_tickets_data(self):
        if not hasattr(self.current_user, 'user_id') or not hasattr(self.current_user, 'role'):
            print("Error: current_user has no user_id or role attribute.", file=sys.stderr)
            self.tickets_table.setRowCount(0)
            QMessageBox.critical(self, "Error", "Cannot load tickets: User information is missing.")
            return

        user_role = self.current_user.role
        user_id = self.current_user.user_id

        # Define roles that should see assigned tickets in "My Tickets"
        # These are roles that primarily work on tickets assigned to them.
        technician_like_roles = ['Technician', 'Engineer']

        # Managers might have different views (e.g., all tickets, team tickets).
        # For "My Tickets", if a manager is also assigned tickets, they should see them.
        # If they are *only* managing, "My Tickets" might be empty or show tickets they requested.
        # For now, let's assume managers also use "My Tickets" for tickets directly assigned to them.
        manager_roles = ['TechManager', 'EngManager']

        if user_role in technician_like_roles or user_role in manager_roles:
            # Technicians, Engineers, and Managers see tickets assigned to them
            self._populate_table(filter_key='assignee_user_id', user_id_to_filter=user_id)
        else:
            # EndUsers (and any other roles not specified above) see tickets they requested
            self._populate_table(filter_key='requester_user_id', user_id_to_filter=user_id)

    def _populate_table(self, filter_key: str, user_id_to_filter: str):
        self.tickets_table.setRowCount(0)
        try:
            tickets: List[Ticket] = list_tickets(filters={filter_key: user_id_to_filter})
        except Exception as e:
            print(f"Error fetching tickets: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"Could not load tickets: {e}")
            return

        if tickets: tickets.sort(key=lambda t: getattr(t, 'updated_at', datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

        self.tickets_table.setRowCount(len(tickets))
        now = datetime.now(timezone.utc)

        for row_num, ticket in enumerate(tickets):
            items: List[QTableWidgetItem] = []

            id_item = QTableWidgetItem(ticket.id)
            id_item.setData(Qt.UserRole, ticket.id) # Store full ticket.id in UserRole
            items.append(id_item)

            items.append(QTableWidgetItem(getattr(ticket, 'title', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'type', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'status', 'N/A')))
            items.append(QTableWidgetItem(getattr(ticket, 'priority', 'N/A')))

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

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if event.isAccepted(): self.load_my_tickets_data()

    @Slot(QTableWidgetItem)
    def handle_ticket_double_clicked(self, item: QTableWidgetItem):
        if not item: # Should not happen if signal is connected to a valid table
            return
        row = item.row()
        # Assuming COLUMN_ID is 0 and holds the QTableWidgetItem with ticket_id in UserRole
        id_item = self.tickets_table.item(row, self.COLUMN_ID)
        if id_item:
            ticket_id = id_item.data(Qt.UserRole) # Retrieve ticket_id
            if not ticket_id: # Fallback if UserRole was not set, try text
                ticket_id = id_item.text()

            if ticket_id:
                print(f"MyTicketsView: Double-click detected on ticket ID: {ticket_id}")
                self.open_ticket_requested.emit(ticket_id)
            else:
                print("MyTicketsView: Could not determine ticket ID from double-clicked row.", file=sys.stderr)

if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try:
        from models import User, Ticket
        from ticket_manager import list_tickets
    except ModuleNotFoundError: pass

    app = QApplication(sys.argv)
    class DummyUserForMyTicketsView(User):
        def __init__(self, u="test_viewer", r="EndUser", uid="viewer_uid_123"):
            self.username = u
            self.role = r
            self.user_id = uid # type: ignore
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TR: __args__ = ('EndUser',); User.ROLES=TR; self.ROLES=TR # type: ignore

        def set_password(self,p):
            pass

        def check_password(self,p):
            return False
    test_user = DummyUserForMyTicketsView()

    _og_list_tickets = ticket_manager.list_tickets
    def mock_list_tickets_my_view(filters=None):
        print(f"MOCK list_tickets_my_view called with filters: {filters}")
        if filters and filters.get('requester_user_id') == test_user.user_id:
            now = datetime.now(timezone.utc)
            return [
                Ticket(id="T001", title="My Laptop Slow", type="IT", status="Open", priority="Medium",
                       requester_user_id=test_user.user_id, created_by_user_id=test_user.user_id,
                       updated_at=now - timedelta(days=1), response_due_at=now+timedelta(hours=1), resolution_due_at=now+timedelta(days=1)),
                Ticket(id="T002", title="Light Flickering", type="Facilities", status="In Progress", priority="Low",
                       requester_user_id=test_user.user_id, created_by_user_id=test_user.user_id,
                       updated_at=now, responded_at=now-timedelta(minutes=30), response_due_at=now-timedelta(minutes=45), resolution_due_at=now+timedelta(days=3)),
            ]
        return []
    ticket_manager.list_tickets = mock_list_tickets_my_view

    my_tickets_view = MyTicketsView(current_user=test_user)
    my_tickets_view.show()
    exit_code = app.exec()
    ticket_manager.list_tickets = _og_list_tickets
    sys.exit(exit_code)
