import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QComboBox, QPushButton, QMessageBox, QFormLayout, QFileDialog,
    QListWidget, QListWidgetItem, QToolButton, QApplication,
    QDialog, QTextBrowser, QSizePolicy # Added QDialog, QTextBrowser, QSizePolicy
)
from PySide6.QtCore import Slot, Qt, QSize, QTimer, Signal # Added QTimer, Signal (though Signal not used here)
from PySide6.QtGui import QIcon

from typing import Optional, List, Tuple

try:
    from models import User
    from ticket_manager import create_ticket, add_attachment_to_ticket
    from kb_article import KBArticle # Added
    from kb_manager import search_articles, get_article # Added
except ModuleNotFoundError:
    print("Warning: Critical modules not found for CreateTicketView. Using fallback definitions.", file=sys.stderr)
    class User: # type: ignore
        user_id: str = "fallback_user"
        ROLES = None
        # Add any other attributes/methods ui_create_ticket_view.py might expect from a User object
        def __init__(self, username="fallback", role="EndUser", user_id="fallback_user"):
            self.username = username
            self.role = role
            self.user_id = user_id

    class KBArticle: # type: ignore
        article_id: str
        title: str
        content: str
        category: Optional[str] = None
        keywords: Optional[List[str]] = None
        # Add any other attributes/methods ui_create_ticket_view.py might expect
        def __init__(self, article_id="fb_kb_id", title="Fallback KB", content="", author_user_id=""):
            self.article_id = article_id
            self.title = title
            self.content = content
            self.author_user_id = author_user_id # Example if needed by other parts

    class _FallbackTicket:
        def __init__(self, ticket_id="dummy_fb_id", title="Fallback Ticket", **extra_kwargs):
            self.id = ticket_id
            self.title = title
            # Allow any other attributes that might be accessed by the calling code after creation
            for key, value in extra_kwargs.items():
                setattr(self, key, value)
            # Ensure attributes accessed in handle_submit_ticket are present
            if not hasattr(self, 'description'): self.description = ""
            if not hasattr(self, 'type'): self.type = "IT"
            if not hasattr(self, 'priority'): self.priority = "Medium"
            if not hasattr(self, 'requester_user_id'): self.requester_user_id = "fallback_user"


    def create_ticket(*args, **kwargs) -> _FallbackTicket: # type: ignore
        print(f"Warning: Using fallback 'create_ticket'. Called with args: {args}, kwargs: {kwargs}", file=sys.stderr)
        # Ensure the title is part of the kwargs for the fallback ticket
        fb_title = kwargs.get("title", "Fallback Ticket Title")
        return _FallbackTicket(title=fb_title, **kwargs)

    def add_attachment_to_ticket(ticket_id: str, user_id: str, source_path: str, original_filename: str): # type: ignore
        print(f"Warning: Using fallback 'add_attachment_to_ticket' for ticket {ticket_id}, file {original_filename}.", file=sys.stderr)
        pass

    def search_articles(query: str, search_fields: Optional[List[str]] = None) -> List[KBArticle]: # type: ignore
        print(f"Warning: Using fallback 'search_articles' for query '{query}'.", file=sys.stderr)
        return []

    def get_article(article_id: str) -> Optional[KBArticle]: # type: ignore
        print(f"Warning: Using fallback 'get_article' for ID '{article_id}'.", file=sys.stderr)
        return None


class CreateTicketView(QWidget):
    # Optional: Signal when a ticket is successfully created
    # ticket_created_successfully = Signal(str) # Emits new ticket_id

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.staged_files_for_upload: List[Tuple[str, str]] = []

        self.setWindowTitle("Create New Ticket")
        main_layout = QVBoxLayout(self)

        # Using QFormLayout for the main form fields
        form_section_layout = QFormLayout()

        self.title_edit = QLineEdit(); self.title_edit.setPlaceholderText("Brief title for the ticket")
        form_section_layout.addRow(QLabel("Title:"), self.title_edit)

        # KB Suggestions List (initially hidden)
        self.kb_suggestions_list = QListWidget()
        self.kb_suggestions_list.setVisible(False)
        self.kb_suggestions_list.setMaximumHeight(100) # Adjust as needed
        self.kb_suggestions_list.itemClicked.connect(self.handle_suggestion_clicked)
        # Insert suggestions list directly after title_edit in a QVBoxLayout for that row
        title_and_suggestions_layout = QVBoxLayout()
        title_and_suggestions_layout.setSpacing(2) # Reduce spacing
        title_and_suggestions_layout.addWidget(self.title_edit)
        title_and_suggestions_layout.addWidget(self.kb_suggestions_list)
        form_section_layout.setWidget(form_section_layout.rowCount()-1, QFormLayout.FieldRole, title_and_suggestions_layout)


        self.description_edit = QTextEdit(); self.description_edit.setPlaceholderText("Detailed description")
        self.description_edit.setMinimumHeight(100); form_section_layout.addRow(QLabel("Description:"), self.description_edit)
        self.type_combo = QComboBox(); self.type_combo.addItems(["IT", "Facilities"]); form_section_layout.addRow(QLabel("Type:"), self.type_combo)
        self.priority_combo = QComboBox(); self.priority_combo.addItems(["Low", "Medium", "High"]); self.priority_combo.setCurrentText("Medium")
        form_section_layout.addRow(QLabel("Priority:"), self.priority_combo)
        main_layout.addLayout(form_section_layout)

        # KB Search Timer
        self.kb_search_timer = QTimer(self)
        self.kb_search_timer.setSingleShot(True)
        self.kb_search_timer.setInterval(500) # 500ms debounce
        self.kb_search_timer.timeout.connect(self.perform_kb_search)
        self.title_edit.textChanged.connect(self.on_title_text_changed)

        # Attachments Section
        attachment_label = QLabel("Attachments:"); main_layout.addWidget(attachment_label)
        self.add_attachment_button = QPushButton("Add Attachment(s)")
        self.add_attachment_button.clicked.connect(self.handle_select_attachments)
        main_layout.addWidget(self.add_attachment_button, alignment=Qt.AlignLeft)
        self.staged_attachments_list_widget = QListWidget(); self.staged_attachments_list_widget.setMaximumHeight(100)
        main_layout.addWidget(self.staged_attachments_list_widget)

        # Submit Button
        self.submit_button = QPushButton("Submit Ticket")
        self.submit_button.clicked.connect(self.handle_submit_ticket)
        button_layout = QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(self.submit_button); button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.message_label = QLabel(""); self.message_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.message_label)
        main_layout.addStretch()
        self.setLayout(main_layout)

    @Slot(str)
    def on_title_text_changed(self, text: str):
        self.kb_search_timer.start() # Restarts the timer on each text change

    @Slot()
    def perform_kb_search(self):
        query = self.title_edit.text().strip()
        self.kb_suggestions_list.clear()
        if len(query) < 3: # Minimum query length for search
            self.kb_suggestions_list.setVisible(False)
            return
        try:
            suggested_articles = search_articles(query, search_fields=['title', 'keywords'])
            if suggested_articles:
                for article in suggested_articles[:5]: # Show top 5 suggestions
                    item = QListWidgetItem(f"{article.title} (Category: {article.category or 'N/A'})")
                    item.setData(Qt.UserRole, article.article_id)
                    self.kb_suggestions_list.addItem(item)
                self.kb_suggestions_list.setVisible(True)
            else:
                self.kb_suggestions_list.setVisible(False)
        except Exception as e:
            print(f"Error during KB search: {e}", file=sys.stderr)
            self.kb_suggestions_list.setVisible(False)

    @Slot(QListWidgetItem)
    def handle_suggestion_clicked(self, item: QListWidgetItem):
        article_id = item.data(Qt.UserRole)
        if article_id:
            try:
                article = get_article(article_id)
                if article:
                    self._show_kb_article_dialog(article)
                else:
                    QMessageBox.warning(self, "Article Not Found", f"Could not retrieve article with ID: {article_id}")
            except Exception as e:
                 QMessageBox.critical(self, "Error", f"Error retrieving article: {e}")
        self.kb_suggestions_list.setVisible(False) # Hide after click

    def _show_kb_article_dialog(self, article: KBArticle):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"KB Article: {article.title}")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        title_label = QLabel(f"<b>{article.title}</b>"); title_label.setTextFormat(Qt.RichText)
        layout.addWidget(title_label)

        category_label = QLabel(f"<i>Category: {article.category or 'N/A'}</i>"); category_label.setTextFormat(Qt.RichText)
        layout.addWidget(category_label)

        keywords_label = QLabel(f"<i>Keywords: {', '.join(article.keywords) if article.keywords else 'None'}</i>"); keywords_label.setTextFormat(Qt.RichText)
        layout.addWidget(keywords_label)

        content_display = QTextBrowser()
        content_display.setMarkdown(article.content) # Assumes content is Markdown
        content_display.setOpenExternalLinks(True) # Open links in browser
        layout.addWidget(content_display)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)

        dialog.setLayout(layout)
        dialog.exec()


    @Slot()
    def handle_select_attachments(self): # As before
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*)");
        if paths: [self.staged_files_for_upload.append((p, os.path.basename(p))) for p in paths if not any(s_p == p for s_p, _ in self.staged_files_for_upload)]; self._update_staged_files_display()

    def _update_staged_files_display(self): # As before
        self.staged_attachments_list_widget.clear()
        for sp, on in self.staged_files_for_upload:
            item=QListWidgetItem();iw=QWidget();lo=QHBoxLayout(iw);lo.setContentsMargins(0,0,0,0);lbl=QLabel(on);lbl.setToolTip(sp);lo.addWidget(lbl,1)
            rb=QToolButton();rb.setText("X");rb.setFixedSize(QSize(20,20));rb.setToolTip(f"Remove {on}");rb.clicked.connect(lambda c=False,p=sp:self.handle_remove_staged_file(p))
            lo.addWidget(rb);iw.setLayout(lo);item.setSizeHint(iw.sizeHint());self.staged_attachments_list_widget.addItem(item);self.staged_attachments_list_widget.setItemWidget(item,iw)

    @Slot(str)
    def handle_remove_staged_file(self, file_path_to_remove: str): # As before
        self.staged_files_for_upload = [(p,n) for p,n in self.staged_files_for_upload if p!=file_path_to_remove]; self._update_staged_files_display()

    @Slot()
    def handle_submit_ticket(self): # As before, with attachment loop
        title = self.title_edit.text().strip(); description = self.description_edit.toPlainText().strip()
        ticket_type = self.type_combo.currentText(); priority = self.priority_combo.currentText()
        if not title or not description:
            self.message_label.setText("Title and Description cannot be empty."); self.message_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Input Error", "Title and Description cannot be empty."); return
        try:
            new_ticket = create_ticket(title=title,description=description,type=ticket_type,priority=priority,requester_user_id=self.current_user.user_id)
            if not new_ticket: raise Exception("Ticket creation returned None.")
            success_uploads=0
            for sp,on in list(self.staged_files_for_upload):
                try: add_attachment_to_ticket(new_ticket.id,self.current_user.user_id,sp,on); success_uploads+=1
                except Exception as e: QMessageBox.warning(self,"Attach Error",f"Could not attach {on}: {e}")
            msg=f"Ticket '{new_ticket.title}' (ID: {new_ticket.id}) created. {success_uploads}/{len(self.staged_files_for_upload)} files attached."
            self.message_label.setText(msg); self.message_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "Ticket Created", msg); self._clear_form()
        except Exception as e:
            self.message_label.setText(f"Error: {e}"); self.message_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}"); print(f"Error: {e}", file=sys.stderr)

    def _clear_form(self): # Modified
        self.title_edit.clear(); self.description_edit.clear()
        self.type_combo.setCurrentIndex(0); self.priority_combo.setCurrentText("Medium")
        self.staged_files_for_upload.clear(); self._update_staged_files_display()
        self.kb_suggestions_list.clear(); self.kb_suggestions_list.setVisible(False) # Clear KB suggestions
        self.message_label.setText("")

if __name__ == '__main__':
    import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from models import User; from ticket_manager import create_ticket, add_attachment_to_ticket
    except: pass # Fallbacks

    app = QApplication(sys.argv)
    class DUFCV(User): # DummyUserForCreateView
        def __init__(self, u="test_c", r="EndUser", uid="c_uid"): self.username=u;self.role=r;self.user_id=uid # type: ignore
        def set_password(self,p):pass; def check_password(self,p):return False
    tu = DUFCV()

    # Mock kb_manager for standalone UI test
    _og_search_articles = kb_manager.search_articles
    _og_get_article = kb_manager.get_article
    def mock_search(query, fields=None):
        print(f"MOCK search_articles: {query}")
        if "vpn" in query.lower(): return [KBArticle(article_id="kb1", title="VPN Setup Guide", content="## VPN Content\nDetails...", author_user_id="sys")]
        if "printer" in query.lower(): return [KBArticle(article_id="kb2", title="Fix Printer Offline", content="Check cable", author_user_id="sys")]
        return []
    def mock_get(aid):
        if aid=="kb1": return KBArticle(article_id="kb1", title="VPN Setup Guide", content="## VPN Content\nDetails for VPN setup...", author_user_id="sys", category="Networking", keywords=["vpn", "remote access"])
        return None
    kb_manager.search_articles = mock_search
    kb_manager.get_article = mock_get

    # Mock ticket_manager as before
    _og_ct = ticket_manager.create_ticket; _og_aat = ticket_manager.add_attachment_to_ticket
    def mct(*a,**kwa): class DT:id="T_NEW";title=kwa.get("title"); return DT();
    def maat(*a,**kwa): pass
    ticket_manager.create_ticket=mct; ticket_manager.add_attachment_to_ticket=maat

    v = CreateTicketView(current_user=tu); v.show()
    app.exec()
    ticket_manager.create_ticket=_og_ct; ticket_manager.add_attachment_to_ticket=_og_aat
    kb_manager.search_articles = _og_search_articles
    kb_manager.get_article = _og_get_article
