import sys
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox
)
from PySide6.QtCore import Slot # For explicit slot decoration, good practice

# Assuming user_manager.py and models.py are in the same directory or PYTHONPATH
try:
    from user_manager import verify_user
    from models import User # For type hinting
    from ui_main_window import MainWindow # Added for integration
except ModuleNotFoundError:
    print("Error: user_manager.py, models.py, or ui_main_window.py not found. Ensure they are accessible.")
    # Fallback for User type hint if models.py is missing
    class User: username: str; role: str
    def verify_user(u, p): return None # Fallback verify_user

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

        if user:
            self.message_label.setText(f"Login successful! Welcome {user.username} (Role: {user.role})")
            self.message_label.setStyleSheet("color: green;")
            # Optional: Keep this for immediate feedback before main window fully loads
            # QMessageBox.information(self, "Login Success", f"Welcome {user.username}!\nRole: {user.role}")

            # Open the main window
            self.main_window = MainWindow(user=user)
            self.main_window.show()

            self.close() # Close the login window
        else:
            self.message_label.setText("Invalid username or password.")
            self.message_label.setStyleSheet("color: red;")
            # Do not show a pop-up for invalid credentials to prevent user enumeration,
            # just update the label. Or, if a pop-up is desired:
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
