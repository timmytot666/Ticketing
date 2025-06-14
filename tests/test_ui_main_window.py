import unittest
from unittest.mock import patch, MagicMock # Changed from unittest.mock.patch
import sys
import os

# Adjust path to import from parent directory if necessary
# This assumes 'tests' is a subdirectory of the project root where models.py etc. are.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import User
from ui_main_window import MainWindow # The class we are testing

# PySide6 imports are not strictly needed for these logic tests if UI elements are mocked,
# but if MainWindow instantiation itself requires QApplication, it might be.
# For now, we'll try to avoid needing QApplication for these non-GUI logic tests.

class DummyUserForTesting(User):
    """A simplified User class for testing MainWindow logic without full model dependencies."""
    def __init__(self, username: str, role: User.ROLES, user_id_val: str = "test_uid"): # type: ignore
        # Bypass User.__init__ if it has complex dependencies like werkzeug for these tests
        self.user_id = user_id_val
        self.username = username
        if User.ROLES and hasattr(User.ROLES, '__args__') and role not in User.ROLES.__args__: # type: ignore
            raise ValueError(f"Invalid role: {role}")
        self.role: User.ROLES = role # type: ignore
        self._password_hash: str = "" # Not used in these specific tests but part of User model

    def set_password(self, password): # pragma: no cover
        self._password_hash = f"dummy_hash_for_{password}"

    def check_password(self, password): # pragma: no cover
        return self._password_hash == f"dummy_hash_for_{password}"

    # Ensure User.ROLES is accessible for validation within DummyUserForTesting
    # This will be inherited if User.ROLES is a class attribute.
    # If User.ROLES is None due to fallback in models.py, we might need to define it here.
    if User.ROLES is None: # Handle case where models.User might be the fallback
        class TempRoles: __args__ = ('EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager')
        ROLES = TempRoles # type: ignore


class TestMainWindowLogic(unittest.TestCase):

    def setUp(self):
        # It's good practice to mock parts of QMainWindow that are not being tested
        # and might require a QApplication instance.
        # For testing _get_ui_config_for_role, we ideally don't need a full QMainWindow.
        # We'll create a "dummy" MainWindow instance or mock its UI methods.

        # Define a minimal set of roles if the imported User.ROLES is None (due to fallback)
        if User.ROLES is None:
             class TempRoles: __args__ = ('EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager')
             User.ROLES = TempRoles #type: ignore


    @patch.object(MainWindow, '_create_menu_bar', return_value=None)
    @patch.object(MainWindow, '_create_status_bar', return_value=None)
    @patch.object(MainWindow, '_create_central_widget', return_value=None)
    @patch.object(MainWindow, 'update_notification_indicator', return_value=None)
    def test_get_ui_config_for_role(self, mock_update_notif, mock_create_central, mock_create_status, mock_create_menu):
        """Test the _get_ui_config_for_role method for different roles."""

        # User for instantiation, role will be overridden in calls to _get_ui_config_for_role
        # Pass a valid role from User.ROLES to the constructor
        valid_role_for_init = User.ROLES.__args__[0] if User.ROLES and hasattr(User.ROLES, '__args__') else 'EndUser' #type: ignore
        user = DummyUserForTesting("testuser", role=valid_role_for_init) # type: ignore

        # MainWindow.__init__ calls setup_ui_for_role, which calls _get_ui_config_for_role.
        # So, the mocks ensure that the UI setup part of __init__ doesn't fail.
        main_window = MainWindow(user=user)

        # Test EndUser
        config_end_user = main_window._get_ui_config_for_role('EndUser')
        self.assertTrue(config_end_user['actions_enabled']['new_ticket'])
        self.assertTrue(config_end_user['actions_enabled']['my_tickets'])
        self.assertFalse(config_end_user['actions_enabled']['all_tickets'])
        self.assertFalse(config_end_user['actions_enabled']['dashboard'])
        self.assertEqual(config_end_user['target_page_widget_name'], 'end_user_page')

        # Test Technician
        config_technician = main_window._get_ui_config_for_role('Technician')
        self.assertFalse(config_technician['actions_enabled']['new_ticket']) # As per current logic
        self.assertTrue(config_technician['actions_enabled']['my_tickets'])
        self.assertTrue(config_technician['actions_enabled']['all_tickets'])
        self.assertFalse(config_technician['actions_enabled']['dashboard'])
        self.assertEqual(config_technician['target_page_widget_name'], 'technician_page')

        # Test TechManager
        config_manager = main_window._get_ui_config_for_role('TechManager')
        self.assertFalse(config_manager['actions_enabled']['new_ticket']) # As per current logic
        self.assertTrue(config_manager['actions_enabled']['my_tickets'])
        self.assertTrue(config_manager['actions_enabled']['all_tickets'])
        self.assertTrue(config_manager['actions_enabled']['dashboard'])
        self.assertEqual(config_manager['target_page_widget_name'], 'manager_page')

        # Test Unknown Role (should default)
        config_unknown = main_window._get_ui_config_for_role('UnknownRole') # type: ignore
        self.assertFalse(config_unknown['actions_enabled']['new_ticket'])
        self.assertFalse(config_unknown['actions_enabled']['my_tickets'])
        self.assertFalse(config_unknown['actions_enabled']['all_tickets'])
        self.assertFalse(config_unknown['actions_enabled']['dashboard'])
        self.assertEqual(config_unknown['target_page_widget_name'], 'welcome_page')

    @patch('ui_main_window.get_notifications_for_user') # Patch where it's used
    @patch.object(MainWindow, '_create_menu_bar', return_value=None)
    @patch.object(MainWindow, '_create_status_bar', return_value=None) # statusBar().addPermanentWidget etc.
    @patch.object(MainWindow, '_create_central_widget', return_value=None)
    def test_update_notification_indicator(self, mock_create_central, mock_create_status, mock_create_menu, mock_get_notifications):
        """Test the update_notification_indicator method."""
        valid_role_for_init = User.ROLES.__args__[0] if User.ROLES and hasattr(User.ROLES, '__args__') else 'EndUser' #type: ignore
        user = DummyUserForTesting("notifyuser", role=valid_role_for_init, user_id_val="uid_notify_test") # type: ignore

        main_window = MainWindow(user=user)
        # MainWindow.__init__ calls update_notification_indicator. Reset mock from that call.
        mock_get_notifications.reset_mock()


        # Mock the QLabel itself for setText assertion
        main_window.notification_indicator_label = MagicMock(spec=sys.modules['PySide6.QtWidgets'].QLabel)

        # Test with 3 unread notifications
        mock_get_notifications.return_value = [object(), object(), object()] # 3 dummy notifications
        main_window.update_notification_indicator()
        mock_get_notifications.assert_called_once_with(user_id="uid_notify_test", unread_only=True)
        main_window.notification_indicator_label.setText.assert_called_once_with("Unread Notifications: 3")

        # Test with 0 unread notifications
        mock_get_notifications.reset_mock()
        main_window.notification_indicator_label.setText.reset_mock() # Reset previous call
        mock_get_notifications.return_value = []
        main_window.update_notification_indicator()
        mock_get_notifications.assert_called_once_with(user_id="uid_notify_test", unread_only=True)
        main_window.notification_indicator_label.setText.assert_called_once_with("Unread Notifications: 0")

        # Test with an exception during notification fetching
        mock_get_notifications.reset_mock()
        main_window.notification_indicator_label.setText.reset_mock()
        mock_get_notifications.side_effect = Exception("Database connection error")
        with patch('builtins.print') as mock_print: # Catch the error print
            main_window.update_notification_indicator()
        mock_get_notifications.assert_called_once_with(user_id="uid_notify_test", unread_only=True)
        main_window.notification_indicator_label.setText.assert_called_once_with("Notifications: Error")
        mock_print.assert_any_call("Error updating notification indicator: Database connection error", file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
