import sys
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView,
    QMessageBox  # For error display
)
from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QShowEvent # For overriding showEvent

from datetime import datetime # For formatting datetime objects
from typing import Optional, List

# Assuming models.py and ticket_manager.py are accessible
try:
    from models import User, Ticket
    from ticket_manager import list_tickets
except ModuleNotFoundError:
    print("Error: models.py or ticket_manager.py not found. Ensure they are accessible.", file=sys.stderr)
    # Fallback definitions for type hinting and basic functionality
    class User: user_id: str = "fallback_user"
    class Ticket:
        id: str; title: str; type: str; status: str; priority: str; updated_at: Optional[datetime]
        def __init__(self, **kwargs): # Basic init for dummy
            for k, v in kwargs.items(): setattr(self, k, v)
            self.updated_at = datetime.now() # Ensure it exists

    def list_tickets(filters=None) -> list: # type: ignore
        print(f"Warning: Using fallback list_tickets function with filters: {filters}. Returning empty list.", file=sys.stderr)
        return []
    # raise # Or re-raise to make it clear during testing if imports fail

class MyTicketsView(QWidget):
    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user

        self.setWindowTitle("My Submitted Tickets") # Can be set if used as a standalone window

        main_layout = QVBoxLayout(self)

        # Refresh Button
        self.refresh_button = QPushButton("Refresh Tickets")
        self.refresh_button.clicked.connect(self.load_my_tickets_data)
        # Add button to a QHBoxLayout for better alignment if needed, or directly
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_button)
        main_layout.addLayout(button_layout)

        # Table Widget
        self.tickets_table = QTableWidget()
        self.tickets_table.setColumnCount(6)
        self.tickets_table.setHorizontalHeaderLabels([
            "ID", "Title", "Type", "Status", "Priority", "Last Updated"
        ])

        # Table Properties
        self.tickets_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tickets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tickets_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tickets_table.verticalHeader().setVisible(False)
        self.tickets_table.horizontalHeader().setStretchLastSection(True)
        # Example of setting resize mode for specific columns
        self.tickets_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID
        self.tickets_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # Title
        self.tickets_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents) # Type
        self.tickets_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents) # Status
        self.tickets_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents) # Priority
        # Last section (Last Updated) will stretch due to setStretchLastSection(True)

        main_layout.addWidget(self.tickets_table)
        self.setLayout(main_layout)

        # Initial data load is handled by showEvent

    @Slot()
    def load_my_tickets_data(self):
        """Public slot to refresh ticket data."""
        if hasattr(self.current_user, 'user_id'):
            self._populate_table(user_id=self.current_user.user_id)
        else:
            print("Error: current_user has no user_id attribute.", file=sys.stderr)
            self.tickets_table.setRowCount(0) # Clear table
            QMessageBox.critical(self, "Error", "Cannot load tickets: User information is missing.")


    def _populate_table(self, user_id: str):
        self.tickets_table.setRowCount(0) # Clear existing table content

        try:
            # Filter tickets where the current user is the requester
            # The Ticket model has requester_user_id and created_by_user_id.
            # Assuming tickets created by the user are "their" tickets.
            tickets: List[Ticket] = list_tickets(filters={'requester_user_id': user_id})
        except Exception as e:
            print(f"Error fetching tickets: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"Could not load tickets: {e}")
            return

        if tickets:
            tickets.sort(key=lambda t: t.updated_at, reverse=True) # Sort by most recent update

        self.tickets_table.setRowCount(len(tickets))
        for row_num, ticket in enumerate(tickets):
            self.tickets_table.setItem(row_num, 0, QTableWidgetItem(ticket.id))
            self.tickets_table.setItem(row_num, 1, QTableWidgetItem(ticket.title))
            self.tickets_table.setItem(row_num, 2, QTableWidgetItem(ticket.type))
            self.tickets_table.setItem(row_num, 3, QTableWidgetItem(ticket.status))
            self.tickets_table.setItem(row_num, 4, QTableWidgetItem(ticket.priority))

            updated_at_str = ticket.updated_at.strftime("%Y-%m-%d %H:%M:%S") if ticket.updated_at else "N/A"
            item_updated_at = QTableWidgetItem(updated_at_str)
            # Optional: Make datetime sortable if user clicks header (requires custom item or proxy model)
            self.tickets_table.setItem(row_num, 5, item_updated_at)

        # Optional: Resize columns after populating, if not using dynamic resize modes like Stretch
        # self.tickets_table.resizeColumnsToContents()


    def showEvent(self, event: QShowEvent):
        """Override showEvent to load data when the widget becomes visible."""
        super().showEvent(event)
        if event.isAccepted(): # Process only if the event is accepted (widget is actually shown)
            self.load_my_tickets_data()


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import os

    # Ensure models and ticket_manager can be found
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    try: # Re-import after path adjustment
        from models import User, Ticket
        from ticket_manager import list_tickets
    except ModuleNotFoundError: # Should use fallbacks defined at top of file if still not found
        pass

    app = QApplication(sys.argv)

    # Dummy User for testing
    class DummyUserForMyTicketsView(User):
        def __init__(self, username="test_viewer", role="EndUser", user_id_val="viewer_uid_123"):
            self.username = username
            self.role = role # type: ignore
            self.user_id = user_id_val
            if not hasattr(self, 'ROLES') or self.ROLES is None: # For fallback User
                 class TempRoles: __args__ = ('EndUser',)
                 User.ROLES = TempRoles #type: ignore
                 self.ROLES = TempRoles #type: ignore
        def set_password(self, p): pass
        def check_password(self, p): return False

    test_user = DummyUserForMyTicketsView()

    # Mock ticket_manager.list_tickets for direct testing without real data
    original_list_tickets = ticket_manager.list_tickets
    def mock_list_tickets(filters=None):
        print(f"Mocked list_tickets called with filters: {filters}")
        if filters and filters.get('requester_user_id') == test_user.user_id:
            return [
                Ticket(id="T001", title="My Laptop is Slow", type="IT", status="Open", priority="Medium",
                       requester_user_id=test_user.user_id, created_by_user_id=test_user.user_id,
                       updated_at=datetime.now(timezone.utc) - timedelta(days=1)),
                Ticket(id="T002", title="Office Light Flickering", type="Facilities", status="In Progress", priority="Low",
                       requester_user_id=test_user.user_id, created_by_user_id=test_user.user_id,
                       updated_at=datetime.now(timezone.utc)),
            ]
        return []
    ticket_manager.list_tickets = mock_list_tickets


    my_tickets_view = MyTicketsView(current_user=test_user)
    my_tickets_view.show()

    exit_code = app.exec()
    ticket_manager.list_tickets = original_list_tickets # Restore original function
    sys.exit(exit_code)
