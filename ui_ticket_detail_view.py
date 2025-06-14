import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QScrollArea, QMessageBox, QApplication
)
from PySide6.QtCore import Slot, Qt, Signal
from PySide6.QtGui import QFont # For comment formatting

from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from models import User, Ticket
    from ticket_manager import get_ticket, update_ticket
    # Placeholder for add_comment_to_ticket, will be properly imported when available
    # from ticket_manager import add_comment_to_ticket
except ModuleNotFoundError:
    print("Error: Critical modules (models, ticket_manager) not found.", file=sys.stderr)
    # Fallbacks
    class User: user_id: str = "fallback_user"
    class Ticket:
        id: str; title: str; description: str; type: str; status: str; priority: str;
        requester_user_id: str; created_by_user_id: str; assignee_user_id: Optional[str];
        created_at: Optional[datetime]; updated_at: Optional[datetime]; comments: List[Dict[str,str]]
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            self.updated_at = datetime.now(); self.created_at = datetime.now(); self.comments = []
    def get_ticket(tid): return None
    def update_ticket(tid, **kwargs): return None
    # def add_comment_to_ticket(tid, uid, text): return False # Placeholder

# Placeholder for the new function - assume it will be added to ticket_manager.py
# This allows the code to be written as if it exists.
def add_comment_to_ticket_placeholder(ticket_id: str, user_id: str, text: str) -> bool:
    print(f"Placeholder: Comment added to ticket {ticket_id} by {user_id}: {text}")
    # In a real scenario, this would interact with ticket_manager which updates the Ticket object
    # and saves it. For now, this placeholder does nothing to the actual ticket data.
    # It needs to return a representation of success or the updated ticket.
    # Let's assume it returns True on success for now.
    return True


class TicketDetailView(QWidget):
    ticket_updated = Signal(str) # Emits ticket_id
    navigate_back = Signal()     # Optional signal

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.current_ticket_id: Optional[str] = None
        self.current_ticket_data: Optional[Ticket] = None

        # Main layout with ScrollArea
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)

        # Ticket Info Section (using QFormLayout for neat label-field pairs)
        info_form_layout = QFormLayout()
        info_form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows) # Ensures responsive wrapping

        self.ticket_id_label = QLabel("N/A")
        info_form_layout.addRow("Ticket ID:", self.ticket_id_label)

        self.title_edit = QLineEdit()
        info_form_layout.addRow("Title:", self.title_edit)

        self.requester_id_label = QLabel("N/A")
        info_form_layout.addRow("Requester ID:", self.requester_id_label)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Open", "In Progress", "Closed"])
        info_form_layout.addRow("Status:", self.status_combo)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        info_form_layout.addRow("Priority:", self.priority_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["IT", "Facilities"])
        info_form_layout.addRow("Type:", self.type_combo)

        self.assignee_edit = QLineEdit() # Placeholder; could be QComboBox later
        self.assignee_edit.setPlaceholderText("Enter User ID or leave blank")
        info_form_layout.addRow("Assigned To (User ID):", self.assignee_edit)

        self.created_at_label = QLabel("N/A")
        info_form_layout.addRow("Created At:", self.created_at_label)

        self.updated_at_label = QLabel("N/A")
        info_form_layout.addRow("Last Updated:", self.updated_at_label)

        layout.addLayout(info_form_layout)

        # Description Section
        layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(100)
        layout.addWidget(self.description_edit)

        # Comments Section
        layout.addWidget(QLabel("Comments/History:"))
        self.comments_display = QTextEdit() # Read-only display for comments
        self.comments_display.setReadOnly(True)
        self.comments_display.setMinimumHeight(150)
        layout.addWidget(self.comments_display)

        layout.addWidget(QLabel("Add New Comment:"))
        self.new_comment_edit = QTextEdit()
        self.new_comment_edit.setMaximumHeight(70) # Smaller box for new comment
        layout.addWidget(self.new_comment_edit)

        self.add_comment_button = QPushButton("Add Comment")
        self.add_comment_button.clicked.connect(self.handle_add_comment)
        layout.addWidget(self.add_comment_button, alignment=Qt.AlignRight)

        # Action Buttons
        action_buttons_layout = QHBoxLayout()
        self.update_ticket_button = QPushButton("Update Ticket")
        self.update_ticket_button.clicked.connect(self.handle_update_ticket)
        action_buttons_layout.addWidget(self.update_ticket_button)

        self.back_button = QPushButton("Back to List") # Optional
        self.back_button.clicked.connect(self.navigate_back.emit)
        action_buttons_layout.addWidget(self.back_button)
        action_buttons_layout.addStretch()
        layout.addLayout(action_buttons_layout)

        self.setLayout(main_layout) # Set main_layout (which contains scroll_area) for the TicketDetailView

    def load_ticket_data(self, ticket_id: str):
        self.current_ticket_id = ticket_id
        try:
            ticket = get_ticket(ticket_id)
            if not ticket:
                QMessageBox.warning(self, "Not Found", f"Ticket ID '{ticket_id}' not found.")
                self.clear_view()
                return
            self.current_ticket_data = ticket
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load ticket data: {e}")
            self.clear_view()
            return

        # Populate read-only labels
        self.ticket_id_label.setText(ticket.id)
        self.requester_id_label.setText(ticket.requester_user_id)
        dt_format = "%Y-%m-%d %H:%M:%S"
        self.created_at_label.setText(ticket.created_at.strftime(dt_format) if ticket.created_at else "N/A")
        self.updated_at_label.setText(ticket.updated_at.strftime(dt_format) if ticket.updated_at else "N/A")

        # Populate editable fields
        self.title_edit.setText(ticket.title)
        self.description_edit.setPlainText(ticket.description)
        self.status_combo.setCurrentText(ticket.status)
        self.priority_combo.setCurrentText(ticket.priority)
        self.type_combo.setCurrentText(ticket.type)
        self.assignee_edit.setText(ticket.assignee_user_id or "")

        self._populate_comments()
        self._apply_role_permissions()


    def _populate_comments(self):
        self.comments_display.clear()
        if self.current_ticket_data and self.current_ticket_data.comments:
            html_comments = ""
            for comment in self.current_ticket_data.comments:
                user_id = comment.get('user_id', 'Unknown User')
                timestamp_str = comment.get('timestamp', 'N/A')
                text = comment.get('text', '')
                # Basic HTML for formatting
                html_comments += f"<p><b>{user_id}</b> ({timestamp_str}):<br/>{text}</p><hr>"
            self.comments_display.setHtml(html_comments)
        else:
            self.comments_display.setPlainText("No comments yet.")

    def _apply_role_permissions(self):
        # Basic permission: allow edits if ticket is not "Closed"
        # More complex logic based on self.current_user.role can be added here
        can_edit = self.current_ticket_data and self.current_ticket_data.status != "Closed"

        # For technicians/engineers/managers, allow editing unless closed.
        # EndUsers might have more restricted editing (e.g., only add comments, or not edit at all).
        # This is a simplified version.
        if self.current_user.role not in ['Technician', 'Engineer', 'TechManager', 'EngManager']:
            can_edit = False # Example: EndUsers cannot edit fields directly, only add comments maybe

        self.title_edit.setReadOnly(not can_edit)
        self.description_edit.setReadOnly(not can_edit)
        self.status_combo.setEnabled(can_edit)
        self.priority_combo.setEnabled(can_edit)
        self.type_combo.setEnabled(can_edit) # Type might be non-editable after creation
        self.assignee_edit.setReadOnly(not can_edit)

        self.update_ticket_button.setEnabled(can_edit)
        # Add comment button might have different logic (e.g., always enabled if ticket is open/in progress)
        self.add_comment_button.setEnabled(self.current_ticket_data and self.current_ticket_data.status != "Closed")


    @Slot()
    def handle_update_ticket(self):
        if not self.current_ticket_id or not self.current_ticket_data:
            QMessageBox.warning(self, "No Ticket", "No ticket is currently loaded for update.")
            return

        update_data: Dict[str, Any] = {}
        # Title (only if changed from original to avoid unnecessary updates)
        if self.title_edit.text() != self.current_ticket_data.title:
            update_data['title'] = self.title_edit.text()
        # Description (only if changed)
        if self.description_edit.toPlainText() != self.current_ticket_data.description:
            update_data['description'] = self.description_edit.toPlainText()
        # Status (only if changed)
        if self.status_combo.currentText() != self.current_ticket_data.status:
            update_data['status'] = self.status_combo.currentText()
        # Priority (only if changed)
        if self.priority_combo.currentText() != self.current_ticket_data.priority:
            update_data['priority'] = self.priority_combo.currentText()
        # Type (only if changed)
        if self.type_combo.currentText() != self.current_ticket_data.type:
            update_data['type'] = self.type_combo.currentText()
        # Assignee (only if changed, handle empty string as None)
        assignee_text = self.assignee_edit.text().strip()
        current_assignee = self.current_ticket_data.assignee_user_id
        if (assignee_text or None) != current_assignee: # handles empty string to None conversion
            update_data['assignee_user_id'] = assignee_text if assignee_text else None

        if not update_data:
            QMessageBox.information(self, "No Changes", "No changes detected to update.")
            return

        try:
            updated_ticket = update_ticket(self.current_ticket_id, **update_data)
            if updated_ticket:
                QMessageBox.information(self, "Success", f"Ticket ID '{self.current_ticket_id}' updated successfully.")
                self.ticket_updated.emit(self.current_ticket_id)
                self.load_ticket_data(self.current_ticket_id) # Reload to show updated data
            else:
                QMessageBox.warning(self, "Update Failed", "Failed to update ticket. It might have been deleted or an error occurred.")
        except ValueError as ve:
            QMessageBox.critical(self, "Validation Error", f"Error updating ticket: {ve}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
            print(f"Error updating ticket {self.current_ticket_id}: {e}", file=sys.stderr)


    @Slot()
    def handle_add_comment(self):
        if not self.current_ticket_id:
            QMessageBox.warning(self, "No Ticket", "No ticket is loaded to add a comment.")
            return

        comment_text = self.new_comment_edit.toPlainText().strip()
        if not comment_text:
            QMessageBox.warning(self, "Empty Comment", "Comment text cannot be empty.")
            return

        try:
            # This is a placeholder. Real implementation will be in ticket_manager.
            # For now, we'll simulate it by adding to current_ticket_data and re-populating
            # This assumes add_comment_to_ticket would modify the ticket and save it.

            # success = add_comment_to_ticket(self.current_ticket_id, self.current_user.user_id, comment_text)

            # --- Start Placeholder block for add_comment_to_ticket ---
            # This block should be replaced by a call to a real ticket_manager function
            # that appends the comment to the Ticket object and saves it.
            if self.current_ticket_data:
                new_comment_obj = {
                    'user_id': self.current_user.user_id,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'text': comment_text
                }
                # Simulate adding to the current ticket data directly
                self.current_ticket_data.comments.append(new_comment_obj)
                # Simulate the ticket's updated_at time being changed
                self.current_ticket_data.updated_at = datetime.now(timezone.utc)

                # Simulate saving and then getting the ticket again (which update_ticket does partially)
                # In a real scenario, add_comment_to_ticket in ticket_manager would handle saving.
                # Here, we're just demonstrating the UI update path.
                # We'd need to save self.current_ticket_data if this was the final persistence layer.
                # For now, we assume the backend function would do this.
                # Let's use the placeholder that just prints.
                success = add_comment_to_ticket_placeholder(self.current_ticket_id, self.current_user.user_id, comment_text)
            else:
                success = False
            # --- End Placeholder block ---

            if success:
                QMessageBox.information(self, "Comment Added", "Comment added successfully.")
                self.new_comment_edit.clear()
                self.ticket_updated.emit(self.current_ticket_id) # Signal that ticket changed
                self.load_ticket_data(self.current_ticket_id) # Reload to show new comment & updated_at
            else:
                QMessageBox.warning(self, "Failed", "Could not add comment.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while adding comment: {e}")
            print(f"Error adding comment to ticket {self.current_ticket_id}: {e}", file=sys.stderr)


    def clear_view(self):
        self.current_ticket_id = None
        self.current_ticket_data = None

        self.ticket_id_label.setText("N/A")
        self.title_edit.clear()
        self.requester_id_label.setText("N/A")
        self.status_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.assignee_edit.clear()
        self.created_at_label.setText("N/A")
        self.updated_at_label.setText("N/A")
        self.description_edit.clear()
        self.comments_display.clear()
        self.new_comment_edit.clear()

        # Reset editable states (or call _apply_role_permissions if it handles default state)
        self.title_edit.setReadOnly(True)
        self.description_edit.setReadOnly(True)
        self.status_combo.setEnabled(False)
        # ... and so on for other editable fields


if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    try: from models import User, Ticket
    except: pass # Fallbacks at top

    app = QApplication(sys.argv)

    class DummyUserDetailView(User):
        def __init__(self, username="detail_viewer", role="Technician", user_id_val="detail_uid_789"):
            self.username = username; self.role = role # type: ignore
            self.user_id = user_id_val
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempRoles: __args__ = ('Technician', 'EndUser') # Ensure role is valid
                 User.ROLES = TempRoles # type: ignore
                 self.ROLES = TempRoles # type: ignore
        def set_password(self,p):pass
        def check_password(self,p):return False

    test_user = DummyUserDetailView()

    # Mock ticket_manager functions
    _original_get_ticket = ticket_manager.get_ticket
    _original_update_ticket = ticket_manager.update_ticket
    # _original_add_comment = ticket_manager.add_comment_to_ticket # When it exists

    _mock_ticket_db = {
        "T001": Ticket(id="T001", title="Mocked Server Down", description="The main server is offline and needs urgent attention.",
                       type="IT", status="Open", priority="High", requester_user_id="user001",
                       created_by_user_id="user001", assignee_user_id="tech001",
                       created_at=datetime.now(timezone.utc)-timedelta(days=2),
                       updated_at=datetime.now(timezone.utc)-timedelta(hours=5),
                       comments=[
                           {'user_id': 'user001', 'timestamp': (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(), 'text': 'Any updates on this?'},
                           {'user_id': 'tech001', 'timestamp': (datetime.now(timezone.utc)-timedelta(hours=6)).isoformat(), 'text': 'Working on it, seems like a power supply issue.'}
                       ])
    }

    def mock_get_ticket(ticket_id):
        print(f"MOCK get_ticket called for ID: {ticket_id}")
        return _mock_ticket_db.get(ticket_id)

    def mock_update_ticket(ticket_id, **kwargs):
        print(f"MOCK update_ticket called for ID: {ticket_id} with data: {kwargs}")
        if ticket_id in _mock_ticket_db:
            ticket = _mock_ticket_db[ticket_id]
            for key, value in kwargs.items():
                if hasattr(ticket, key): setattr(ticket, key, value)
            ticket.updated_at = datetime.now(timezone.utc)
            return ticket
        return None

    # def mock_add_comment_to_ticket(ticket_id, user_id, text):
    #     print(f"MOCK add_comment called for {ticket_id} by {user_id}: {text}")
    #     if ticket_id in _mock_ticket_db:
    #         _mock_ticket_db[ticket_id].comments.append({'user_id':user_id, 'timestamp':datetime.now(timezone.utc).isoformat(), 'text':text})
    #         _mock_ticket_db[ticket_id].updated_at = datetime.now(timezone.utc)
    #         return True
    #     return False

    ticket_manager.get_ticket = mock_get_ticket
    ticket_manager.update_ticket = mock_update_ticket
    # ticket_manager.add_comment_to_ticket = mock_add_comment_to_ticket # When it exists
    # For now, the view uses its own placeholder: add_comment_to_ticket_placeholder

    detail_view = TicketDetailView(current_user=test_user)

    def on_ticket_updated(tid):
        print(f"TEST: ticket_updated signal for ticket_id: {tid}")
    def on_navigate_back():
        print("TEST: navigate_back signal received.")
        detail_view.close() # Example action

    detail_view.ticket_updated.connect(on_ticket_updated)
    detail_view.navigate_back.connect(on_navigate_back)

    detail_view.load_ticket_data("T001") # Load initial ticket
    detail_view.show()

    exit_code = app.exec()

    # Restore original functions
    ticket_manager.get_ticket = _original_get_ticket
    ticket_manager.update_ticket = _original_update_ticket
    # ticket_manager.add_comment_to_ticket = _original_add_comment

    sys.exit(exit_code)
