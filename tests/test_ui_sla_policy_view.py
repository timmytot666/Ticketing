import unittest
from unittest.mock import patch, MagicMock, PropertyMock, call
import sys
import os
import uuid # For checking generated policy_id structure

# Adjust path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import User
from ui_sla_policy_view import SLAPolicyView

from PySide6.QtWidgets import QLineEdit, QComboBox, QSpinBox, QTableWidget, QLabel, QMessageBox, QTableWidgetItem
from PySide6.QtCore import Qt # For Qt.UserRole

# DummyUser for testing
class DummyUserForSLAPolicyTest(User):
    def __init__(self, username: str, role: User.ROLES, user_id_val: str = "test_sla_uid"): # type: ignore
        if User.ROLES is None or not hasattr(User.ROLES, '__args__') or role not in User.ROLES.__args__: # type: ignore
            class TempRoles: __args__ = ('EngManager', 'TechManager', 'EndUser') # Ensure role is valid
            User.ROLES = TempRoles #type: ignore
            if role not in User.ROLES.__args__: raise ValueError(f"Invalid role '{role}'") # type: ignore
        self.user_id = user_id_val; self.username = username; self.role: User.ROLES = role # type: ignore
        self._password_hash: Optional[str] = None
    def set_password(self, password): self._password_hash = f"dummy_{password}" # pragma: no cover
    def check_password(self, password): return self._password_hash == f"dummy_{password}" # pragma: no cover

@patch('ui_sla_policy_view.save_sla_policies')
@patch('ui_sla_policy_view.get_sla_policies')
class TestSLAPolicyViewLogic(unittest.TestCase):

    @patch('ui_sla_policy_view.QApplication.instance') # Avoids "QApplication instance not found"
    def setUp(self, mock_qapp_instance, mock_get_policies, mock_save_policies): # Mocks passed by decorator order
        if User.ROLES is None: # Ensure User.ROLES is populated for DummyUser
            class TempRoles: __args__ = ('EngManager',)
            User.ROLES = TempRoles #type: ignore

        self.mock_get_policies = mock_get_policies
        self.mock_save_policies = mock_save_policies

        self.dummy_user = DummyUserForSLAPolicyTest("sla_manager", "EngManager")

        # To test logic without full GUI, we prevent actual QWidget setup if it causes issues
        # and mock the UI elements the logic interacts with.
        with patch.object(SLAPolicyView, 'setLayout', MagicMock()):
            self.view = SLAPolicyView(current_user=self.dummy_user)

        # Mock UI elements accessed by the methods under test
        self.view.policies_table = MagicMock(spec=QTableWidget)
        self.view.policy_id_label = MagicMock(spec=QLabel)
        self.view.name_edit = MagicMock(spec=QLineEdit)
        self.view.priority_combo = MagicMock(spec=QComboBox)
        self.view.type_combo = MagicMock(spec=QComboBox)
        self.view.response_hours_spin = MagicMock(spec=QSpinBox)
        self.view.resolve_hours_spin = MagicMock(spec=QSpinBox)
        self.view.delete_button = MagicMock(spec=QPushButton)

        # Mock QMessageBox for confirmation dialogs and info/warning messages
        self.mock_qmessagebox_patcher = patch('ui_sla_policy_view.QMessageBox')
        self.mock_qmessagebox = self.mock_qmessagebox_patcher.start()
        self.addCleanup(self.mock_qmessagebox_patcher.stop)


    def test_load_and_display_policies_populates_table(self, mock_get_policies, mock_save_policies):
        sample_policies = [
            {'policy_id': '1', 'name': 'P1', 'priority': 'High', 'ticket_type': 'IT', 'response_time_hours': 1, 'resolution_time_hours': 4},
            {'policy_id': '2', 'name': 'P2', 'priority': 'Medium', 'ticket_type': 'All', 'response_time_hours': 2, 'resolution_time_hours': 8}
        ]
        mock_get_policies.return_value = sample_policies

        # Mock clear_form_and_selection as it's called at the end of _load_and_display_policies
        with patch.object(self.view, 'clear_form_and_selection') as mock_clear_form:
            self.view._load_and_display_policies()

        self.assertEqual(self.view.policies, sample_policies) # Check policies are stored
        self.view.policies_table.setRowCount.assert_called_with(len(sample_policies))
        # Check if setItem was called for a few key items (e.g., first row, name and ID in UserRole)
        self.view.policies_table.setItem.assert_any_call(0, self.view.COLUMN_NAME, unittest.mock.ANY)
        # Verify UserRole data for the first item of the first policy
        args_list_item_0_0 = self.view.policies_table.setItem.call_args_list[0][0] # First call, args part
        table_widget_item_0_0 = args_list_item_0_0[2] # The QTableWidgetItem
        self.assertEqual(table_widget_item_0_0.data(Qt.UserRole), '1')
        mock_clear_form.assert_called_once()


    def test_handle_policy_selection_populates_form(self, mock_get_policies, mock_save_policies):
        policy1 = {'policy_id': 'id1', 'name': 'Policy One', 'priority': 'High', 'ticket_type': 'IT',
                   'response_time_hours': 1.0, 'resolution_time_hours': 8.0}
        self.view.policies = [policy1] # Pre-populate internal list

        mock_item = MagicMock(spec=QTableWidgetItem)
        mock_item.data.return_value = 'id1' # This is what .data(Qt.UserRole) should return

        self.view.policies_table.selectedItems.return_value = [mock_item] # Simulate one item selected
        self.view.policies_table.currentRow.return_value = 0 # Simulate first row selected
        self.view.policies_table.item.return_value = mock_item # item(row, col_name) returns the item with data

        self.view.handle_policy_selection()

        self.view.policy_id_label.setText.assert_called_with("ID: id1")
        self.view.name_edit.setText.assert_called_with("Policy One")
        self.view.priority_combo.setCurrentText.assert_called_with("High")
        self.view.type_combo.setCurrentText.assert_called_with("IT")
        self.view.response_hours_spin.setValue.assert_called_with(1)
        self.view.resolve_hours_spin.setValue.assert_called_with(8)
        self.view.delete_button.setEnabled.assert_called_with(True)
        self.assertEqual(self.view.selected_policy_id, 'id1')

    def test_handle_policy_selection_clears_if_no_selection(self, mock_get_policies, mock_save_policies):
        self.view.policies_table.selectedItems.return_value = [] # No items selected
        with patch.object(self.view, 'clear_form_and_selection') as mock_clear_form:
            self.view.handle_policy_selection()
        mock_clear_form.assert_called_once()


    def test_handle_save_new_policy(self, mock_get_policies, mock_save_policies):
        self.view.selected_policy_id = None # Ensure it's a new policy
        self.view.name_edit.text.return_value = "New Policy Alpha"
        self.view.priority_combo.currentText.return_value = "Low"
        self.view.type_combo.currentText.return_value = "Facilities"
        self.view.response_hours_spin.value.return_value = 12
        self.view.resolve_hours_spin.value.return_value = 72

        mock_save_policies.return_value = True # Simulate successful save

        with patch.object(self.view, '_load_and_display_policies') as mock_load_display:
            self.view.handle_save_policy()

        mock_save_policies.assert_called_once()
        saved_policies_arg = mock_save_policies.call_args[0][0] # Policies list passed to save_sla_policies
        self.assertEqual(len(saved_policies_arg), 1)
        new_policy = saved_policies_arg[0]
        self.assertTrue(new_policy['policy_id'].startswith("sla_"))
        self.assertEqual(new_policy['name'], "New Policy Alpha")

        self.mock_qmessagebox.information.assert_called_once()
        mock_load_display.assert_called_once()


    def test_handle_save_edit_existing_policy(self, mock_get_policies, mock_save_policies):
        existing_policy = {'policy_id': 'edit_id_1', 'name': 'Old Name', 'priority': 'High',
                           'ticket_type': 'IT', 'response_time_hours': 1, 'resolution_time_hours': 8}
        self.view.policies = [existing_policy] # Initial policies list
        self.view.selected_policy_id = 'edit_id_1' # Simulate this policy is selected and being edited

        self.view.name_edit.text.return_value = "Updated Name"
        self.view.priority_combo.currentText.return_value = "Medium"
        # Other fields kept same for simplicity, or can be mocked to return new values
        self.view.type_combo.currentText.return_value = existing_policy['ticket_type']
        self.view.response_hours_spin.value.return_value = existing_policy['response_time_hours']
        self.view.resolve_hours_spin.value.return_value = existing_policy['resolution_time_hours']

        mock_save_policies.return_value = True
        with patch.object(self.view, '_load_and_display_policies') as mock_load_display:
            self.view.handle_save_policy()

        mock_save_policies.assert_called_once()
        saved_policies_arg = mock_save_policies.call_args[0][0]
        self.assertEqual(len(saved_policies_arg), 1)
        updated_policy = saved_policies_arg[0]
        self.assertEqual(updated_policy['policy_id'], 'edit_id_1')
        self.assertEqual(updated_policy['name'], "Updated Name")
        self.assertEqual(updated_policy['priority'], "Medium")
        mock_load_display.assert_called_once()


    def test_handle_save_policy_validation_failure_empty_name(self, mock_get_policies, mock_save_policies):
        self.view.name_edit.text.return_value = "" # Empty name
        # Other form field mocks don't matter here as validation should catch empty name first
        self.view.priority_combo.currentText.return_value = "Low"
        # ...

        self.view.handle_save_policy()

        mock_save_policies.assert_not_called()
        self.mock_qmessagebox.warning.assert_called_once_with(self.view, "Validation Error", "Policy Name cannot be empty.")


    def test_handle_delete_policy(self, mock_get_policies, mock_save_policies):
        policy_to_delete = {'policy_id': 'del_id_1', 'name': 'To Delete', 'priority':'Low', 'ticket_type':'All', 'response_time_hours':1, 'resolution_time_hours':1}
        other_policy = {'policy_id': 'keep_id_1', 'name': 'To Keep', 'priority':'Low', 'ticket_type':'All', 'response_time_hours':1, 'resolution_time_hours':1}
        self.view.policies = [policy_to_delete, other_policy]
        self.view.selected_policy_id = 'del_id_1'

        self.mock_qmessagebox.question.return_value = QMessageBox.Yes # Simulate user confirms deletion
        mock_save_policies.return_value = True # Simulate successful save

        with patch.object(self.view, '_load_and_display_policies') as mock_load_display:
            self.view.handle_delete_policy()

        mock_save_policies.assert_called_once()
        remaining_policies_arg = mock_save_policies.call_args[0][0]
        self.assertEqual(len(remaining_policies_arg), 1)
        self.assertEqual(remaining_policies_arg[0]['policy_id'], 'keep_id_1')

        self.mock_qmessagebox.information.assert_called_once()
        mock_load_display.assert_called_once()

    def test_handle_delete_policy_no_selection(self, mock_get_policies, mock_save_policies):
        self.view.selected_policy_id = None
        self.view.handle_delete_policy()
        self.mock_qmessagebox.warning.assert_called_once_with(self.view, "No Selection", "No policy selected for deletion.")
        mock_save_policies.assert_not_called()

    def test_handle_delete_policy_user_cancels(self, mock_get_policies, mock_save_policies):
        self.view.selected_policy_id = 'some_id'
        self.view.policies = [{'policy_id': 'some_id', 'name': 'Some Policy'}]
        self.mock_qmessagebox.question.return_value = QMessageBox.No # Simulate user cancels

        self.view.handle_delete_policy()
        mock_save_policies.assert_not_called()


if __name__ == '__main__':
    unittest.main()
