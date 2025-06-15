import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QMessageBox, QApplication, QWidget
)
from PySide6.QtCore import Slot, Qt
from typing import Optional, TYPE_CHECKING

# To avoid circular import issues if user_manager also imports from UI elements (though not typical)
# We can use TYPE_CHECKING for type hints.
if TYPE_CHECKING:
    from user_manager import set_user_password # For type hinting only

# For runtime, import locally or ensure no circularity. For this structure, direct import is fine.
try:
    from user_manager import set_user_password
except ModuleNotFoundError:
    print("Error: user_manager.py not found. ChangePasswordDialog will not function correctly.", file=sys.stderr)
    def set_user_password(uid: str, np: str) -> bool: # Fallback
        print(f"Fallback set_user_password called for {uid}")
        return False

class ChangePasswordDialog(QDialog):
    MIN_PASSWORD_LENGTH = 8 # Example minimum password length

    def __init__(self, user_id: str, username: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.user_id = user_id
        self.username = username

        self.setWindowTitle(f"Change Password for {username}")
        self.setModal(True) # Make dialog modal
        self.setMinimumWidth(350)

        main_layout = QVBoxLayout(self)

        instruction_label = QLabel(
            "Your password has expired or needs to be reset.\n"
            "Please enter a new password to continue."
        )
        instruction_label.setWordWrap(True)
        main_layout.addWidget(instruction_label)

        # New Password
        new_password_layout = QHBoxLayout()
        new_password_layout.addWidget(QLabel("New Password:"))
        self.new_password_edit = QLineEdit()
        self.new_password_edit.setEchoMode(QLineEdit.Password)
        self.new_password_edit.setPlaceholderText(f"Min. {self.MIN_PASSWORD_LENGTH} characters")
        new_password_layout.addWidget(self.new_password_edit)
        main_layout.addLayout(new_password_layout)

        # Confirm Password
        confirm_password_layout = QHBoxLayout()
        confirm_password_layout.addWidget(QLabel("Confirm New Password:"))
        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setEchoMode(QLineEdit.Password)
        confirm_password_layout.addWidget(self.confirm_password_edit)
        main_layout.addLayout(confirm_password_layout)

        # Message Label for errors
        self.message_label = QLabel("")
        self.message_label.setStyleSheet("color: red;") # Style for error messages
        self.message_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.message_label)

        # Button Box
        self.button_box = QDialogButtonBox()
        self.ok_button = self.button_box.addButton(QDialogButtonBox.Ok)
        self.cancel_button = self.button_box.addButton(QDialogButtonBox.Cancel)
        main_layout.addWidget(self.button_box)

        # Connections
        self.ok_button.clicked.connect(self.handle_accept) # QDialogButtonBox.Ok maps to accepted signal
        # self.button_box.accepted.connect(self.handle_accept) # Alternative connection
        self.button_box.rejected.connect(self.reject) # QDialog.reject() closes with Rejected state

        self.new_password_edit.returnPressed.connect(self.confirm_password_edit.setFocus)
        self.confirm_password_edit.returnPressed.connect(self.handle_accept)

        self.setLayout(main_layout)

    @Slot()
    def handle_accept(self):
        self.message_label.setText("") # Clear previous messages
        new_password = self.new_password_edit.text()
        confirm_password = self.confirm_password_edit.text()

        if not new_password or not confirm_password:
            self.message_label.setText("Password fields cannot be empty.")
            return

        if len(new_password) < self.MIN_PASSWORD_LENGTH:
            self.message_label.setText(f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters long.")
            return

        if new_password != confirm_password:
            self.message_label.setText("Passwords do not match.")
            return

        try:
            success = set_user_password(self.user_id, new_password)
            if success:
                QMessageBox.information(self, "Success",
                                        "Password changed successfully.\n"
                                        "You may need to log in again with your new password.")
                self.accept() # Close dialog with QDialog.Accepted state
            else:
                # This could be due to user_id not found (unlikely if dialog is launched correctly)
                # or a failure in _save_users within user_manager.
                error_msg = "Failed to set new password. User not found or save error."
                self.message_label.setText(error_msg)
                QMessageBox.critical(self, "Error", error_msg + "\nPlease contact an administrator.")
        except ValueError as ve: # e.g., if set_user_password raises ValueError for empty password (already checked here)
            self.message_label.setText(f"Validation Error: {ve}")
            # QMessageBox.warning(self, "Validation Error", str(ve))
        except Exception as e:
            error_msg_unexpected = "An unexpected error occurred while setting password."
            self.message_label.setText(error_msg_unexpected)
            print(f"Unexpected error in ChangePasswordDialog.handle_accept: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"{error_msg_unexpected}\nDetails: {e}")


if __name__ == '__main__':
    import os
    # Ensure user_manager can be found if it's in parent or sibling dir
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Re-import after path adjustment for direct testing if needed
    try:
        from user_manager import set_user_password as real_set_user_password
    except ModuleNotFoundError:
        # Fallback already defined at top of file if initial import failed
        real_set_user_password = set_user_password


    app = QApplication(sys.argv)

    # --- Mocking user_manager.set_user_password for testing dialog scenarios ---
    mock_set_password_patcher = patch('__main__.set_user_password')
    # If set_user_password was imported as `from user_manager import set_user_password`
    # then the patch path would be 'ui_change_password_dialog.set_user_password'
    # However, since we might be using the fallback, patching __main__ for direct run.
    # For robust test, it's better to patch where it's looked up: 'ui_change_password_dialog.set_user_password'

    mock_set_password_func = MagicMock()

    def run_dialog_test(return_value_for_set_password, expected_dialog_result):
        mock_set_password_func.reset_mock(return_value=True, side_effect=None) # Reset for each run
        mock_set_password_func.return_value = return_value_for_set_password

        # Patch the set_user_password function that the dialog will call
        # The path depends on how it's imported in ChangePasswordDialog
        with patch('ui_change_password_dialog.set_user_password', mock_set_password_func):
            dialog = ChangePasswordDialog(user_id="test_user_id", username="testuser")
            result = dialog.exec()
            print(f"Dialog result: {'Accepted' if result == QDialog.Accepted else 'Rejected'}")
            assert result == expected_dialog_result
            if return_value_for_set_password and result == QDialog.Accepted: # only assert if it was supposed to be called
                 mock_set_password_func.assert_called_once()
            elif result == QDialog.Accepted and not return_value_for_set_password : # Should not accept if save failed
                 print("Error: Dialog accepted even if set_user_password returned False")
                 assert False
            print("-" * 20)


    print("Test 1: Successful password change")
    run_dialog_test(True, QDialog.Accepted)
    # User interaction: Enter "newpassword123", "newpassword123", click OK

    print("Test 2: Failed password change (user_manager returns False)")
    run_dialog_test(False, QDialog.Rejected) # Dialog might close if not handled by just setting message_label
    # User interaction: Enter "newpassword123", "newpassword123", click OK. Dialog should show error, not accept.
    # The current dialog logic: if set_user_password returns False, it sets message_label but doesn't explicitly prevent accept.
    # QDialogButtonBox.Ok typically results in accept() unless an error handler in handle_accept prevents it or calls reject().
    # For this manual test, the dialog will accept, but show an error. The assert will fail.
    # To fix this, handle_accept should not call self.accept() if success is False.
    # Let's assume for now the dialog closes and shows QMessageBox.
    # The provided code in the prompt *does* call self.accept() only on success=True.

    print("Test 3: Passwords do not match (handled by dialog logic)")
    # No need to mock set_user_password for this, as it won't be called.
    dialog_mismatch = ChangePasswordDialog(user_id="test_uid", username="test_user_mismatch")
    # Simulate user typing:
    # dialog_mismatch.new_password_edit.setText("password123")
    # dialog_mismatch.confirm_password_edit.setText("password456")
    # dialog_mismatch.ok_button.click() # or dialog_mismatch.handle_accept()
    # For manual test: Run, enter mismatching passwords, click OK. Check message_label. Dialog stays open.
    print("Manually test mismatch, empty, short password scenarios by running the dialog.")
    dialog_mismatch.show() # Show for manual interaction if desired, or simulate clicks for full auto test.

    # For a full auto test of "Passwords do not match":
    # with patch('ui_change_password_dialog.set_user_password', mock_set_password_func):
    #     dialog = ChangePasswordDialog(user_id="test_user_id", username="testuser_mismatch_auto")
    #     dialog.new_password_edit.setText("validpass123")
    #     dialog.confirm_password_edit.setText("mismatch123")
    #     dialog.handle_accept() # Call slot directly
    #     assert "Passwords do not match" in dialog.message_label.text()
    #     mock_set_password_func.assert_not_called()

    # To run the last dialog for interaction:
    # sys.exit(app.exec()) # Uncomment to interact with the last dialog

    # For automated flow, we'd often close test dialogs programmatically or not use exec()
    # but rather test methods directly. The above `run_dialog_test` simulates this partially.

    # Clean exit for non-interactive test run
    sys.exit(0)
