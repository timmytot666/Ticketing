import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import sys
import os
import re # For testing link processing

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QListWidget, QDialogButtonBox, QTextEdit, QListWidgetItem, QMessageBox
from PySide6.QtCore import QUrl, Qt

from ui_ticket_detail_view import TicketDetailView, KBSearchDialog # Import both classes
from models import User, Ticket # For dummy user and ticket
from kb_article import KBArticle # For mock return types

class DummyUserForTicketDetailKBTest(User):
    def __init__(self, username="test_tech", role="Technician", user_id_val="kb_detail_uid"):
        if User.ROLES is None or not hasattr(User.ROLES, '__args__') or role not in User.ROLES.__args__: # type: ignore
            class TempRoles: __args__ = ('Technician', 'EndUser')
            User.ROLES = TempRoles #type: ignore
            if role not in User.ROLES.__args__: raise ValueError(f"Invalid role '{role}'") # type: ignore
        self.user_id = user_id_val; self.username = username; self.role: User.ROLES = role # type: ignore
        self._password_hash = None
    def set_password(self, password): self._password_hash = f"dummy_{password}"
    def check_password(self, password): return self._password_hash == f"dummy_{password}"


@patch('ui_ticket_detail_view.QApplication.instance') # Avoids "QApplication instance not found"
class TestTicketDetailViewKBLogic(unittest.TestCase):

    def setUp(self, mock_qapp_instance):
        if User.ROLES is None: # Ensure User.ROLES for DummyUser
            class TempRoles: __args__ = ('Technician',)
            User.ROLES = TempRoles #type: ignore
        self.dummy_user = DummyUserForTicketDetailKBTest()

        # Mock dependencies for TicketDetailView that are not UI elements themselves
        # These are typically manager functions or other utility functions.
        # UI elements on TicketDetailView will be mocked directly if needed.
        self.mock_kb_get_article_patcher = patch('ui_ticket_detail_view.kb_get_article')
        self.mock_kb_get_article = self.mock_kb_get_article_patcher.start()
        self.addCleanup(self.mock_kb_get_article_patcher.stop)

        # Mock methods that would create further dialogs from within the method being tested
        self.mock_show_kb_dialog_patcher = patch.object(TicketDetailView, '_show_kb_article_dialog')
        self.mock_show_kb_dialog = self.mock_show_kb_dialog_patcher.start()
        self.addCleanup(self.mock_show_kb_dialog_patcher.stop)


        with patch.object(TicketDetailView, 'setLayout', MagicMock()):
             # Patch methods called by __init__ that might cause issues if not mocked
            with patch.object(TicketDetailView, '_create_menu_bar', MagicMock()), \
                 patch.object(TicketDetailView, '_create_status_bar', MagicMock()), \
                 patch.object(TicketDetailView, '_create_central_widget', MagicMock()), \
                 patch.object(TicketDetailView, 'setup_ui_for_role', MagicMock()), \
                 patch.object(TicketDetailView, 'update_notification_indicator', MagicMock()), \
                 patch.object(TicketDetailView, '_populate_current_attachments', MagicMock()), \
                 patch.object(TicketDetailView, '_apply_role_permissions', MagicMock()):
                # Mock specific UI elements used in the logic
                self.view = TicketDetailView(current_user=self.dummy_user)

        self.view.new_comment_edit = MagicMock(spec=QTextEdit)
        self.view.comments_display = MagicMock(spec=QTextBrowser) # Changed to QTextBrowser

    def test_process_text_for_kb_links(self, mock_qapp_instance):
        text_no_link = "This is a normal comment."
        self.assertEqual(self.view.process_text_for_kb_links(text_no_link), text_no_link.replace(os.linesep, '<br/>'))

        text_one_link = "Please see [KB: VPN Guide](kb://kb_vpn_001) for help."
        expected_html_one_link = "Please see <a href=\"kb://kb_vpn_001\">VPN Guide</a> for help."
        self.assertEqual(self.view.process_text_for_kb_links(text_one_link), expected_html_one_link.replace(os.linesep, '<br/>'))

        text_multiple_links = "Link1: [KB: L1](kb://id1)). And Link2: [KB: Link Two](kb://id_two)."
        expected_html_multiple = "Link1: <a href=\"kb://id1\">L1</a>)). And Link2: <a href=\"kb://id_two\">Link Two</a>."
        self.assertEqual(self.view.process_text_for_kb_links(text_multiple_links), expected_html_multiple.replace(os.linesep, '<br/>'))

        text_malformed_start = "Text [KB: No End(kb://id1) and [KB: Good](kb://id2)"
        # Only the good link should be converted
        expected_malformed = "Text [KB: No End(kb://id1) and <a href=\"kb://id2\">Good</a>"
        self.assertEqual(self.view.process_text_for_kb_links(text_malformed_start), expected_malformed.replace(os.linesep, '<br/>'))

    @patch('ui_ticket_detail_view.KBSearchDialog') # Patch the dialog class itself
    def test_handle_link_kb_article_inserts_link(self, MockKBSearchDialog, mock_qapp_instance):
        mock_dialog_instance = MockKBSearchDialog.return_value
        mock_dialog_instance.exec.return_value = QDialog.Accepted # Simulate user clicked "Insert Link"
        mock_dialog_instance.get_selected_article_link_data.return_value = ("kb_test_id", "Test KB Article")

        self.view.handle_link_kb_article()

        MockKBSearchDialog.assert_called_once_with(self.view) # Check dialog was created with correct parent
        self.view.new_comment_edit.insertPlainText.assert_called_once_with("[KB: Test KB Article](kb://kb_test_id)\n")

    @patch('ui_ticket_detail_view.KBSearchDialog')
    def test_handle_link_kb_article_dialog_rejected(self, MockKBSearchDialog, mock_qapp_instance):
        mock_dialog_instance = MockKBSearchDialog.return_value
        mock_dialog_instance.exec.return_value = QDialog.Rejected # Simulate user clicked "Cancel"

        self.view.handle_link_kb_article()
        self.view.new_comment_edit.insertPlainText.assert_not_called()

    @patch('ui_ticket_detail_view.QMessageBox.warning')
    def test_handle_kb_link_clicked_article_found(self, mock_qmessage_warning, mock_qapp_instance):
        mock_url = MagicMock(spec=QUrl)
        mock_url.scheme.return_value = 'kb'
        mock_url.host.return_value = 'kb_article_123' # QUrl.host() for kb://article_id

        mock_kb_article = KBArticle(article_id="kb_article_123", title="Found Article", content="...", author_user_id="author")
        self.mock_kb_get_article.return_value = mock_kb_article

        self.view.handle_kb_link_clicked(mock_url)

        self.mock_kb_get_article.assert_called_once_with('kb_article_123')
        self.mock_show_kb_dialog.assert_called_once_with(mock_kb_article)
        mock_qmessage_warning.assert_not_called()


    @patch('ui_ticket_detail_view.QMessageBox.warning')
    def test_handle_kb_link_clicked_article_not_found(self, mock_qmessage_warning, mock_qapp_instance):
        mock_url = MagicMock(spec=QUrl)
        mock_url.scheme.return_value = 'kb'
        mock_url.host.return_value = 'kb_unknown_id'

        self.mock_kb_get_article.return_value = None # Simulate article not found

        self.view.handle_kb_link_clicked(mock_url)

        self.mock_kb_get_article.assert_called_once_with('kb_unknown_id')
        self.mock_show_kb_dialog.assert_not_called()
        mock_qmessage_warning.assert_called_once_with(self.view, "KB Article Not Found", "Could not find KB article with ID: kb_unknown_id")

    def test_handle_kb_link_clicked_ignores_other_schemes(self, mock_qapp_instance):
        mock_url = MagicMock(spec=QUrl)
        mock_url.scheme.return_value = 'http' # Non-kb scheme

        self.view.handle_kb_link_clicked(mock_url)

        self.mock_kb_get_article.assert_not_called()
        self.mock_show_kb_dialog.assert_not_called()


# --- Tests for KBSearchDialog logic (optional, can be part of above or separate if complex) ---
@patch('ui_ticket_detail_view.QApplication.instance')
class TestKBSearchDialogLogic(unittest.TestCase):
    def setUp(self, mock_qapp_instance):
        # Mock kb_manager.search_articles used by the dialog
        self.mock_search_articles_patcher = patch('ui_ticket_detail_view.kb_search_articles')
        self.mock_search_articles = self.mock_search_articles_patcher.start()
        self.addCleanup(self.mock_search_articles_patcher.stop)

        # Patch away QDialog's exec_ and other UI methods if they cause issues
        with patch.object(QDialog, 'show', MagicMock()), \
             patch.object(QDialog, 'setLayout', MagicMock()):
            self.dialog = KBSearchDialog() # Test with no parent for simplicity

        # Mock UI elements of the dialog
        self.dialog.search_query_edit = MagicMock(spec=QLineEdit)
        self.dialog.results_list = MagicMock(spec=QListWidget)
        self.dialog.button_box = MagicMock(spec=QDialogButtonBox)
        # Mock the actual button from the button box
        self.mock_insert_button = MagicMock(spec=QPushButton)
        self.dialog.button_box.button.return_value = self.mock_insert_button


    def test_perform_search_populates_results(self, mock_qapp_instance):
        self.dialog.search_query_edit.text.return_value = "vpn setup"
        mock_articles = [
            KBArticle(article_id="kb1", title="VPN Setup Guide", content="...", author_user_id="a"),
            KBArticle(article_id="kb2", title="Advanced VPN", content="...", author_user_id="b")
        ]
        self.mock_search_articles.return_value = mock_articles

        self.dialog.perform_search()

        self.mock_search_articles.assert_called_once_with("vpn setup", search_fields=['title', 'keywords', 'content'])
        self.dialog.results_list.clear.assert_called_once()
        self.assertEqual(self.dialog.results_list.addItem.call_count, 2)
        # Check data stored in one item
        args_item1, _ = self.dialog.results_list.addItem.call_args_list[0]
        qlistwidgetitem1 = args_item1[0]
        self.assertTrue(qlistwidgetitem1.text().startswith("VPN Setup Guide"))
        self.assertEqual(qlistwidgetitem1.data(Qt.UserRole), ("kb1", "VPN Setup Guide"))
        self.dialog.button_box.button.assert_called() # For update_button_states

    def test_perform_search_query_too_short_shows_message(self, mock_qapp_instance):
        self.dialog.search_query_edit.text.return_value = "hi"
        with patch('ui_ticket_detail_view.QMessageBox.information') as mock_msg_info:
            self.dialog.perform_search()
        mock_msg_info.assert_called_once()
        self.mock_search_articles.assert_not_called()
        self.dialog.results_list.clear.assert_called_once()

    def test_update_button_states(self, mock_qapp_instance):
        # Scenario 1: Item selected, data is valid
        mock_item_with_data = MagicMock(spec=QListWidgetItem)
        mock_item_with_data.data.return_value = ("id1", "Title1") # Valid data tuple
        self.dialog.results_list.currentItem.return_value = mock_item_with_data
        self.dialog.update_button_states()
        self.mock_insert_button.setEnabled.assert_called_with(True)

        # Scenario 2: No item selected
        self.dialog.results_list.currentItem.return_value = None
        self.dialog.update_button_states()
        self.mock_insert_button.setEnabled.assert_called_with(False)

        # Scenario 3: Item selected, but data is None (e.g. "No results" item)
        mock_item_no_data = MagicMock(spec=QListWidgetItem)
        mock_item_no_data.data.return_value = None # Invalid data (e.g. placeholder item)
        self.dialog.results_list.currentItem.return_value = mock_item_no_data
        self.dialog.update_button_states()
        self.mock_insert_button.setEnabled.assert_called_with(False)


    @patch.object(KBSearchDialog, 'accept') # Mock QDialog.accept()
    def test_accept_selection_and_close_with_selection(self, mock_accept_method, mock_qapp_instance):
        mock_item = MagicMock(spec=QListWidgetItem)
        mock_item.data.return_value = ("kb_accept_id", "Accepted Title")
        self.dialog.results_list.currentItem.return_value = mock_item

        self.dialog.accept_selection_and_close()

        self.assertEqual(self.dialog.selected_article_id, "kb_accept_id")
        self.assertEqual(self.dialog.selected_article_title, "Accepted Title")
        mock_accept_method.assert_called_once()

    @patch('ui_ticket_detail_view.QMessageBox.warning')
    @patch.object(KBSearchDialog, 'accept')
    def test_accept_selection_and_close_no_selection(self, mock_accept_method, mock_qmessage_warning, mock_qapp_instance):
        self.dialog.results_list.currentItem.return_value = None # No selection

        self.dialog.accept_selection_and_close()

        mock_qmessage_warning.assert_called_once_with(self.dialog, "No Selection", "Please select an article from the list to insert.")
        mock_accept_method.assert_not_called()
        self.assertIsNone(self.dialog.selected_article_id)


@patch('ui_ticket_detail_view.QApplication.instance')
class TestTicketDetailViewDataDisplay(unittest.TestCase):
    def setUp(self, mock_qapp_instance):
        if User.ROLES is None: # Ensure User.ROLES for DummyUser
            class TempRoles: __args__ = ('Technician', 'EndUser', 'TechManager', 'EngManager', 'Engineer') # Add all roles used
            User.ROLES = TempRoles #type: ignore

        self.dummy_current_user = DummyUserForTicketDetailKBTest(username="test_viewer", role="Technician")

        # Patch external manager calls
        self.mock_get_ticket_patcher = patch('ui_ticket_detail_view.get_ticket')
        self.mock_get_ticket = self.mock_get_ticket_patcher.start()
        self.addCleanup(self.mock_get_ticket_patcher.stop)

        self.mock_get_user_by_id_patcher = patch('ui_ticket_detail_view.get_user_by_id')
        self.mock_get_user_by_id = self.mock_get_user_by_id_patcher.start()
        self.addCleanup(self.mock_get_user_by_id_patcher.stop)

        # Mock other manager calls that might be triggered during load_ticket_data
        self.mock_get_sla_policies_patcher = patch('ui_ticket_detail_view.get_sla_policies')
        self.mock_get_sla_policies = self.mock_get_sla_policies_patcher.start()
        self.mock_get_sla_policies.return_value = [] # Default to no SLA policies
        self.addCleanup(self.mock_get_sla_policies_patcher.stop)


        # Instantiate the view, mocking UI construction that's not relevant
        # We need to allow __init__ to run to set up basic attributes.
        # However, methods that build complex UI or attach to main window can be mocked.
        with patch.object(TicketDetailView, 'setLayout', MagicMock()), \
             patch.object(TicketDetailView, '_populate_current_attachments', MagicMock()), \
             patch.object(TicketDetailView, '_apply_role_permissions', MagicMock()), \
             patch.object(TicketDetailView, '_calculate_and_display_sla_status', MagicMock()):
            self.view = TicketDetailView(current_user=self.dummy_current_user)

        # Mock the specific UI elements we will interact with or check
        # These elements are created in TicketDetailView.__init__
        # We replace them with MagicMock AFTER __init__ has run if they were created.
        # If __init__ itself is too complex, these might need to be set BEFORE __init__
        # and __init__ patched not to create them. But current structure seems to create them.

        # For comments display
        self.view.comments_display = MagicMock(spec=QTextBrowser)

        # For requester info display (these are created in TicketDetailView's __init__)
        # We can just let them be created and then check their .text() property.
        # If direct creation is an issue, they can be mocked out like comments_display.
        # For now, assume they are QLabels created by the real __init__ which runs before this mock assignment.
        # To ensure they are QLabels and exist, we can check their type or mock them more thoroughly.
        # For simplicity in this step, we'll rely on them being created by __init__ and accessible.
        # Let's ensure they are at least MagicMocks if we don't want to rely on full init.
        # The QFormLayout adds them, so they should exist as attributes on self.view
        # We will re-assign them to MagicMock to control their behavior for assertions if needed,
        # or simply use their actual instances and check their text property.
        # For now, let's assume we check the actual QLabels created by init.
        # If that fails, we will mock them explicitly.
        self.view.requester_id_label = MagicMock(spec=QLabel) # Mocked because it's set in load_ticket_data
        self.view.requester_phone_label = MagicMock(spec=QLabel)
        self.view.requester_email_label = MagicMock(spec=QLabel)
        self.view.requester_department_label = MagicMock(spec=QLabel)

        # Also other labels set in load_ticket_data
        self.view.ticket_id_label = MagicMock(spec=QLabel)
        self.view.created_at_label = MagicMock(spec=QLabel)
        self.view.updated_at_label = MagicMock(spec=QLabel)
        self.view.title_edit = MagicMock(spec=QLineEdit)
        self.view.description_edit = MagicMock(spec=QTextEdit)
        self.view.status_combo = MagicMock(spec=QComboBox)
        self.view.priority_combo = MagicMock(spec=QComboBox)
        self.view.type_combo = MagicMock(spec=QComboBox)
        self.view.assignee_edit = MagicMock(spec=QLineEdit)
        self.view.sla_policy_label = MagicMock(spec=QLabel)
        self.view.responded_at_label = MagicMock(spec=QLabel)
        self.view.response_due_label = MagicMock(spec=QLabel)
        self.view.resolution_due_label = MagicMock(spec=QLabel)
        self.view.sla_status_label = MagicMock(spec=QLabel)


    def test_comment_display_user_found(self, mock_qapp_instance):
        comment_user_id = "commenter_u1"
        comment_username = "CommenterOne"

        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.id = "T123"
        mock_ticket.requester_user_id = "req_u1" # Needed for load_ticket_data
        mock_ticket.assignee_user_id = None # Default
        mock_ticket.sla_policy_id = None # Default
        mock_ticket.comments = [
            {'user_id': comment_user_id, 'timestamp': '2023-01-01T12:00:00Z', 'text': 'Test comment 1'}
        ]
        self.mock_get_ticket.return_value = mock_ticket

        mock_comment_user = MagicMock(spec=User)
        mock_comment_user.username = comment_username
        # Let get_user_by_id return default for requester, specific for commenter
        self.mock_get_user_by_id.side_effect = lambda uid: mock_comment_user if uid == comment_user_id else None

        self.view.load_ticket_data("T123")

        # Check that comments_display.setHtml was called
        self.view.comments_display.setHtml.assert_called_once()
        html_output_call = self.view.comments_display.setHtml.call_args[0][0]

        # Assert that the username is in the HTML
        self.assertIn(comment_username, html_output_call)
        self.assertNotIn(comment_user_id, html_output_call) # Username should be there, not ID
        self.assertIn("Test comment 1", html_output_call)

    def test_comment_display_user_not_found(self, mock_qapp_instance):
        comment_user_id = "commenter_u2_unknown"

        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.id = "T124"
        mock_ticket.requester_user_id = "req_u2"
        mock_ticket.assignee_user_id = None
        mock_ticket.sla_policy_id = None
        mock_ticket.comments = [
            {'user_id': comment_user_id, 'timestamp': '2023-01-02T12:00:00Z', 'text': 'Another comment'}
        ]
        self.mock_get_ticket.return_value = mock_ticket
        self.mock_get_user_by_id.return_value = None # User not found for any ID

        self.view.load_ticket_data("T124")

        self.view.comments_display.setHtml.assert_called_once()
        html_output_call = self.view.comments_display.setHtml.call_args[0][0]

        self.assertIn(f"{comment_user_id} (Unknown)", html_output_call)
        self.assertIn("Another comment", html_output_call)

    def test_requester_info_all_details_found(self, mock_qapp_instance):
        requester_id = "req_full_details"
        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.id = "T_ReqFull"
        mock_ticket.requester_user_id = requester_id
        # Fill other necessary fields for load_ticket_data to avoid errors
        mock_ticket.assignee_user_id = None; mock_ticket.sla_policy_id = None; mock_ticket.comments = []
        self.mock_get_ticket.return_value = mock_ticket

        mock_requester_user = MagicMock(spec=User)
        mock_requester_user.username = "RequesterFull"
        mock_requester_user.phone = "555-0001"
        mock_requester_user.email = "req.full@example.com"
        mock_requester_user.department = "Requester Dept"
        self.mock_get_user_by_id.return_value = mock_requester_user

        self.view.load_ticket_data("T_ReqFull")

        self.mock_get_user_by_id.assert_called_with(requester_id) # Ensure it was called for the requester
        self.view.requester_phone_label.setText.assert_called_with("555-0001")
        self.view.requester_email_label.setText.assert_called_with("req.full@example.com")
        self.view.requester_department_label.setText.assert_called_with("Requester Dept")

    def test_requester_info_some_details_missing(self, mock_qapp_instance):
        requester_id = "req_some_details"
        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.id = "T_ReqSome"
        mock_ticket.requester_user_id = requester_id
        mock_ticket.assignee_user_id = None; mock_ticket.sla_policy_id = None; mock_ticket.comments = []
        self.mock_get_ticket.return_value = mock_ticket

        mock_requester_user = MagicMock(spec=User)
        mock_requester_user.username = "RequesterSome"
        mock_requester_user.phone = "555-0002"
        mock_requester_user.email = None # Missing email
        mock_requester_user.department = "Some Dept"
        self.mock_get_user_by_id.return_value = mock_requester_user

        self.view.load_ticket_data("T_ReqSome")

        self.view.requester_phone_label.setText.assert_called_with("555-0002")
        self.view.requester_email_label.setText.assert_called_with("N/A")
        self.view.requester_department_label.setText.assert_called_with("Some Dept")

    def test_requester_info_all_new_details_none(self, mock_qapp_instance):
        requester_id = "req_no_new_details"
        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.id = "T_ReqNoneNew"
        mock_ticket.requester_user_id = requester_id
        mock_ticket.assignee_user_id = None; mock_ticket.sla_policy_id = None; mock_ticket.comments = []
        self.mock_get_ticket.return_value = mock_ticket

        mock_requester_user = MagicMock(spec=User)
        mock_requester_user.username = "RequesterNoNew"
        mock_requester_user.phone = None
        mock_requester_user.email = None
        mock_requester_user.department = None
        self.mock_get_user_by_id.return_value = mock_requester_user

        self.view.load_ticket_data("T_ReqNoneNew")

        self.view.requester_phone_label.setText.assert_called_with("N/A")
        self.view.requester_email_label.setText.assert_called_with("N/A")
        self.view.requester_department_label.setText.assert_called_with("N/A")

    def test_requester_info_user_not_found(self, mock_qapp_instance):
        requester_id = "req_not_found"
        mock_ticket = MagicMock(spec=Ticket)
        mock_ticket.id = "T_ReqNotFound"
        mock_ticket.requester_user_id = requester_id
        mock_ticket.assignee_user_id = None; mock_ticket.sla_policy_id = None; mock_ticket.comments = []
        self.mock_get_ticket.return_value = mock_ticket

        self.mock_get_user_by_id.return_value = None # Simulate user not found

        self.view.load_ticket_data("T_ReqNotFound")

        self.view.requester_phone_label.setText.assert_called_with("N/A")
        self.view.requester_email_label.setText.assert_called_with("N/A")
        self.view.requester_department_label.setText.assert_called_with("N/A")


if __name__ == '__main__':
    unittest.main()
