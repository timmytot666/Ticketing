import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QDialog # Added for checking dialog result
)
from PySide6.QtCore import Slot # For explicit slot decoration, good practice

# Assuming user_manager.py and models.py are in the same directory or PYTHONPATH
try:
    from user_manager import verify_user
    from models import User # For type hinting
    from ui_main_window import MainWindow
    from ui_change_password_dialog import ChangePasswordDialog # Added
except ModuleNotFoundError:
    print("Error: A required module was not found. Ensure all UI and manager files are accessible.")
    # Fallback for User type hint if models.py is missing
    class User: username: str; role: str; force_password_reset: bool = False; user_id: str = "fb_user" # Added more for fallback
    def verify_user(u, p): return None # Fallback verify_user
    class MainWindow: pass # Fallback
    class ChangePasswordDialog: pass # Fallback


from typing import Optional

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login - Ticketing System")
        self.setGeometry(300, 300, 300, 200) # x, y, width, height
        self.main_window: Optional[MainWindow] = None # Reference to the main window

        layout = QVBoxLayout()

        # Username
        self.username_label = QLabel("Username:")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)

        # Password
        self.password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        # Login Button
        self.login_button = QPushButton("Login")
        layout.addWidget(self.login_button)

        # Message Label
        self.message_label = QLabel("") # For displaying messages
        layout.addWidget(self.message_label)

        self.setLayout(layout)

        # Connect signals to slots
        self.login_button.clicked.connect(self.handle_login)
        self.username_input.returnPressed.connect(self.handle_login) # Allow login on Enter from username
        self.password_input.returnPressed.connect(self.handle_login) # Allow login on Enter from password


    @Slot() # Explicitly mark as a slot
    def handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            self.message_label.setText("Username and password cannot be empty.")
            self.message_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Input Error", "Username and password cannot be empty.")
            return

        try:
            user: Optional[User] = verify_user(username, password)
        except Exception as e: # Catch any backend errors from verify_user (e.g. file access)
            self.message_label.setText(f"An error occurred: {e}")
            self.message_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Login Error", f"An unexpected error occurred during login: {e}")
            return

        if user: # verify_user now returns None if inactive or invalid credentials
            if hasattr(user, 'force_password_reset') and user.force_password_reset:
                # self.message_label.setText("Password change required.") # Optional immediate feedback
                # Ensure ChangePasswordDialog can be instantiated (might need to adjust fallback if User is also fallback)
                try:
                    change_password_dialog = ChangePasswordDialog(user_id=user.user_id, username=user.username, parent=self)
                    dialog_result = change_password_dialog.exec()

                    if dialog_result == QDialog.Accepted:
                        QMessageBox.information(self, "Password Changed", "Password changed successfully. Please log in again with your new password.")
                        self.username_edit.clear()
                        self.password_input.clear() # Changed from self.password_edit
                        self.message_label.setText("Please log in with your new password.")
                        self.username_edit.setFocus()
                    else:
                        self.message_label.setText("Password change is required to proceed. Login aborted.")
                    return # Stop further login processing here in both cases.
                except TypeError as te: # Catch if fallback ChangePasswordDialog is incompatible
                     self.message_label.setText("Error: Password change dialog unavailable.")
                     print(f"TypeError when creating/executing ChangePasswordDialog: {te}", file=sys.stderr)
                     return


            # If not force_password_reset, proceed to MainWindow
            # self.message_label.setText(f"Login successful! Welcome {user.username} (Role: {user.role})") # Optional

            self.main_window = MainWindow(user=user)
            self.main_window.show()
            self.close()
        else: # User is None (login failed or inactive)
            self.message_label.setText("Invalid username, password, or account inactive.")
            self.message_label.setStyleSheet("color: red;")
            # QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

# Example of running this window directly for testing (optional)
if __name__ == '__main__':
    # This is necessary to ensure that user_manager, models, and ui_main_window can be found
    import os
    import sys
    # Assuming this script is in 'src/' and other modules are also in 'src/' or 'src/models' etc.
    # If ui_login.py is run directly, its own directory is already in sys.path.
    # If other modules are in parent or sibling dirs, adjust path:
    # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


    app = QApplication(sys.argv)
    login_win = LoginWindow()
    login_win.show()
    sys.exit(app.exec())
