import sys
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView,
    QComboBox,
    QLabel,
    QApplication, # For direct test
    QMessageBox
)
from PySide6.QtCore import Slot, Qt, Signal, QShowEvent
from PySide6.QtGui import QFont # Not explicitly used in spec, but good for styling if needed

from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from models import User, Ticket
    from ticket_manager import list_tickets
except ModuleNotFoundError:
    print("Error: Critical modules (models, ticket_manager) not found.", file=sys.stderr)
    # Fallbacks
    class User: user_id: str = "fallback_user"
    class Ticket:
        id: str; title: str; requester_user_id: str; type: str; status: str; priority: str;
        assignee_user_id: Optional[str]; updated_at: Optional[datetime]
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            self.updated_at = datetime.now()
    def list_tickets(filters=None) -> list: # type: ignore
        print(f"Warning: Using fallback list_tickets with filters: {filters}. Returning empty.", file=sys.stderr)
        return []

class AllTicketsView(QWidget):
    ticket_selected = Signal(str) # Emits ticket_id

    COLUMN_ID = 0
    COLUMN_TITLE = 1
    COLUMN_REQUESTER_ID = 2
    COLUMN_TYPE = 3
    COLUMN_STATUS = 4
    COLUMN_PRIORITY = 5
    COLUMN_ASSIGNEE_ID = 6
    COLUMN_LAST_UPDATED = 7

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user # May be used for role-specific actions later

        self.setWindowTitle("All Tickets")
        main_layout = QVBoxLayout(self)

        # Filter Area
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["All", "Open", "In Progress", "Closed"])
        filter_layout.addWidget(self.status_filter_combo)

        filter_layout.addWidget(QLabel("Type:"))
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItems(["All", "IT", "Facilities"])
        filter_layout.addWidget(self.type_filter_combo)

        filter_layout.addWidget(QLabel("Priority:"))
        self.priority_filter_combo = QComboBox()
        self.priority_filter_combo.addItems(["All", "Low", "Medium", "High"])
        filter_layout.addWidget(self.priority_filter_combo)

        filter_layout.addStretch()

        self.apply_filters_button = QPushButton("Apply Filters")
        self.apply_filters_button.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.apply_filters_button)

        self.refresh_button = QPushButton("Refresh List") # Or "Clear Filters & Refresh"
        self.refresh_button.clicked.connect(self.load_and_display_tickets) # Default load without filters
        filter_layout.addWidget(self.refresh_button)

        main_layout.addLayout(filter_layout)

        # Tickets Table
        self.tickets_table = QTableWidget()
        self.tickets_table.setColumnCount(8)
        self.tickets_table.setHorizontalHeaderLabels([
            "ID", "Title", "Requester ID", "Type", "Status", "Priority", "Assigned ID", "Last Updated"
        ])
        self.tickets_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tickets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tickets_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tickets_table.verticalHeader().setVisible(False)
        # self.tickets_table.horizontalHeader().setStretchLastSection(True)
        self.tickets_table.horizontalHeader().setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.Stretch)
        for col in [self.COLUMN_ID, self.COLUMN_REQUESTER_ID, self.COLUMN_TYPE, self.COLUMN_STATUS,
                    self.COLUMN_PRIORITY, self.COLUMN_ASSIGNEE_ID, self.COLUMN_LAST_UPDATED]:
            self.tickets_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.tickets_table.itemDoubleClicked.connect(self.handle_ticket_double_clicked)
        main_layout.addWidget(self.tickets_table)
        self.setLayout(main_layout)

    @Slot()
    def apply_filters(self):
        self.load_and_display_tickets(use_filters=True)

    @Slot()
    def load_and_display_tickets(self, use_filters: bool = False):
        filters_dict: Dict[str, Any] = {}
        if use_filters:
            status = self.status_filter_combo.currentText()
            if status != "All": filters_dict['status'] = status

            ticket_type = self.type_filter_combo.currentText()
            if ticket_type != "All": filters_dict['type'] = ticket_type

            priority = self.priority_filter_combo.currentText()
            if priority != "All": filters_dict['priority'] = priority

        self._populate_table(filters=filters_dict if filters_dict else None)


    def _populate_table(self, filters: Optional[Dict[str, Any]] = None):
        self.tickets_table.setRowCount(0)
        try:
            # If filters is None or empty, list_tickets should return all tickets
            effective_filters = filters if filters else {}
            tickets: List[Ticket] = list_tickets(filters=effective_filters)
        except Exception as e:
            print(f"Error fetching tickets: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"Could not load tickets: {e}")
            return

        if tickets:
            tickets.sort(key=lambda t: t.updated_at, reverse=True)

        self.tickets_table.setRowCount(len(tickets))
        for row_num, ticket in enumerate(tickets):
            id_item = QTableWidgetItem(ticket.id)
            id_item.setData(Qt.UserRole, ticket.id) # Store ticket_id for easy access
            self.tickets_table.setItem(row_num, self.COLUMN_ID, id_item)
            self.tickets_table.setItem(row_num, self.COLUMN_TITLE, QTableWidgetItem(ticket.title))
            self.tickets_table.setItem(row_num, self.COLUMN_REQUESTER_ID, QTableWidgetItem(ticket.requester_user_id))
            self.tickets_table.setItem(row_num, self.COLUMN_TYPE, QTableWidgetItem(ticket.type))
            self.tickets_table.setItem(row_num, self.COLUMN_STATUS, QTableWidgetItem(ticket.status))
            self.tickets_table.setItem(row_num, self.COLUMN_PRIORITY, QTableWidgetItem(ticket.priority))
            self.tickets_table.setItem(row_num, self.COLUMN_ASSIGNEE_ID, QTableWidgetItem(ticket.assignee_user_id or "N/A"))

            updated_at_str = ticket.updated_at.strftime("%Y-%m-%d %H:%M:%S") if ticket.updated_at else "N/A"
            self.tickets_table.setItem(row_num, self.COLUMN_LAST_UPDATED, QTableWidgetItem(updated_at_str))

    @Slot(QTableWidgetItem)
    def handle_ticket_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        id_cell_item = self.tickets_table.item(row, self.COLUMN_ID)
        if id_cell_item:
            ticket_id = id_cell_item.data(Qt.UserRole)
            if ticket_id:
                self.ticket_selected.emit(ticket_id)
                print(f"Ticket {ticket_id} double-clicked (selected).") # For debugging

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if event.isAccepted():
            self.load_and_display_tickets(use_filters=False) # Load all tickets initially


if __name__ == '__main__':
    import os
    from datetime import timedelta # For dummy data
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    try: from models import User, Ticket
    except: pass # Fallbacks at top of file

    app = QApplication(sys.argv)

    class DummyUserForAllTickets(User):
        def __init__(self, username="all_ticket_viewer", role="Technician", user_id_val="tech_uid_456"):
            self.username = username; self.role = role # type: ignore
            self.user_id = user_id_val
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempRoles: __args__ = ('Technician',) # Example role
                 User.ROLES = TempRoles #type: ignore
                 self.ROLES = TempRoles #type: ignore
        def set_password(self, p): pass
        def check_password(self, p): return False

    test_user = DummyUserForAllTickets()

    _original_list_tickets = ticket_manager.list_tickets
    _mock_db_all_tickets = [
        Ticket(id="T001", title="Server Down", requester_user_id="user001", type="IT", status="Open", priority="High", assignee_user_id="tech001", updated_at=datetime.now(timezone.utc)),
        Ticket(id="T002", title="Printer Jam", requester_user_id="user002", type="Facilities", status="In Progress", priority="Medium", assignee_user_id="tech002", updated_at=datetime.now(timezone.utc) - timedelta(hours=1)),
        Ticket(id="T003", title="Software Install Request", requester_user_id="user003", type="IT", status="Open", priority="Low", assignee_user_id=None, updated_at=datetime.now(timezone.utc) - timedelta(days=1)),
        Ticket(id="T004", title="AC Unit Broken", requester_user_id="user001", type="Facilities", status="Closed", priority="High", assignee_user_id="tech001", updated_at=datetime.now(timezone.utc) - timedelta(days=2)),
    ]
    def mock_list_tickets_for_all_view(filters=None):
        print(f"MOCK list_tickets_for_all_view called with filters: {filters}")
        if not filters: return _mock_db_all_tickets

        filtered_list = _mock_db_all_tickets
        if 'status' in filters:
            filtered_list = [t for t in filtered_list if t.status == filters['status']]
        if 'type' in filters:
            filtered_list = [t for t in filtered_list if t.type == filters['type']]
        if 'priority' in filters:
            filtered_list = [t for t in filtered_list if t.priority == filters['priority']]
        return filtered_list
    ticket_manager.list_tickets = mock_list_tickets_for_all_view


    all_tickets_view = AllTicketsView(current_user=test_user)
    def handle_selection(ticket_id):
        print(f"TEST: ticket_selected signal received for ticket_id: {ticket_id}")
        QMessageBox.information(all_tickets_view, "Ticket Selected", f"Ticket ID: {ticket_id} would be opened.")
    all_tickets_view.ticket_selected.connect(handle_selection)

    all_tickets_view.show()
    exit_code = app.exec()
    ticket_manager.list_tickets = _original_list_tickets # Restore
    sys.exit(exit_code)
