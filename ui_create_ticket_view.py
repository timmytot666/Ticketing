import sys
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QMessageBox,
    QFormLayout  # Using QFormLayout for a standard form appearance
)
from PySide6.QtCore import Slot, Qt

from typing import Optional

# Assuming models.py and ticket_manager.py are accessible
try:
    from models import User
    from ticket_manager import create_ticket
except ModuleNotFoundError:
    print("Error: models.py or ticket_manager.py not found. Ensure they are accessible.", file=sys.stderr)
    # Fallback for User type hint and create_ticket function
    class User: user_id: str = "fallback_user"
    def create_ticket(*args, **kwargs):
        print("Warning: Using fallback create_ticket function.")
        class DummyTicket: id = "dummy_id"; title = kwargs.get("title", "Dummy")
        return DummyTicket()
    raise # Re-raise to make it clear during testing if imports fail. Or define dummy for User.ROLES

class CreateTicketView(QWidget):
    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user

        self.setWindowTitle("Create New Ticket") # Can be set if this widget is used as a window

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Enter a brief title for the ticket")
        form_layout.addRow(QLabel("Title:"), self.title_edit)

        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Provide a detailed description of the issue")
        self.description_edit.setMinimumHeight(100) # Give some space for description
        form_layout.addRow(QLabel("Description:"), self.description_edit)

        # Type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["IT", "Facilities"])
        form_layout.addRow(QLabel("Type:"), self.type_combo)

        # Priority
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText("Medium") # Default priority
        form_layout.addRow(QLabel("Priority:"), self.priority_combo)

        main_layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Submit Ticket")
        self.submit_button.clicked.connect(self.handle_submit_ticket)

        # Button layout for alignment
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push button to the right
        button_layout.addWidget(self.submit_button)
        button_layout.addStretch() # Or center it: addStretch before and after

        main_layout.addLayout(button_layout)

        # Message Label
        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.message_label)

        main_layout.addStretch() # Pushes content to the top

        self.setLayout(main_layout)

    @Slot()
    def handle_submit_ticket(self):
        title = self.title_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        ticket_type = self.type_combo.currentText()
        priority = self.priority_combo.currentText()

        if not title or not description:
            self.message_label.setText("Title and Description cannot be empty.")
            self.message_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Input Error", "Title and Description cannot be empty.")
            return

        try:
            new_ticket = create_ticket(
                title=title,
                description=description,
                type=ticket_type,
                priority=priority,
                requester_user_id=self.current_user.user_id
                # assignee_user_id is omitted, will default to None in ticket_manager/model
            )
            success_message = f"Ticket '{new_ticket.title}' created successfully with ID: {new_ticket.id}"
            self.message_label.setText(success_message)
            self.message_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "Ticket Created", success_message)
            self._clear_form()
            # In a real MDI or tabbed interface, you might emit a signal here
            # self.ticket_created.emit(new_ticket.id)
        except ValueError as ve:
            error_message = f"Error: {ve}"
            self.message_label.setText(error_message)
            self.message_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Creation Error", f"Error creating ticket: {ve}")
        except Exception as e:
            self.message_label.setText("An unexpected error occurred. Please try again.")
            self.message_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Error", "An unexpected error occurred while creating the ticket.")
            print(f"Error creating ticket: {e}", file=sys.stderr) # Log for debugging

    def _clear_form(self):
        self.title_edit.clear()
        self.description_edit.clear()
        self.type_combo.setCurrentIndex(0) # Reset to the first item ("IT")
        self.priority_combo.setCurrentText("Medium") # Reset to "Medium"
        self.message_label.setText("") # Clear message label

if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import os

    # Ensure models and ticket_manager can be found if they are in parent or sibling dirs
    # This handles running the script directly if it's part of a larger package structure.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Re-import after path adjustment if initial imports failed due to path issues
    # This is more for robustness if the script is moved or run in unusual ways.
    try:
        from models import User
        from ticket_manager import create_ticket # Ensure this is the real one for testing
    except ModuleNotFoundError: # If still not found, the fallback in the class will be used
        pass


    app = QApplication(sys.argv)

    # Create a dummy user for testing - ensure it has user_id
    # Use the actual User class if possible, but provide a fallback dummy if User has complex deps for init
    class DummyUserForCreateView(User):
        def __init__(self, username, role, user_id_val="test_creator_uid"):
            # This simplified init avoids issues if User's real __init__ needs more (e.g. password_hash)
            # or if ROLES Literal is tricky with the fallback.
            self.username = username
            self.role = role # type: ignore
            self.user_id = user_id_val
            # Add ROLES if models.User fallback is active and User.ROLES is None
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempRoles: __args__ = ('EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager')
                 User.ROLES = TempRoles # type: ignore # Assign to the User class for consistency
                 self.ROLES = TempRoles # type: ignore

        def set_password(self, password): pass # Not needed for this view test
        def check_password(self, password) -> bool: return False # Not needed

    try:
        # Try to use the real User object
        test_user_role = User.ROLES.__args__[0] if User.ROLES and hasattr(User.ROLES, '__args__') else 'EndUser' # type: ignore
        test_user = User(username="test_form_user", role=test_user_role, user_id_val="form_user_001") # type: ignore
    except Exception: # Fallback to simpler dummy if real User init fails
        test_user = DummyUserForCreateView(username="test_form_user_dummy", role='EndUser', user_id_val="form_user_002") # type: ignore


    create_ticket_view = CreateTicketView(current_user=test_user)
    create_ticket_view.show()
    sys.exit(app.exec())
