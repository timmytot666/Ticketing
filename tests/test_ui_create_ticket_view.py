import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication, QListWidgetItem, QLineEdit, QListWidget, QDialog
from PySide6.QtCore import Qt, QTimer # Added QTimer

from ui_create_ticket_view import CreateTicketView # The class to test
from models import User # For dummy user
from kb_article import KBArticle # For mock return types

class DummyUserForCreateTicketKBTest(User):
    def __init__(self, username="testuser", role="EndUser", user_id_val="kb_test_uid"):
        if User.ROLES is None or not hasattr(User.ROLES, '__args__') or role not in User.ROLES.__args__: # type: ignore
            class TempRoles: __args__ = ('EndUser', 'Technician')
            User.ROLES = TempRoles # type: ignore
            if role not in User.ROLES.__args__: raise ValueError(f"Invalid role '{role}'") # type: ignore
        self.user_id = user_id_val; self.username = username; self.role: User.ROLES = role # type: ignore
        self._password_hash = None
    def set_password(self, password): self._password_hash = f"dummy_{password}"
    def check_password(self, password): return self._password_hash == f"dummy_{password}"


@patch('ui_create_ticket_view.QApplication.instance') # Avoids "QApplication instance not found"
class TestCreateTicketViewKBLogic(unittest.TestCase):

    def setUp(self, mock_qapp_instance):
        if User.ROLES is None: # Ensure User.ROLES for DummyUser
            class TempRoles: __args__ = ('EndUser',)
            User.ROLES = TempRoles #type: ignore

        self.dummy_user = DummyUserForCreateTicketKBTest()

        # Patch away parts of QWidget.__init__ if they cause issues without a full QApplication
        # or rely on QApplication.instance() being mocked.
        # For this view, it's usually fine if we mock its children.
        with patch.object(CreateTicketView, 'setLayout', MagicMock()): # Prevent actual layouting
             self.view = CreateTicketView(current_user=self.dummy_user)

        # Mock UI elements relevant to KB suggestions
        self.view.title_edit = MagicMock(spec=QLineEdit)
        self.view.kb_suggestions_list = MagicMock(spec=QListWidget)

        # Mock kb_manager functions used by the view
        self.mock_search_articles_patcher = patch('ui_create_ticket_view.search_articles')
        self.mock_search_articles = self.mock_search_articles_patcher.start()

        self.mock_get_article_patcher = patch('ui_create_ticket_view.get_article')
        self.mock_get_article = self.mock_get_article_patcher.start()

        # Mock the dialog display method
        self.mock_show_kb_dialog_patcher = patch.object(self.view, '_show_kb_article_dialog')
        self.mock_show_kb_dialog = self.mock_show_kb_dialog_patcher.start()

        # Mock QTimer start if needed, or test its timeout effect directly
        # For now, we will call perform_kb_search directly after setting up timer state if needed
        self.view.kb_search_timer = MagicMock(spec=QTimer) # Replace actual timer with mock

    def tearDown(self):
        self.mock_search_articles_patcher.stop()
        self.mock_get_article_patcher.stop()
        self.mock_show_kb_dialog_patcher.stop()

    def test_on_title_text_changed_starts_timer(self, mock_qapp_instance):
        self.view.on_title_text_changed("test query")
        self.view.kb_search_timer.start.assert_called_once()

    def test_perform_kb_search_calls_search_and_populates(self, mock_qapp_instance):
        self.view.title_edit.text.return_value = "VPN issue" # Query text
        mock_article1 = KBArticle(article_id="kb1", title="VPN Setup", content="...", author_user_id="admin", category="Net")
        mock_article2 = KBArticle(article_id="kb2", title="VPN Troubleshooting", content="...", author_user_id="admin", category="Net")
        self.mock_search_articles.return_value = [mock_article1, mock_article2]

        self.view.perform_kb_search()

        self.mock_search_articles.assert_called_once_with("VPN issue", search_fields=['title', 'keywords'])
        self.view.kb_suggestions_list.clear.assert_called_once()
        self.assertEqual(self.view.kb_suggestions_list.addItem.call_count, 2)

        # Check first item added
        args_item1, _ = self.view.kb_suggestions_list.addItem.call_args_list[0]
        qlistwidgetitem1 = args_item1[0] # The QListWidgetItem instance
        self.assertTrue(qlistwidgetitem1.text().startswith("VPN Setup"))
        self.assertEqual(qlistwidgetitem1.data(Qt.UserRole), "kb1")

        self.view.kb_suggestions_list.setVisible.assert_called_with(True)

    def test_perform_kb_search_no_results(self, mock_qapp_instance):
        self.view.title_edit.text.return_value = "Obscure problem"
        self.mock_search_articles.return_value = [] # No articles found

        self.view.perform_kb_search()

        self.mock_search_articles.assert_called_once_with("Obscure problem", search_fields=['title', 'keywords'])
        self.view.kb_suggestions_list.clear.assert_called_once()
        self.view.kb_suggestions_list.addItem.assert_not_called() # No items to add
        self.view.kb_suggestions_list.setVisible.assert_called_with(False)

    def test_perform_kb_search_query_too_short(self, mock_qapp_instance):
        self.view.title_edit.text.return_value = "Hi" # Query too short (len < 3)

        self.view.perform_kb_search()

        self.mock_search_articles.assert_not_called()
        self.view.kb_suggestions_list.clear.assert_called_once()
        self.view.kb_suggestions_list.setVisible.assert_called_with(False)

    def test_handle_suggestion_clicked_shows_article(self, mock_qapp_instance):
        mock_list_item = MagicMock(spec=QListWidgetItem)
        mock_list_item.data.return_value = "kb_test_id_123" # article_id stored in UserRole

        mock_article = KBArticle(article_id="kb_test_id_123", title="Test Article", content="Details", author_user_id="author")
        self.mock_get_article.return_value = mock_article

        self.view.handle_suggestion_clicked(mock_list_item)

        self.mock_get_article.assert_called_once_with("kb_test_id_123")
        self.mock_show_kb_dialog.assert_called_once_with(mock_article)
        self.view.kb_suggestions_list.setVisible.assert_called_with(False) # Should hide after click

    @patch('ui_create_ticket_view.QMessageBox.warning')
    def test_handle_suggestion_clicked_article_not_found(self, mock_qmessagebox_warning, mock_qapp_instance):
        mock_list_item = MagicMock(spec=QListWidgetItem)
        mock_list_item.data.return_value = "kb_not_found_id"

        self.mock_get_article.return_value = None # Simulate article not found

        self.view.handle_suggestion_clicked(mock_list_item)

        self.mock_get_article.assert_called_once_with("kb_not_found_id")
        self.mock_show_kb_dialog.assert_not_called() # Dialog should not be shown
        mock_qmessagebox_warning.assert_called_once()
        self.view.kb_suggestions_list.setVisible.assert_called_with(False)

    def test_clear_form_hides_suggestions(self, mock_qapp_instance):
        # Ensure _clear_form also clears and hides the suggestion list
        self.view._clear_form() # Call directly
        self.view.kb_suggestions_list.clear.assert_called_once()
        self.view.kb_suggestions_list.setVisible.assert_called_with(False)


if __name__ == '__main__':
    unittest.main()
