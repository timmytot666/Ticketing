import sys
import os
from PySide6.QtWidgets import QApplication

# Add current directory to sys.path to allow ui_login import
# This is often needed when running scripts directly that are part of a package
# not formally installed, especially for subtask environments.
# It ensures that Python can find 'ui_login.py' in the same directory.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from ui_login import LoginWindow
except ImportError as e:
    print(f"Error importing LoginWindow from ui_login: {e}", file=sys.stderr)
    print("Ensure ui_login.py is in the same directory as main_gui.py or in PYTHONPATH.", file=sys.stderr)
    # Fallback: Define a dummy LoginWindow to allow QApplication to run for testing purposes
    # if the main goal is just to test QApplication initialization.
    if "LoginWindow" not in globals(): # Check if it was truly not imported
        from PySide6.QtWidgets import QWidget, QLabel
        class LoginWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("Fallback Window")
                self.label = QLabel("Error: LoginWindow could not be loaded from ui_login.py.", self)
                self.resize(400,100)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Check if LoginWindow is the fallback or the real one
    if hasattr(LoginWindow, 'handle_login'): # A simple check for the real LoginWindow
        login_window = LoginWindow()
        login_window.show()
    else: # Fallback LoginWindow due to import error
        print("Showing fallback window due to LoginWindow import error.", file=sys.stderr)
        fallback_window = LoginWindow() # This is the dummy
        fallback_window.show()
        # Optionally, could exit here if the real window is critical
        # sys.exit(1)

    sys.exit(app.exec())
