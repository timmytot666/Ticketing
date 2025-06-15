import unittest
from unittest.mock import MagicMock, patch, PropertyMock, call

# Attempt to import PySide6 components
try:
    from PySide6.QtWidgets import QWidget, QTableWidget, QLineEdit, QComboBox, QPushButton, QLabel, QCheckBox, QMessageBox, QTableWidgetItem
    from PySide6.QtCore import Qt, Signal
    from models import User  # Assuming User model can be imported
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False
    # Placeholders for type hinting if PySide6 is not available
    class QWidget: pass
    class QTableWidget: pass
    class QLineEdit: pass
    class QComboBox: pass
    class QPushButton: pass
    class QLabel: pass
    class QCheckBox: pass
    class QMessageBox:
        Information = 1
        Warning = 2
        Critical = 3
        @staticmethod
        def information(*args): pass
        @staticmethod
        def warning(*args): pass
        @staticmethod
        def critical(*args): pass
    class QTableWidgetItem:
        def __init__(self, text=""): self.text_data = text
        def text(self): return self.text_data
        def data(self, role): return None
        def setData(self, role, value): pass

    class Signal:
        def connect(self, slot): pass
        def emit(self, *args, **kwargs): pass

    class User: # Basic placeholder
        ROLES = ["EndUser", "Technician", "Engineer", "TechManager", "EngManager"]
        def __init__(self, user_id="uid", username="uname", role="EndUser", is_active=True, force_password_reset=False, password_hash=None):
            self.user_id = user_id
            self.username = username
            self.role = role
            self.is_active = is_active
            self.force_password_reset = force_password_reset
            self.password_hash = password_hash


# Assuming ui_user_management_view.py contains UserManagementView
from ui_user_management_view import UserManagementView

# Dummy manager user for instantiating the view
DUMMY_MANAGER_USER = User(user_id="manager001", username="mgr", role="TechManager")
# Define User.ROLES here if not available from imported User model during test runtime
USER_ROLES_FALLBACK = ["EndUser", "Technician", "Engineer", "TechManager", "EngManager"]


class TestUserManagementViewLogic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if PYSIDE_AVAILABLE:
            from PySide6.QtWidgets import QApplication
            cls.app = QApplication.instance() or QApplication([])
        else:
            cls.app = None # type: ignore

    def setUp(self):
        self.mock_main_window = MagicMock() # Mock the main window or parent

        # Patch user_manager functions
        self.patcher_list_users = patch('ui_user_management_view.user_manager.list_all_users')
        self.mock_list_all_users = self.patcher_list_users.start()

        self.patcher_create_user = patch('ui_user_management_view.user_manager.create_user')
        self.mock_create_user = self.patcher_create_user.start()

        self.patcher_update_profile = patch('ui_user_management_view.user_manager.update_user_profile')
        self.mock_update_user_profile = self.patcher_update_profile.start()

        self.patcher_set_password = patch('ui_user_management_view.user_manager.set_user_password')
        self.mock_set_user_password = self.patcher_set_password.start()

        # Patch QMessageBox
        self.patcher_qmessagebox = patch('PySide6.QtWidgets.QMessageBox') # Target where it's USED
        self.mock_qmessagebox = self.patcher_qmessagebox.start()

        # Patch User model's ROLES if necessary (e.g. if models.User is not fully available)
        # If User.ROLES is directly accessed as User.ROLES in the view's __init__ for populating a combo box
        if not PYSIDE_AVAILABLE or not hasattr(User, 'ROLES'): # Simple check
            self.patcher_user_roles = patch('models.User.ROLES', USER_ROLES_FALLBACK)
            self.patcher_user_roles.start()


        self.view = UserManagementView(DUMMY_MANAGER_USER, parent=self.mock_main_window)

        # Mock UI elements of UserManagementView
        self.view.users_table = MagicMock(spec=QTableWidget)
        self.view.username_filter_edit = MagicMock(spec=QLineEdit)
        self.view.role_filter_combo = MagicMock(spec=QComboBox)
        # ... other filter inputs like is_active_filter_combo, force_reset_filter_combo
        self.view.is_active_filter_combo = MagicMock(spec=QComboBox)
        self.view.force_reset_filter_combo = MagicMock(spec=QComboBox)


        # Detail form inputs
        self.view.username_edit = MagicMock(spec=QLineEdit)
        self.view.password_edit = MagicMock(spec=QLineEdit)
        self.view.confirm_password_edit = MagicMock(spec=QLineEdit)
        self.view.role_combo = MagicMock(spec=QComboBox)
        self.view.is_active_checkbox = MagicMock(spec=QCheckBox)
        self.view.force_reset_checkbox = MagicMock(spec=QCheckBox)
        self.view.message_label = MagicMock(spec=QLabel)

        # Buttons
        self.view.save_button = MagicMock(spec=QPushButton)
        self.view.add_new_button = MagicMock(spec=QPushButton)
        self.view.refresh_button = MagicMock(spec=QPushButton)

        # Simulate that QTableWidgetItem can be created and data set/retrieved
        if not PYSIDE_AVAILABLE:
            # If we are in placeholder mode, make QTableWidgetItem usable
            patch_qtablewidgetitem = patch('PySide6.QtWidgets.QTableWidgetItem', QTableWidgetItem)
            self.mock_qtablewidgetitem_class = patch_qtablewidgetitem.start()


    def tearDown(self):
        self.patcher_list_users.stop()
        self.patcher_create_user.stop()
        self.patcher_update_profile.stop()
        self.patcher_set_password.stop()
        self.patcher_qmessagebox.stop()
        if hasattr(self, 'patcher_user_roles'):
            self.patcher_user_roles.stop()
        if hasattr(self, 'mock_qtablewidgetitem_class'):
            self.mock_qtablewidgetitem_class.stop()
        patch.stopall()


    def _create_dummy_user_obj(self, user_id="id1", username="test", role="EndUser", is_active=True, force_reset=False):
        # This helper should ideally use the actual User class from models
        # For isolation, we can mock it if needed, but here we assume User can be instantiated.
        user = User(username=username, role=role, is_active=is_active, force_password_reset=force_reset)
        user.user_id = user_id
        return user

    def test_load_and_display_users_populates_table(self):
        sample_users = [
            self._create_dummy_user_obj("id1", "userA", "Engineer", True, False),
            self._create_dummy_user_obj("id2", "userB", "Technician", False, True),
        ]
        self.mock_list_all_users.return_value = sample_users

        # Mock filter values
        self.view.username_filter_edit.text.return_value = "test_filter_user"
        self.view.role_filter_combo.currentData.return_value = "test_filter_role"
        self.view.is_active_filter_combo.currentData.return_value = "True"
        self.view.force_reset_filter_combo.currentData.return_value = "False"


        self.view._load_and_display_users()

        expected_filters = {
            "username": "test_filter_user",
            "role": "test_filter_role",
            "is_active": True,
            "force_password_reset": False
        }
        self.mock_list_all_users.assert_called_once_with(filters=expected_filters, sort_by='username', reverse_sort=False)

        self.view.users_table.setRowCount.assert_called_with(2)
        # Check if setItem is called for each cell (simplified check for first user, first cell)
        self.view.users_table.setItem.assert_any_call(0, 0, unittest.mock.ANY) # Username
        item_arg = self.view.users_table.setItem.call_args_list[0][0][2] # Get the QTableWidgetItem
        if PYSIDE_AVAILABLE: # Actual QTableWidgetItem has text()
             self.assertEqual(item_arg.text(), "userA")
        else: # Placeholder has text_data
             self.assertEqual(item_arg.text_data, "userA")


    def test_handle_user_selection_populates_form(self):
        selected_row = 0
        user_id_item = MagicMock() # QTableWidgetItem
        user_id_item.data.return_value = "id1" # Store user_id in Qt.UserRole

        # Mock table to return the item when item(row, col) is called
        self.view.users_table.item.return_value = user_id_item

        user_obj = self._create_dummy_user_obj("id1", "selectedUser", "Engineer", False, True)
        self.view.users_list_data = {"id1": user_obj} # Populate internal cache

        # Mock combo box findText
        self.view.role_combo.findText = MagicMock(return_value=1) # Assume "Engineer" is at index 1

        self.view._set_form_for_new_user = MagicMock() # Mock this helper

        self.view.handle_user_selection()

        self.view.username_edit.setText.assert_called_with("selectedUser")
        self.view.role_combo.setCurrentIndex.assert_called_with(1)
        self.view.is_active_checkbox.setChecked.assert_called_with(False)
        self.view.force_reset_checkbox.setChecked.assert_called_with(True)
        self.view.password_edit.clear.assert_called_once()
        self.view.confirm_password_edit.clear.assert_called_once()
        self.view._set_form_for_new_user.assert_called_once_with(False)
        self.assertEqual(self.view.selected_user_id, "id1")


    def test_handle_save_changes_new_user_success(self):
        self.view.selected_user_id = None # New user mode
        self.view.username_edit.text.return_value = "newbie"
        self.view.password_edit.text.return_value = "Password123"
        self.view.confirm_password_edit.text.return_value = "Password123"
        self.view.role_combo.currentData.return_value = "EndUser" # role_name
        self.view.is_active_checkbox.isChecked.return_value = True
        self.view.force_reset_checkbox.isChecked.return_value = False

        new_user_obj = self._create_dummy_user_obj(username="newbie", role="EndUser")
        self.mock_create_user.return_value = new_user_obj

        self.view._load_and_display_users = MagicMock() # Mock refresh

        self.view.handle_save_changes()

        self.mock_create_user.assert_called_once_with(
            username="newbie",
            password="Password123",
            role="EndUser",
            is_active=True,
            force_password_reset=False
        )
        self.mock_qmessagebox.information.assert_called_once_with(self.view, "Success", "User newbie created successfully.")
        self.view._load_and_display_users.assert_called_once()


    def test_handle_save_changes_new_user_password_mismatch(self):
        self.view.selected_user_id = None # New user mode
        self.view.username_edit.text.return_value = "newbie"
        self.view.password_edit.text.return_value = "Password123"
        self.view.confirm_password_edit.text.return_value = "PasswordMismatch"
        # ... other fields don't matter for this test path

        self.view.handle_save_changes()

        self.mock_qmessagebox.warning.assert_called_once_with(self.view, "Input Error", "Passwords do not match.")
        self.mock_create_user.assert_not_called()

    def test_handle_save_changes_new_user_creation_fails(self):
        self.view.selected_user_id = None
        self.view.username_edit.text.return_value = "newbie"
        self.view.password_edit.text.return_value = "Password123"
        self.view.confirm_password_edit.text.return_value = "Password123"
        self.view.role_combo.currentData.return_value = "EndUser"
        self.view.is_active_checkbox.isChecked.return_value = True
        self.view.force_reset_checkbox.isChecked.return_value = False

        self.mock_create_user.return_value = None # Simulate failure in manager

        self.view.handle_save_changes()

        self.mock_qmessagebox.critical.assert_called_once_with(self.view, "Error", "Failed to create user newbie.")
        self.mock_create_user.assert_called_once() # It was called


    def test_handle_save_changes_edit_user_success(self):
        user_id_to_edit = "existing_uid"
        self.view.selected_user_id = user_id_to_edit

        self.view.username_edit.text.return_value = "edited_username" # Assuming username can be edited, though usually not.
                                                                    # If not, this line and related assert can be removed.
        self.view.role_combo.currentData.return_value = "Technician"
        self.view.is_active_checkbox.isChecked.return_value = False
        self.view.force_reset_checkbox.isChecked.return_value = True

        # Password fields are empty, meaning no password change intended
        self.view.password_edit.text.return_value = ""
        self.view.confirm_password_edit.text.return_value = ""

        updated_user_obj = self._create_dummy_user_obj(user_id=user_id_to_edit, username="edited_username",
                                                      role="Technician", is_active=False, force_reset=True)
        self.mock_update_user_profile.return_value = updated_user_obj
        self.view._load_and_display_users = MagicMock()

        self.view.handle_save_changes()

        self.mock_update_user_profile.assert_called_once_with(
            user_id=user_id_to_edit,
            role="Technician",
            is_active=False,
            force_password_reset=True
            # username="edited_username" # if username is updatable
        )
        self.mock_set_user_password.assert_not_called() # No password change
        self.mock_qmessagebox.information.assert_called_once_with(self.view, "Success", f"User profile for {updated_user_obj.username} updated successfully.")
        self.view._load_and_display_users.assert_called_once()

    def test_handle_save_changes_edit_user_with_password_change_success(self):
        user_id_to_edit = "existing_uid_pass_change"
        self.view.selected_user_id = user_id_to_edit

        # Assume other fields are not changed for simplicity, focus on password
        self.view.role_combo.currentData.return_value = "EndUser" # Original role
        self.view.is_active_checkbox.isChecked.return_value = True # Original active
        self.view.force_reset_checkbox.isChecked.return_value = False # Original reset

        self.view.password_edit.text.return_value = "NewPassword456"
        self.view.confirm_password_edit.text.return_value = "NewPassword456"

        # Mock update_user_profile to return a user (even if no profile fields changed)
        # This is because the flow might call update_user_profile first for non-password fields.
        # Or, the logic might be smart enough to only call set_password.
        # For this test, assume profile update is called, then password set.
        original_user_obj = self._create_dummy_user_obj(user_id=user_id_to_edit, username="user_pass_change")
        self.mock_update_user_profile.return_value = original_user_obj
        self.mock_set_user_password.return_value = True # Password change succeeds

        self.view._load_and_display_users = MagicMock()

        self.view.handle_save_changes()

        self.mock_update_user_profile.assert_called_once() # Called for other profile data
        self.mock_set_user_password.assert_called_once_with(user_id_to_edit, "NewPassword456")

        # Check for two success messages or one combined message
        # Current implementation in many UIs would show one for profile, one for password.
        # Or, a single "Changes saved" message. Let's assume two for now.
        self.mock_qmessagebox.information.assert_any_call(self.view, "Success", f"User profile for {original_user_obj.username} updated successfully.")
        self.mock_qmessagebox.information.assert_any_call(self.view, "Success", f"Password for {original_user_obj.username} updated successfully.")
        self.view._load_and_display_users.assert_called_once()


    def test_handle_save_changes_edit_user_password_change_fails(self):
        user_id_to_edit = "existing_uid_pass_fail"
        self.view.selected_user_id = user_id_to_edit

        self.view.password_edit.text.return_value = "NewPassword789"
        self.view.confirm_password_edit.text.return_value = "NewPassword789"

        # Assume profile update part succeeds or is not the focus
        user_obj = self._create_dummy_user_obj(user_id=user_id_to_edit, username="user_pass_fail")
        self.mock_update_user_profile.return_value = user_obj
        self.mock_set_user_password.return_value = False # Password change fails

        self.view.handle_save_changes()

        self.mock_set_user_password.assert_called_once_with(user_id_to_edit, "NewPassword789")
        self.mock_qmessagebox.critical.assert_called_once_with(self.view, "Error", f"Failed to update password for {user_obj.username}.")
        # Depending on logic, _load_and_display_users might still be called if profile update succeeded.


if __name__ == '__main__':
    if not PYSIDE_AVAILABLE:
        print("Skipping TestUserManagementViewLogic: PySide6 components not available or not fully mocked.")
    else:
        unittest.main()
