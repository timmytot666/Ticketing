import sys
import os # For __main__ path adjustments
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QTextEdit, QComboBox,
    QLabel, QMessageBox, QHeaderView, QAbstractItemView, QApplication
)
from PySide6.QtCore import Slot, Qt, Signal # Added Signal if needed later
from PySide6.QtGui import QFont

from typing import Optional, List, Dict, Any

try:
    from models import User # For current_user type hint
    from kb_article import KBArticle # For type hinting
    from kb_manager import (
        list_articles, get_article, create_article,
        update_article, delete_article
    )
except ModuleNotFoundError:
    print("Error: Critical modules (models, kb_article, kb_manager) not found for KBArticleView.", file=sys.stderr)
    # Fallbacks
    class User: user_id: str = "fallback_user"; ROLES = None
    class KBArticle:
        article_id: str; title: str; category: Optional[str]; updated_at: Any
        def __init__(self, **kwargs): [setattr(self,k,v) for k,v in kwargs.items()]
    def list_articles(sort_by='updated_at', reverse=True): return []
    def get_article(aid): return None
    def create_article(t,c,a,kw=None,cat=None): return None
    def update_article(aid, **kw): return None
    def delete_article(aid): return False


class KBArticleView(QWidget):
    # Define signals if other parts of the UI need to react to KB changes
    # article_created = Signal(str) # article_id
    # article_updated = Signal(str) # article_id
    # article_deleted = Signal(str) # article_id

    COLUMN_TITLE = 0
    COLUMN_CATEGORY = 1
    COLUMN_UPDATED_AT = 2
    DATE_FORMAT = "%Y-%m-%d %H:%M"

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.articles: List[KBArticle] = []
        self.selected_article_id: Optional[str] = None

        self.setWindowTitle("Knowledge Base Management")

        main_hbox_layout = QHBoxLayout(self)

        # --- Left Side: Articles Table ---
        table_v_layout = QVBoxLayout()
        table_title = QLabel("Knowledge Base Articles")
        title_font = QFont(); title_font.setBold(True); title_font.setPointSize(12)
        table_title.setFont(title_font)
        table_v_layout.addWidget(table_title, alignment=Qt.AlignCenter)

        self.articles_table = QTableWidget()
        self.articles_table.setColumnCount(3)
        self.articles_table.setHorizontalHeaderLabels(["Title", "Category", "Last Updated"])
        self.articles_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.articles_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.articles_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.articles_table.verticalHeader().setVisible(False)
        self.articles_table.horizontalHeader().setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.Stretch)
        self.articles_table.horizontalHeader().setSectionResizeMode(self.COLUMN_CATEGORY, QHeaderView.ResizeToContents)
        self.articles_table.horizontalHeader().setSectionResizeMode(self.COLUMN_UPDATED_AT, QHeaderView.ResizeToContents)
        self.articles_table.itemSelectionChanged.connect(self.handle_article_selection)
        table_v_layout.addWidget(self.articles_table)

        main_hbox_layout.addLayout(table_v_layout, 1) # Table takes 1 part of space

        # --- Right Side: Article Form ---
        form_v_layout = QVBoxLayout()
        form_title_label = QLabel("Article Details"); form_title_label.setFont(title_font)
        form_v_layout.addWidget(form_title_label, alignment=Qt.AlignCenter)

        self.article_form = QFormLayout()
        self.article_form.setRowWrapPolicy(QFormLayout.WrapAllRows)

        self.article_id_label = QLabel("ID: <new article>")
        self.article_form.addRow(self.article_id_label)

        self.title_edit = QLineEdit(); self.article_form.addRow("Title:", self.title_edit)
        self.category_edit = QLineEdit(); self.category_edit.setPlaceholderText("e.g., Networking, Printers"); self.article_form.addRow("Category:", self.category_edit)
        self.keywords_edit = QLineEdit(); self.keywords_edit.setPlaceholderText("comma, separated, keywords"); self.article_form.addRow("Keywords:", self.keywords_edit)

        self.article_form.addRow(QLabel("Content (Markdown supported):"))
        self.content_edit = QTextEdit(); self.content_edit.setMinimumHeight(200); self.article_form.addRow(self.content_edit)

        self.author_label = QLabel("Author: N/A"); self.article_form.addRow(self.author_label)
        self.created_at_label = QLabel("Created: N/A"); self.article_form.addRow(self.created_at_label)
        self.updated_at_label = QLabel("Updated: N/A"); self.article_form.addRow(self.updated_at_label)

        form_v_layout.addLayout(self.article_form)
        form_v_layout.addStretch(1) # Pushes form elements up slightly

        form_buttons_layout = QHBoxLayout()
        self.add_new_button = QPushButton("Add New (Clear Form)"); self.add_new_button.clicked.connect(self.prepare_for_new_article)
        form_buttons_layout.addWidget(self.add_new_button)
        self.save_button = QPushButton("Save Article"); self.save_button.clicked.connect(self.handle_save_article)
        form_buttons_layout.addWidget(self.save_button)
        form_v_layout.addLayout(form_buttons_layout)

        self.delete_button = QPushButton("Delete Selected Article"); self.delete_button.clicked.connect(self.handle_delete_article)
        self.delete_button.setEnabled(False)
        form_v_layout.addWidget(self.delete_button, 0, Qt.AlignRight)

        main_hbox_layout.addLayout(form_v_layout, 2) # Form takes 2 parts of space

        self.setLayout(main_hbox_layout)
        self._load_and_display_articles()

    def _load_and_display_articles(self):
        try:
            self.articles = list_articles(sort_by='updated_at', reverse=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load KB articles: {e}")
            self.articles = []

        self.articles_table.setRowCount(0)
        self.articles_table.setRowCount(len(self.articles))

        for row_num, article in enumerate(self.articles):
            title_item = QTableWidgetItem(article.title)
            title_item.setData(Qt.UserRole, article.article_id) # Store ID
            self.articles_table.setItem(row_num, self.COLUMN_TITLE, title_item)
            self.articles_table.setItem(row_num, self.COLUMN_CATEGORY, QTableWidgetItem(article.category or "N/A"))
            updated_at_str = article.updated_at.strftime(self.DATE_FORMAT) if article.updated_at else "N/A"
            self.articles_table.setItem(row_num, self.COLUMN_UPDATED_AT, QTableWidgetItem(updated_at_str))

        self.articles_table.resizeColumnsToContents()
        self.articles_table.horizontalHeader().setSectionResizeMode(self.COLUMN_TITLE, QHeaderView.Stretch) # Ensure title stretches
        self.clear_form_and_selection()

    @Slot()
    def handle_article_selection(self):
        selected_items = self.articles_table.selectedItems()
        if not selected_items: self.clear_form_and_selection(); return

        selected_row = self.articles_table.currentRow()
        if selected_row < 0: self.clear_form_and_selection(); return

        article_id_item = self.articles_table.item(selected_row, self.COLUMN_TITLE) # ID stored in title item
        if not article_id_item: self.clear_form_and_selection(); return

        article_id = article_id_item.data(Qt.UserRole)
        # Fetch full article details if table only has summary, or find in self.articles
        # For now, assume self.articles has full data, or call get_article for more fields if needed
        selected_article = next((art for art in self.articles if art.article_id == article_id), None)

        if selected_article:
            self.selected_article_id = article_id
            self.article_id_label.setText(f"ID: {selected_article.article_id}")
            self.title_edit.setText(selected_article.title)
            self.category_edit.setText(selected_article.category or "")
            self.keywords_edit.setText(", ".join(selected_article.keywords) if selected_article.keywords else "")
            self.content_edit.setPlainText(selected_article.content) # Use setPlainText for plain text/Markdown
            self.author_label.setText(f"Author: {selected_article.author_user_id[:8]}...")
            self.created_at_label.setText(f"Created: {selected_article.created_at.strftime(self.DATE_FORMAT)}")
            self.updated_at_label.setText(f"Updated: {selected_article.updated_at.strftime(self.DATE_FORMAT)}")
            self.delete_button.setEnabled(True)
        else:
            self.clear_form_and_selection()

    @Slot()
    def prepare_for_new_article(self):
        self.clear_form_and_selection()

    def clear_form_and_selection(self):
        self.articles_table.clearSelection()
        self.selected_article_id = None
        self.article_id_label.setText("ID: <new article>")
        self.title_edit.clear(); self.category_edit.clear(); self.keywords_edit.clear(); self.content_edit.clear()
        self.author_label.setText("Author: N/A"); self.created_at_label.setText("Created: N/A"); self.updated_at_label.setText("Updated: N/A")
        self.delete_button.setEnabled(False)
        self.title_edit.setFocus()

    @Slot()
    def handle_save_article(self):
        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText().strip() # Or toHtml() if rich text
        keywords_str = self.keywords_edit.text().strip()
        category = self.category_edit.text().strip()

        if not title or not content:
            QMessageBox.warning(self, "Validation Error", "Title and Content cannot be empty.")
            return

        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
        category_to_save = category if category else None # Store None if empty

        try:
            if self.selected_article_id: # Editing
                updated = update_article(
                    article_id=self.selected_article_id, title=title, content=content,
                    keywords=keywords, category=category_to_save
                    # author_user_id and created_at are not changed on update
                )
                if updated: QMessageBox.information(self, "Success", "Article updated successfully.")
                else: QMessageBox.warning(self, "Update Failed", "Could not update article or no changes made.")
            else: # New article
                new_article = create_article(
                    title=title, content=content, author_user_id=self.current_user.user_id,
                    keywords=keywords, category=category_to_save
                )
                if new_article: QMessageBox.information(self, "Success", f"Article '{new_article.title}' created.")
                else: QMessageBox.warning(self, "Creation Failed", "Could not create article.")

            self._load_and_display_articles() # Refresh list and clear form
        except ValueError as ve: # Catch validation errors from manager/model
            QMessageBox.critical(self, "Validation Error", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    @Slot()
    def handle_delete_article(self):
        if not self.selected_article_id:
            QMessageBox.warning(self, "No Selection", "No article selected for deletion.")
            return

        article_to_delete = next((art for art in self.articles if art.article_id == self.selected_article_id), None)
        if not article_to_delete:
            QMessageBox.warning(self, "Error", "Selected article not found. Please refresh.")
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete article: '{article_to_delete.title}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if delete_article(self.selected_article_id):
                    QMessageBox.information(self, "Success", f"Article '{article_to_delete.title}' deleted.")
                    self._load_and_display_articles()
                else:
                    QMessageBox.warning(self, "Delete Failed", "Failed to delete article from storage.")
            except Exception as e:
                 QMessageBox.critical(self, "Delete Error", f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from models import User; from kb_article import KBArticle; import kb_manager
    except: pass # Fallbacks at top

    app = QApplication(sys.argv)
    class DummyUserKB(User):
        def __init__(self, u="kb_editor", r="TechManager", uid="kb_editor_uid"):
            self.username=u; self.role=r; self.user_id=uid #type: ignore
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TR: __args__ = ('TechManager','EndUser'); User.ROLES=TR; self.ROLES=TR #type: ignore

        def set_password(self,p):pass
        def check_password(self,p):return False
    test_user = DummyUserKB()

    # Mock kb_manager functions for standalone UI test
    _MOCK_KB_DB: List[KBArticle] = []
    def _find_mock_article(article_id):
        return next((art for art in _MOCK_KB_DB if art.article_id == article_id), None)

    _og_list_articles = kb_manager.list_articles
    _og_get_article = kb_manager.get_article
    _og_create_article = kb_manager.create_article
    _og_update_article = kb_manager.update_article
    _og_delete_article = kb_manager.delete_article

    def mock_list_articles(sort_by='updated_at', reverse=True):
        print(f"MOCK list_articles called (sort: {sort_by}, rev: {reverse}) -> {len(_MOCK_KB_DB)} items")
        # Simplified sort for mock
        _MOCK_KB_DB.sort(key=lambda x: getattr(x, sort_by, datetime.min), reverse=reverse)
        return list(_MOCK_KB_DB) # Return a copy

    def mock_get_article(article_id): return _find_mock_article(article_id)

    def mock_create_article(title, content, author_user_id, keywords=None, category=None):
        print(f"MOCK create_article: {title}")
        new_id = "kb_" + uuid.uuid4().hex[:8]
        # Use actual KBArticle for realistic object
        article = KBArticle(title=title, content=content, author_user_id=author_user_id,
                            keywords=keywords, category=category, article_id=new_id)
        _MOCK_KB_DB.append(article)
        return article

    def mock_update_article(article_id, **kwargs):
        print(f"MOCK update_article: {article_id} with {kwargs}")
        article = _find_mock_article(article_id)
        if article:
            for k, v in kwargs.items():
                if hasattr(article, k): setattr(article, k, v)
            article.updated_at = datetime.now(timezone.utc)
            return article
        return None

    def mock_delete_article(article_id):
        print(f"MOCK delete_article: {article_id}")
        original_len = len(_MOCK_KB_DB)
        _MOCK_KB_DB[:] = [art for art in _MOCK_KB_DB if art.article_id != article_id]
        return len(_MOCK_KB_DB) < original_len

    kb_manager.list_articles = mock_list_articles
    kb_manager.get_article = mock_get_article
    kb_manager.create_article = mock_create_article
    kb_manager.update_article = mock_update_article
    kb_manager.delete_article = mock_delete_article

    # Add some initial mock data
    mock_create_article("Initial KB Article 1", "Content for article 1.", "init_user", ["test", "init"], "General")
    mock_create_article("Troubleshooting Network Issues", "Steps for network problems.", "init_user", ["network", "connectivity"], "Networking")


    kb_view = KBArticleView(current_user=test_user)
    kb_view.show()
    app.exec()

    kb_manager.list_articles = _og_list_articles
    kb_manager.get_article = _og_get_article
    kb_manager.create_article = _og_create_article
    kb_manager.update_article = _og_update_article
    kb_manager.delete_article = _og_delete_article
