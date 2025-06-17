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


        # Detail form inputs - using actual names from UserManagementView
        self.view.detail_username_edit = MagicMock(spec=QLineEdit)
        self.view.detail_new_password_edit = MagicMock(spec=QLineEdit) # Corrected name
        self.view.detail_confirm_password_edit = MagicMock(spec=QLineEdit) # Corrected name
        self.view.detail_role_combo = MagicMock(spec=QComboBox) # Corrected name
        self.view.detail_is_active_check = MagicMock(spec=QCheckBox) # Corrected name
        self.view.detail_force_reset_check = MagicMock(spec=QCheckBox) # Corrected name

        # New fields
        self.view.phone_edit = MagicMock(spec=QLineEdit)
        self.view.email_edit = MagicMock(spec=QLineEdit)
        self.view.department_edit = MagicMock(spec=QLineEdit)

        self.view.message_label = MagicMock(spec=QLabel)
        self.view.detail_user_id_label = MagicMock(spec=QLabel) # For user ID display
        self.view.password_group_widget = MagicMock(spec=QWidget) # For visibility toggling

        # Buttons (assuming these are the correct names from the view)
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
        self.view.username_search_edit = MagicMock(spec=QLineEdit) # Corrected name for filter input
        self.view.username_search_edit.text.return_value = "test_filter_user"
        self.view.role_filter_combo.currentText.return_value = "test_filter_role" # Use currentText
        self.view.active_filter_combo = MagicMock(spec=QComboBox) # Corrected name for filter input
        self.view.active_filter_combo.currentText.return_value = "Active" # Use "Active" as in view
        self.view.force_reset_filter_combo.currentText.return_value = "No" # Use "No" as in view


        self.view._load_and_display_users()

        expected_filters = {
            "username": "test_filter_user",
            "role": "test_filter_role",
            "is_active": True, # "Active" maps to True
            "force_password_reset": False # "No" maps to False
        }
        # Allow for sort_by to be any string, and reverse_sort any boolean as they have defaults
        self.mock_list_all_users.assert_called_once_with(filters=expected_filters, sort_by=unittest.mock.ANY, reverse_sort=unittest.mock.ANY)

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
        # Adjust how users_list_data is structured to match the view (list of User objects)
        self.view.users_list_data = [user_obj]

        # Mock combo box findText (used by setCurrentText indirectly if that's how it works)
        # More directly, the view uses setCurrentText. We can check that.
        # self.view.detail_role_combo.findText = MagicMock(return_value=1)
        self.view.detail_role_combo.setCurrentText = MagicMock()


        # _set_form_for_new_user is called internally, ensure it's not breaking things or mock it
        # For this test, we are interested in the population part, so we can allow _set_form_for_new_user to be called.
        # self.view._set_form_for_new_user = MagicMock()

        self.view.handle_user_selection() # This method will call _set_form_for_new_user(False)

        self.view.detail_username_edit.setText.assert_called_with("selectedUser")
        self.view.detail_role_combo.setCurrentText.assert_called_with("Engineer")
        self.view.detail_is_active_check.setChecked.assert_called_with(False)
        self.view.detail_force_reset_check.setChecked.assert_called_with(True)
        # Password fields are not cleared in handle_user_selection, but in _set_form_for_new_user
        # self.view.detail_new_password_edit.clear.assert_called_once()
        # self.view.detail_confirm_password_edit.clear.assert_called_once()
        self.assertEqual(self.view.selected_user_id, "id1")


    def test_handle_save_changes_new_user_success(self):
        self.view.selected_user_id = None # New user mode
        self.view.detail_username_edit.text.return_value = "newbie" # Corrected mock name
        self.view.detail_new_password_edit.text.return_value = "Password123"  # Corrected mock name
        self.view.detail_confirm_password_edit.text.return_value = "Password123" # Corrected mock name
        self.view.detail_role_combo.currentText.return_value = "EndUser" # Corrected mock name, use currentText
        self.view.detail_is_active_check.isChecked.return_value = True # Corrected mock name
        self.view.detail_force_reset_check.isChecked.return_value = False # Corrected mock name

        # Populate new fields for this test
        self.view.phone_edit.text.return_value = "123-456-7890"
        self.view.email_edit.text.return_value = "newbie@example.com"
        self.view.department_edit.text.return_value = "Sales"

        new_user_obj = self._create_dummy_user_obj(username="newbie", role="EndUser")
        # Simulate that the created user object would also have these fields
        new_user_obj.phone = "123-456-7890"
        new_user_obj.email = "newbie@example.com"
        new_user_obj.department = "Sales"
        self.mock_create_user.return_value = new_user_obj


        self.view._load_and_display_users = MagicMock() # Mock refresh
        self.view._set_form_for_new_user = MagicMock() # Mock this to check it's called

        self.view.handle_save_changes()

        self.mock_create_user.assert_called_once_with(
            "newbie", # username
            "Password123", # password
            "EndUser", # role
            is_active=True,
            force_password_reset=False,
            phone="123-456-7890",
            email="newbie@example.com",
            department="Sales"
        )
        self.mock_qmessagebox.information.assert_called_once_with(self.view, "Success", "User newbie created successfully.")
        self.view._load_and_display_users.assert_called_once()
        self.view._set_form_for_new_user.assert_called_once_with(True) # Reset form after creation

    def test_handle_save_changes_create_user_with_empty_new_fields(self):
        self.view.selected_user_id = None # New user mode
        self.view.detail_username_edit.text.return_value = "basicuser"
        self.view.detail_new_password_edit.text.return_value = "Password123"
        self.view.detail_confirm_password_edit.text.return_value = "Password123"
        self.view.detail_role_combo.currentText.return_value = "EndUser"
        self.view.detail_is_active_check.isChecked.return_value = True
        self.view.detail_force_reset_check.isChecked.return_value = False
        # Ensure new fields are empty
        self.view.phone_edit.text.return_value = ""
        self.view.email_edit.text.return_value = "  " # Test stripping
        self.view.department_edit.text.return_value = ""

        new_user_obj = self._create_dummy_user_obj(username="basicuser", role="EndUser")
        self.mock_create_user.return_value = new_user_obj

        self.view._load_and_display_users = MagicMock()
        self.view._set_form_for_new_user = MagicMock()

        self.view.handle_save_changes()

        self.mock_create_user.assert_called_once_with(
            "basicuser",
            "Password123",
            "EndUser",
            is_active=True,
            force_password_reset=False,
            phone=None,
            email=None, # Stripped and then None
            department=None
        )
        self.mock_qmessagebox.information.assert_called_once_with(self.view, "Success", "User basicuser created successfully.")


    def test_handle_save_changes_new_user_password_mismatch(self): # Existing test, ensure it's fine
        self.view.selected_user_id = None # New user mode
        self.view.detail_username_edit.text.return_value = "newbie"
        self.view.detail_new_password_edit.text.return_value = "Password123"
        self.view.detail_confirm_password_edit.text.return_value = "PasswordMismatch"
        # ... other fields don't matter for this test path

        self.view.handle_save_changes()

        self.mock_qmessagebox.warning.assert_called_once_with(self.view, "Input Error", "Passwords do not match.")
        self.mock_create_user.assert_not_called()

    def test_handle_save_changes_new_user_creation_fails(self):
        self.view.selected_user_id = None
        self.view.detail_username_edit.text.return_value = "newbie"
        self.view.detail_new_password_edit.text.return_value = "Password123"
        self.view.detail_confirm_password_edit.text.return_value = "Password123"
        self.view.detail_role_combo.currentText.return_value = "EndUser"
        self.view.detail_is_active_check.isChecked.return_value = True
        self.view.detail_force_reset_check.isChecked.return_value = False
        # Mock new fields as empty
        self.view.phone_edit.text.return_value = ""
        self.view.email_edit.text.return_value = ""
        self.view.department_edit.text.return_value = ""


        self.mock_create_user.side_effect = ValueError("Creation failed in manager") # Simulate manager error

        self.view.handle_save_changes()

        # QMessageBox.critical is called by the general exception handler in the view
        self.mock_qmessagebox.critical.assert_called_once_with(self.view, "Validation Error", "Creation failed in manager")
        self.mock_create_user.assert_called_once() # It was called


    def test_handle_save_changes_edit_user_success(self):
        user_id_to_edit = "existing_uid"
        self.view.selected_user_id = user_id_to_edit

        self.view.detail_username_edit.text.return_value = "existing_uid" # Username edit is readOnly, so it's original
        self.view.detail_role_combo.currentText.return_value = "Technician"
        self.view.detail_is_active_check.isChecked.return_value = False
        self.view.detail_force_reset_check.isChecked.return_value = True
        # Mock new fields
        self.view.phone_edit.text.return_value = "123-phone"
        self.view.email_edit.text.return_value = "edit@example.com"
        self.view.department_edit.text.return_value = "EditedDept"


        # Password fields are not relevant for this part of edit profile (handled by force_reset or separate dialog)
        # self.view.detail_new_password_edit.text.return_value = ""
        # self.view.detail_confirm_password_edit.text.return_value = ""

        updated_user_obj = self._create_dummy_user_obj(user_id=user_id_to_edit, username="existing_uid",
                                                      role="Technician", is_active=False, force_reset=True)
        # Add new fields to the returned obj for message for this specific test
        updated_user_obj.phone = "123-phone"
        updated_user_obj.email = "edit@example.com"
        updated_user_obj.department = "EditedDept"
        self.mock_update_user_profile.return_value = updated_user_obj

        self.view._load_and_display_users = MagicMock()

        self.view.handle_save_changes()

        expected_payload = {
            "role": "Technician",
            "is_active": False,
            "force_password_reset": True,
            "phone": "123-phone", # Value from the mocked QLineEdit
            "email": "edit@example.com",   # Value from the mocked QLineEdit
            "department": "EditedDept" # Value from the mocked QLineEdit
        }
        self.mock_update_user_profile.assert_called_once_with(user_id_to_edit, **expected_payload)
        self.mock_qmessagebox.information.assert_called_once_with(self.view, "Success", "User 'existing_uid' updated.")
        self.view._load_and_display_users.assert_called_once()

    def test_handle_save_changes_edit_user_clears_one_new_field(self):
        user_id_to_edit = "existing_uid_clear_field"
        self.view.selected_user_id = user_id_to_edit

        self.view.detail_username_edit.text.return_value = "existing_uid_clear_field"
        self.view.detail_role_combo.currentText.return_value = "EndUser"
        self.view.detail_is_active_check.isChecked.return_value = True
        self.view.detail_force_reset_check.isChecked.return_value = False
        self.view.phone_edit.text.return_value = "" # User clears this field
        self.view.email_edit.text.return_value = "original@example.com" # This one remains
        self.view.department_edit.text.return_value = "OriginalDept"   # This one remains

        updated_user_obj = self._create_dummy_user_obj(user_id=user_id_to_edit, username="existing_uid_clear_field")
        updated_user_obj.email = "original@example.com" # Reflects final state
        updated_user_obj.department = "OriginalDept" # Reflects final state
        # phone will be None

        self.mock_update_user_profile.return_value = updated_user_obj
        self.view._load_and_display_users = MagicMock()
        self.view.handle_save_changes()

        expected_payload = {
            "role": "EndUser",
            "is_active": True,
            "force_password_reset": False,
            "phone": None, # Expected to be None as input was empty
            "email": "original@example.com",
            "department": "OriginalDept"
        }
        self.mock_update_user_profile.assert_called_once_with(user_id_to_edit, **expected_payload)
        self.mock_qmessagebox.information.assert_called_once_with(self.view, "Success", "User 'existing_uid_clear_field' updated.")

    def test_edit_user_populates_new_fields(self):
        user_id_to_select = "uid_with_details"
        user_obj = self._create_dummy_user_obj(user_id_to_select, "UserWithDetails", "Engineer")
        user_obj.phone = "777-7777"
        user_obj.email = "details@example.com"
        user_obj.department = "R&D"
        self.view.users_list_data = [user_obj]

        # Simulate table selection
        mock_item = MagicMock(spec=QTableWidgetItem)
        mock_item.data.return_value = user_id_to_select
        self.view.users_table.selectedItems.return_value = [mock_item] # Must be a list
        self.view.users_table.currentRow.return_value = 0
        self.view.users_table.item.return_value = mock_item # For user_id_item

        self.view.handle_user_selection()

        self.view.phone_edit.setText.assert_called_with("777-7777")
        self.view.email_edit.setText.assert_called_with("details@example.com")
        self.view.department_edit.setText.assert_called_with("R&D")

    def test_edit_user_populates_new_fields_empty_or_none(self):
        user_id_to_select = "uid_no_details"
        user_obj = self._create_dummy_user_obj(user_id_to_select, "UserNoDetails", "EndUser")
        user_obj.phone = None
        user_obj.email = "" # Test with empty string
        user_obj.department = None
        self.view.users_list_data = [user_obj]

        mock_item = MagicMock(spec=QTableWidgetItem)
        mock_item.data.return_value = user_id_to_select
        self.view.users_table.selectedItems.return_value = [mock_item]
        self.view.users_table.currentRow.return_value = 0
        self.view.users_table.item.return_value = mock_item

        self.view.handle_user_selection()

        self.view.phone_edit.setText.assert_called_with("") # None becomes empty string
        self.view.email_edit.setText.assert_called_with("") # Empty string remains empty
        self.view.department_edit.setText.assert_called_with("") # None becomes empty string

    def test_new_fields_are_present(self): # Existing test, should still pass
        self.assertIsInstance(self.view.phone_edit, QLineEdit)
        self.assertIsInstance(self.view.email_edit, QLineEdit)
        self.assertIsInstance(self.view.department_edit, QLineEdit)

if __name__ == '__main__':
    if not PYSIDE_AVAILABLE:
        print("Skipping TestUserManagementViewLogic: PySide6 components not available or not fully mocked.")
    else:
        unittest.main()

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
