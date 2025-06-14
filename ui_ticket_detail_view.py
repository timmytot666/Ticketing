import sys
import os
import shutil
import re # Added for KB link processing
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QScrollArea, QMessageBox, QApplication,
    QFileDialog, QListWidget, QListWidgetItem, QToolButton, QSizePolicy,
    QDialog, QDialogButtonBox, QTextBrowser # Added QTextBrowser
)
from PySide6.QtCore import Slot, Qt, Signal, QSize, QUrl, QDesktopServices
from PySide6.QtGui import QFont, QIcon

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

try:
    from models import User, Ticket
    from kb_article import KBArticle
    from ticket_manager import get_ticket, update_ticket, add_comment_to_ticket, add_attachment_to_ticket, remove_attachment_from_ticket, ATTACHMENT_DIR
    from settings_manager import get_sla_policies
    from kb_manager import search_articles as kb_search_articles
    from kb_manager import get_article as kb_get_article
except ModuleNotFoundError:
    print("Error: Critical modules not found for TicketDetailView/KBSearchDialog.", file=sys.stderr)

    # Imports needed for FallbackTicket default values
    from datetime import datetime, timezone
    from typing import Optional, List, Any # Any can be used if Dict not critical for fallback type hint

    class User: # type: ignore
        user_id: str = "fb_user"
        ROLES = None
        def __init__(self, username="fb_user", role="EndUser", user_id="fb_user_id"): # Basic init
            self.username = username
            self.role = role
            self.user_id = user_id

    class Ticket: # Fallback Ticket class
        def __init__(self, **kwargs: Any):
            # Initialize default attributes that TicketDetailView might access
            self.id: str = "fb_ticket_id"
            self.title: str = "Fallback Ticket"
            self.description: str = "Fallback description"
            self.status: str = "Open"
            self.priority: str = "Medium"
            self.type: str = "IT"
            self.requester_user_id: str = "fb_requester_id"
            self.assignee_user_id: Optional[str] = None
            self.created_by_user_id: str = "fb_creator_id" # If used by view logic
            self.created_at: datetime = datetime.now(timezone.utc)
            self.updated_at: datetime = datetime.now(timezone.utc)

            self.attachments: List[Dict[str, Any]] = [] # Default
            self.comments: List[Dict[str, Any]] = []    # Default

            # SLA related fields (as used in TicketDetailView)
            self.sla_policy_id: Optional[str] = None
            self.response_due_at: Optional[datetime] = None
            self.resolution_due_at: Optional[datetime] = None
            self.responded_at: Optional[datetime] = None
            self.sla_paused_at: Optional[datetime] = None
            self.total_paused_duration_seconds: float = 0.0

            # Apply any kwargs passed, potentially overriding defaults
            for key, value in kwargs.items():
                setattr(self, key, value)

    class KBArticle: # type: ignore
        article_id: str = "fb_kb_id"
        title: str = "Fallback KB Article"
        content: str = "Fallback content"
        # Add other fields if necessary for fallback usage in this view
        category: Optional[str] = None
        keywords: Optional[List[str]] = None
        author_user_id: str = "fb_author"
        created_at: datetime = datetime.now(timezone.utc)
        updated_at: datetime = datetime.now(timezone.utc)

        def __init__(self, **kwargs: Any): # Allow kwargs for flexibility
            for key, value in kwargs.items():
                setattr(self, key, value)


    def get_ticket(tid): return None; def update_ticket(tid, **kwargs): return None
    def add_comment_to_ticket(tid,uid,txt): return None; def add_attachment_to_ticket(tid,uid,src,oname): return None
    def remove_attachment_from_ticket(tid,attid): return None; ATTACHMENT_DIR = "ticket_attachments_fallback"
    def get_sla_policies(): return []; def kb_search_articles(q, sf=None): return []; def kb_get_article(aid): return None

# --- KB Search Dialog (from previous step, ensure it's here) ---
class KBSearchDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent); self.setWindowTitle("Search Knowledge Base"); self.setMinimumSize(400,300); self.setModal(True)
        self.selected_article_id:Optional[str]=None; self.selected_article_title:Optional[str]=None
        main_layout=QVBoxLayout(self); search_layout=QHBoxLayout(); search_layout.addWidget(QLabel("Search:"))
        self.search_query_edit=QLineEdit(); self.search_query_edit.setPlaceholderText("Enter keywords..."); search_layout.addWidget(self.search_query_edit)
        self.search_button=QPushButton("Search"); search_layout.addWidget(self.search_button); main_layout.addLayout(search_layout)
        self.results_list=QListWidget(); self.results_list.itemDoubleClicked.connect(self.accept_selection_and_close); self.results_list.itemSelectionChanged.connect(self.update_button_states); main_layout.addWidget(self.results_list)
        self.button_box=QDialogButtonBox(); self.insert_link_button=self.button_box.addButton("Insert Link",QDialogButtonBox.AcceptRole); self.button_box.addButton(QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept_selection_and_close); self.button_box.rejected.connect(self.reject); main_layout.addWidget(self.button_box)
        self.search_button.clicked.connect(self.perform_search); self.search_query_edit.returnPressed.connect(self.perform_search)
        self.update_button_states()
    @Slot()
    def perform_search(self):
        query=self.search_query_edit.text().strip(); self.results_list.clear(); self.selected_article_id=None; self.selected_article_title=None; self.update_button_states()
        if len(query)<3: QMessageBox.information(self,"Search Query Too Short","Please enter at least 3 characters to search."); return
        try:
            articles:List[KBArticle]=kb_search_articles(query,search_fields=['title','keywords','content'])
            if articles: [self.results_list.addItem(item) for article in articles if (item:=QListWidgetItem(f"{getattr(article,'title','N/A')} (ID: {getattr(article,'article_id','N/A')[:8]}...)"), item.setData(Qt.UserRole,(getattr(article,'article_id',None),getattr(article,'title',None))), True)[2]] # complex list comp for brevity
            else: self.results_list.addItem("No articles found matching your query.")
        except Exception as e: QMessageBox.critical(self,"Search Error",f"Error searching knowledge base: {e}"); print(f"KB Search Error: {e}",file=sys.stderr)
        self.update_button_states()
    @Slot()
    def update_button_states(self): btn=self.button_box.button(QDialogButtonBox.AcceptRole); btn and btn.setEnabled(self.results_list.currentItem() is not None and self.results_list.currentItem().data(Qt.UserRole)is not None)
    @Slot()
    def accept_selection_and_close(self):
        ci=self.results_list.currentItem()
        if ci and ci.data(Qt.UserRole): aid,ati=ci.data(Qt.UserRole); (aid and ati) and (setattr(self,'selected_article_id',aid),setattr(self,'selected_article_title',ati),self.accept()) or QMessageBox.warning(self,"Selection Error","Invalid article data.")
        else: QMessageBox.warning(self,"No Selection","Please select an article.")
    def get_selected_article_link_data(self)->Optional[Tuple[str,str]]:return (self.selected_article_id,self.selected_article_title) if self.selected_article_id and self.selected_article_title else None

class TicketDetailView(QWidget):
    ticket_updated=Signal(str); navigate_back=Signal()
    DATE_FORMAT="%Y-%m-%d %H:%M:%S UTC"
    def __init__(self, current_user:User, parent:Optional[QWidget]=None):
        super().__init__(parent)
        # ... (member initializations as before) ...
        self.current_user=current_user; self.current_ticket_id:Optional[str]=None; self.current_ticket_data:Optional[Ticket]=None; self.staged_files_for_upload:List[Tuple[str,str]]=[]; self.attachment_base_path=ATTACHMENT_DIR
        main_layout=QVBoxLayout(self); scroll_area=QScrollArea(); scroll_area.setWidgetResizable(True); main_layout.addWidget(scroll_area); content_widget=QWidget(); scroll_area.setWidget(content_widget); layout=QVBoxLayout(content_widget)
        info_form_layout=QFormLayout(); info_form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        # ... (Ticket Info fields as before) ...
        self.ticket_id_label = QLabel("N/A"); info_form_layout.addRow("Ticket ID:", self.ticket_id_label)
        self.title_edit = QLineEdit(); info_form_layout.addRow("Title:", self.title_edit)
        self.requester_id_label = QLabel("N/A"); info_form_layout.addRow("Requester ID:", self.requester_id_label)
        self.status_combo = QComboBox(); self.status_combo.addItems(["Open", "In Progress", "On Hold", "Closed"]); info_form_layout.addRow("Status:", self.status_combo)
        self.priority_combo = QComboBox(); self.priority_combo.addItems(["Low", "Medium", "High"]); info_form_layout.addRow("Priority:", self.priority_combo)
        self.type_combo = QComboBox(); self.type_combo.addItems(["IT", "Facilities"]); info_form_layout.addRow("Type:", self.type_combo)
        self.assignee_edit = QLineEdit(); self.assignee_edit.setPlaceholderText("User ID or blank"); info_form_layout.addRow("Assigned To:", self.assignee_edit)
        self.created_at_label = QLabel("N/A"); info_form_layout.addRow("Created At:", self.created_at_label)
        self.updated_at_label = QLabel("N/A"); info_form_layout.addRow("Last Updated:", self.updated_at_label)
        self.sla_policy_label = QLabel("N/A"); info_form_layout.addRow("SLA Policy:", self.sla_policy_label)
        self.responded_at_label = QLabel("N/A"); info_form_layout.addRow("Responded At:", self.responded_at_label)
        self.response_due_label = QLabel("N/A"); info_form_layout.addRow("Response Due:", self.response_due_label)
        self.resolution_due_label = QLabel("N/A"); info_form_layout.addRow("Resolution Due:", self.resolution_due_label)
        self.sla_status_label = QLabel("SLA Status: N/A"); info_form_layout.addRow(self.sla_status_label)
        layout.addLayout(info_form_layout)
        layout.addWidget(QLabel("Description:")); self.description_edit=QTextEdit(); self.description_edit.setMinimumHeight(80); layout.addWidget(self.description_edit)
        layout.addWidget(QLabel("Current Attachments:")); self.current_attachments_list_widget=QListWidget(); self.current_attachments_list_widget.setMaximumHeight(120); layout.addWidget(self.current_attachments_list_widget)

        # Comments Section - Changed to QTextBrowser
        layout.addWidget(QLabel("Comments/History:"))
        self.comments_display = QTextBrowser() # Changed from QTextEdit
        self.comments_display.setReadOnly(True)
        self.comments_display.setOpenLinks(False) # IMPORTANT for custom link handling
        self.comments_display.anchorClicked.connect(self.handle_kb_link_clicked) # Connect signal
        self.comments_display.setMinimumHeight(100); layout.addWidget(self.comments_display)

        new_comment_layout=QHBoxLayout(); self.new_comment_edit=QTextEdit(); self.new_comment_edit.setMaximumHeight(60); new_comment_layout.addWidget(self.new_comment_edit,1)
        self.link_kb_button=QPushButton("Link KB"); self.link_kb_button.setToolTip("Search KB"); self.link_kb_button.clicked.connect(self.handle_link_kb_article); new_comment_layout.addWidget(self.link_kb_button)
        layout.addLayout(new_comment_layout)
        self.add_comment_button=QPushButton("Add Comment"); self.add_comment_button.clicked.connect(self.handle_add_comment); layout.addWidget(self.add_comment_button,alignment=Qt.AlignRight)

        # ... (New Attachments Section and Action Buttons as before) ...
        layout.addWidget(QLabel("Add New Attachments:")); self.add_new_attachment_button = QPushButton("Select Files to Stage"); self.add_new_attachment_button.clicked.connect(self.handle_select_attachments); layout.addWidget(self.add_new_attachment_button, alignment=Qt.AlignLeft)
        self.staged_attachments_list_widget = QListWidget(); self.staged_attachments_list_widget.setMaximumHeight(80); layout.addWidget(self.staged_attachments_list_widget)
        self.upload_staged_button = QPushButton("Upload Staged Attachments"); self.upload_staged_button.clicked.connect(self.handle_upload_staged_attachments); self.upload_staged_button.setEnabled(False); layout.addWidget(self.upload_staged_button, alignment=Qt.AlignLeft)
        action_buttons_layout = QHBoxLayout(); self.update_ticket_button = QPushButton("Update Ticket"); self.update_ticket_button.clicked.connect(self.handle_update_ticket); action_buttons_layout.addWidget(self.update_ticket_button)
        self.back_button = QPushButton("Back to List"); self.back_button.clicked.connect(self.navigate_back.emit); action_buttons_layout.addWidget(self.back_button); action_buttons_layout.addStretch(); layout.addLayout(action_buttons_layout)

        self.setLayout(main_layout)

    # ... (load_ticket_data, _format_datetime_display, _populate_current_attachments, _format_timedelta, _calculate_and_display_sla_status as before) ...
    def load_ticket_data(self, ticket_id: str): # Unchanged from previous step essentially
        self.current_ticket_id = ticket_id; self.staged_files_for_upload.clear(); self._update_staged_files_display()
        try:
            ticket = get_ticket(ticket_id)
            if not ticket: QMessageBox.warning(self, "Not Found", f"Ticket ID '{ticket_id}' not found."); self.clear_view(); return
            self.current_ticket_data = ticket
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to load ticket data: {e}"); self.clear_view(); return
        self.ticket_id_label.setText(ticket.id); self.requester_id_label.setText(ticket.requester_user_id)
        self.created_at_label.setText(self._format_datetime_display(ticket.created_at)); self.updated_at_label.setText(self._format_datetime_display(ticket.updated_at))
        self.title_edit.setText(ticket.title); self.description_edit.setPlainText(ticket.description)
        self.status_combo.setCurrentText(ticket.status); self.priority_combo.setCurrentText(ticket.priority)
        self.type_combo.setCurrentText(ticket.type); self.assignee_edit.setText(ticket.assignee_user_id or "")
        if ticket.sla_policy_id:
            all_sla_policies = get_sla_policies(); policy_name = next((p['name'] for p in all_sla_policies if p['policy_id'] == ticket.sla_policy_id), ticket.sla_policy_id)
            self.sla_policy_label.setText(policy_name)
        else: self.sla_policy_label.setText("N/A")
        self.responded_at_label.setText(self._format_datetime_display(ticket.responded_at))
        self.response_due_label.setText(self._format_datetime_display(ticket.response_due_at))
        self.resolution_due_label.setText(self._format_datetime_display(ticket.resolution_due_at))
        self._calculate_and_display_sla_status(ticket); self._populate_comments(); self._populate_current_attachments(); self._apply_role_permissions()
    def _populate_current_attachments(self):  # Unchanged from previous step
        self.current_attachments_list_widget.clear()
        if self.current_ticket_data and hasattr(self.current_ticket_data, 'attachments') and self.current_ticket_data.attachments:
            for att_meta in self.current_ticket_data.attachments:
                item_widget = QWidget(); item_layout = QHBoxLayout(item_widget); item_layout.setContentsMargins(5,2,5,2)
                filename = att_meta.get('original_filename', 'N/A'); filesize_kb = att_meta.get('filesize',0)/1024.0
                uploader = att_meta.get('uploader_user_id','N/A')[:8]; uploaded_at_short = att_meta.get('uploaded_at','N/A')[:10]
                info_label = QLabel(f"{filename} ({filesize_kb:.2f} KB) - By: {uploader} on {uploaded_at_short}"); info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); item_layout.addWidget(info_label)
                open_b = QToolButton();open_b.setText("Open");open_b.clicked.connect(lambda c=False,m=att_meta:self.handle_open_attachment(m));item_layout.addWidget(open_b)
                save_as_b = QToolButton();save_as_b.setText("Save As...");save_as_b.clicked.connect(lambda c=False,m=att_meta:self.handle_save_attachment_as(m));item_layout.addWidget(save_as_b)
                remove_b = QToolButton();remove_b.setText("Remove");can_rem=(self.current_user.user_id==att_meta.get('uploader_user_id') or self.current_user.role in ['TechManager','EngManager']);remove_b.setEnabled(can_rem);remove_b.clicked.connect(lambda c=False,aid=att_meta.get('attachment_id'):self.handle_remove_attachment(aid) if aid else None);item_layout.addWidget(remove_b)
                li=QListWidgetItem(self.current_attachments_list_widget);li.setSizeHint(item_widget.sizeHint());self.current_attachments_list_widget.addItem(li);self.current_attachments_list_widget.setItemWidget(li,item_widget)
        else: li=QListWidgetItem("No attachments yet.");li.setFlags(li.flags()&~Qt.ItemIsSelectable);self.current_attachments_list_widget.addItem(li)
    def _format_timedelta(self, delta: timedelta) -> str: days=delta.days;h,r=divmod(delta.seconds,3600);m,_=divmod(r,60); s=f"-{days}d {h}h {m}m" if days>0 else f"-{h}h {m}m"; return s if days<0 else (f"{days}d {h}h {m}m" if days > 0 else f"{h}h {m}m")
    def _calculate_and_display_sla_status(self, ticket: Ticket): # Unchanged
        if not ticket: self.sla_status_label.setText("SLA Status: N/A"); return
        status_parts = []; now = datetime.now(timezone.utc)
        if ticket.sla_paused_at: status_parts.append(f"Paused (since {self._format_datetime_display(ticket.sla_paused_at)})")
        if ticket.responded_at: resp_status = f"Responded: {self._format_datetime_display(ticket.responded_at)}"; (ticket.response_due_at and ticket.responded_at > ticket.response_due_at) and (resp_status += " (LATE)"); status_parts.append(resp_status)
        elif ticket.response_due_at: status_parts.append("Response: OVERDUE" if now > ticket.response_due_at else f"Response Due: {self._format_timedelta(ticket.response_due_at - now)}")
        else: status_parts.append("Response: N/A")
        if ticket.status == 'Closed': reso_status = f"Resolved: {self._format_datetime_display(ticket.updated_at)}"; (ticket.resolution_due_at and ticket.updated_at > ticket.resolution_due_at) and (reso_status += " (LATE)"); status_parts.append(reso_status)
        elif ticket.resolution_due_at: status_parts.append("Resolution: OVERDUE" if now > ticket.resolution_due_at else f"Resolution Due: {self._format_timedelta(ticket.resolution_due_at - now)}")
        else: status_parts.append("Resolution: N/A")
        self.sla_status_label.setText(" | ".join(status_parts) if status_parts else "SLA Status: N/A")

    def process_text_for_kb_links(self, text: str) -> str: # New Method
        # Pattern to find [KB: Display Text](kb://article_id)
        # Ensure Display Text does not contain ']' and article_id does not contain ')'
        pattern = r'\[KB:([^\]]+)\]\(kb:\/\/([^)\s]+)\)'

        def replace_link(match):
            display_text = match.group(1)
            article_id = match.group(2)
            # Replace with HTML anchor tag
            return f'<a href="kb://{article_id}">{display_text}</a>'

        # Replace os.linesep with <br/> for QTextBrowser display before link processing
        html_text = text.replace(os.linesep, '<br/>')
        processed_text = re.sub(pattern, replace_link, html_text)
        return processed_text

    def _populate_comments(self): # Modified
        self.comments_display.clear()
        if self.current_ticket_data and self.current_ticket_data.comments:
            full_html_content = ""
            for comment in self.current_ticket_data.comments:
                user_id = comment.get('user_id', 'Unknown User')
                timestamp_str = comment.get('timestamp', 'N/A') # Should be ISO format
                text = comment.get('text', '')

                # Process text for KB links before adding to display
                processed_text_for_display = self.process_text_for_kb_links(text)

                # Using basic HTML for structure.
                comment_html = f"<p><b>{user_id} ({timestamp_str[:19]})</b><br/>{processed_text_for_display}</p><hr style='margin: 2px 0; border-color: #eee;'/>"
                full_html_content += comment_html

            # Set the entire HTML content at once
            self.comments_display.setHtml(full_html_content if full_html_content else "<p>No comments yet.</p>")
        else:
            self.comments_display.setHtml("<p>No comments yet.</p>") # Use setHtml for consistency

    def _apply_role_permissions(self): # Unchanged from previous step
        ce=self.current_ticket_data and self.current_ticket_data.status!="Closed";ipr=self.current_user.role in ['Technician','Engineer','TechManager','EngManager'];cef=ce and ipr
        self.title_edit.setReadOnly(not cef);self.description_edit.setReadOnly(not cef);self.status_combo.setEnabled(cef);self.priority_combo.setEnabled(cef);self.type_combo.setEnabled(cef);self.assignee_edit.setReadOnly(not cef);self.update_ticket_button.setEnabled(cef)
        caoa = self.current_ticket_data and self.current_ticket_data.status != "Closed"
        self.add_comment_button.setEnabled(caoa); self.add_new_attachment_button.setEnabled(caoa); self.link_kb_button.setEnabled(caoa)

    @Slot(QUrl) # New Slot for handling clicked KB links
    def handle_kb_link_clicked(self, url: QUrl):
        if url.scheme() == 'kb':
            article_id = url.host() # For kb://article_id format
            if not article_id: # Try path if host is empty (e.g. if link was kb:article_id)
                article_id = url.path().lstrip('/')

            if article_id:
                try:
                    article = kb_get_article(article_id)
                    if article:
                        self._show_kb_article_dialog(article) # Re-use existing dialog
                    else:
                        QMessageBox.warning(self, "KB Article Not Found", f"Could not find KB article with ID: {article_id}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error retrieving KB article '{article_id}': {e}")
            else:
                QMessageBox.warning(self, "Invalid KB Link", "The KB link is malformed or missing an ID.")
        # else:
            # QDesktopServices.openUrl(url) # If we want to handle other schemes like http, mailto

    def _show_kb_article_dialog(self, article: KBArticle): # Re-used from previous step
        dialog = QDialog(self); dialog.setWindowTitle(f"KB: {article.title}"); dialog.setMinimumSize(500,400)
        layout = QVBoxLayout(dialog)
        title_l = QLabel(f"<b>{article.title}</b>"); title_l.setTextFormat(Qt.RichText); layout.addWidget(title_l)
        cat_l = QLabel(f"<i>Category: {getattr(article,'category','N/A')}</i>"); cat_l.setTextFormat(Qt.RichText); layout.addWidget(cat_l)
        kw_l = QLabel(f"<i>Keywords: {', '.join(getattr(article,'keywords',[]))}</i>"); kw_l.setTextFormat(Qt.RichText); layout.addWidget(kw_l)
        content_b = QTextBrowser(); content_b.setMarkdown(getattr(article,'content','')); content_b.setOpenExternalLinks(True); layout.addWidget(content_b)
        close_b = QPushButton("Close"); close_b.clicked.connect(dialog.accept); layout.addWidget(close_b, alignment=Qt.AlignRight)
        dialog.setLayout(layout); dialog.exec()

    # ... (Other slots like handle_select_attachments, _update_staged_files_display, handle_remove_staged_file, handle_upload_staged_attachments, handle_update_ticket, handle_add_comment, handle_link_kb_article, clear_view as before)
    @Slot()
    def handle_select_attachments(self): # Unchanged
        if not self.current_ticket_id: QMessageBox.information(self, "No Ticket Loaded", "Load ticket first."); return
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*)");
        if paths: [self.staged_files_for_upload.append((p, os.path.basename(p))) for p in paths if not any(s_p == p for s_p, _ in self.staged_files_for_upload)]; self._update_staged_files_display()
    def _update_staged_files_display(self): # Unchanged
        self.staged_attachments_list_widget.clear()
        for sp, on in self.staged_files_for_upload:
            item=QListWidgetItem();iw=QWidget();lo=QHBoxLayout(iw);lo.setContentsMargins(0,0,0,0);lbl=QLabel(on);lbl.setToolTip(sp);lo.addWidget(lbl,1)
            rb=QToolButton();rb.setText("X");rb.setFixedSize(QSize(20,20));rb.setToolTip(f"Remove {on}");rb.clicked.connect(lambda c=False,p=sp:self.handle_remove_staged_file(p))
            lo.addWidget(rb);iw.setLayout(lo);item.setSizeHint(iw.sizeHint());self.staged_attachments_list_widget.addItem(item);self.staged_attachments_list_widget.setItemWidget(item,iw)
        self.upload_staged_button.setEnabled(bool(self.staged_files_for_upload))
    @Slot(str)
    def handle_remove_staged_file(self, file_path_to_remove: str): # Unchanged
        self.staged_files_for_upload = [(p,n) for p,n in self.staged_files_for_upload if p!=file_path_to_remove]; self._update_staged_files_display()
    @Slot()
    def handle_upload_staged_attachments(self): # Unchanged
        if not self.current_ticket_id: QMessageBox.warning(self, "No Ticket", "No ticket loaded."); return
        if not self.staged_files_for_upload: QMessageBox.information(self, "No Files", "No files staged."); return
        sc=0;for sp,on in list(self.staged_files_for_upload):
            try:
                if add_attachment_to_ticket(self.current_ticket_id,self.current_user.user_id,sp,on):sc+=1
                else: QMessageBox.warning(self, "Attach Error", f"Failed to attach {on}.")
            except Exception as e: QMessageBox.warning(self, "Attach Error", f"Could not attach {on}: {e}")
        if sc>0:QMessageBox.information(self,"Upload Complete",f"{sc} file(s) uploaded.");self.staged_files_for_upload.clear();self._update_staged_files_display();self.ticket_updated.emit(self.current_ticket_id);self.load_ticket_data(self.current_ticket_id)
        elif self.staged_files_for_upload : QMessageBox.warning(self,"Upload Info","No new files uploaded.")
    def handle_open_attachment(self, att_meta): stored=att_meta.get("stored_filename");fp=os.path.join(self.attachment_base_path,stored) if stored else None; (QDesktopServices.openUrl(QUrl.fromLocalFile(fp)) if fp and os.path.exists(fp) else QMessageBox.warning(self,"Error","File not found."))
    def handle_save_attachment_as(self, att_meta):
        sf=att_meta.get("stored_filename");of=att_meta.get("original_filename","attachment");sp=os.path.join(self.attachment_base_path,sf) if sf else None
        if not sp or not os.path.exists(sp): QMessageBox.warning(self,"Error","Source file missing.");return
        sdp,_=QFileDialog.getSaveFileName(self,"Save As...",of);
        if sdp: try:shutil.copy2(sp,sdp);QMessageBox.information(self,"Success","Saved.")
                except Exception as e:QMessageBox.critical(self,"Error",f"Save failed: {e}")
    @Slot()
    def handle_remove_attachment(self, att_id: str): # Unchanged
        if not self.current_ticket_id or not att_id: return
        if QMessageBox.question(self,"Confirm","Remove attachment?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            try:
                if remove_attachment_from_ticket(self.current_ticket_id,att_id):QMessageBox.information(self,"Success","Attachment removed.");self.ticket_updated.emit(self.current_ticket_id);self.load_ticket_data(self.current_ticket_id)
                else:QMessageBox.warning(self,"Error","Failed to remove attachment.")
            except Exception as e:QMessageBox.critical(self,"Error",f"Error removing: {e}")
    @Slot()
    def handle_update_ticket(self): # Unchanged
        if not self.current_ticket_id or not self.current_ticket_data: return
        ud={};cf=False
        if self.title_edit.text()!=self.current_ticket_data.title:ud['title']=self.title_edit.text();cf=True
        if self.description_edit.toPlainText()!=self.current_ticket_data.description:ud['description']=self.description_edit.toPlainText();cf=True
        if self.status_combo.currentText()!=self.current_ticket_data.status:ud['status']=self.status_combo.currentText();cf=True
        if self.priority_combo.currentText()!=self.current_ticket_data.priority:ud['priority']=self.priority_combo.currentText();cf=True
        if self.type_combo.currentText()!=self.current_ticket_data.type:ud['type']=self.type_combo.currentText();cf=True
        a=self.assignee_edit.text().strip();ca=self.current_ticket_data.assignee_user_id
        if(a or None)!=ca:ud['assignee_user_id']=a if a else None;cf=True
        if not cf and not ud:QMessageBox.information(self,"No Changes","No changes detected.");return
        try:
            upd=update_ticket(self.current_ticket_id,**ud)
            if upd:QMessageBox.information(self,"Success","Ticket updated.");self.ticket_updated.emit(self.current_ticket_id);self.load_ticket_data(self.current_ticket_id)
            else:QMessageBox.warning(self,"Update Failed","Failed to update ticket.")
        except Exception as e:QMessageBox.critical(self,"Error",f"Update error: {e}");print(f"Error:{e}",file=sys.stderr)
    @Slot()
    def handle_add_comment(self): # Unchanged
        if not self.current_ticket_id: QMessageBox.warning(self,"No Ticket","No ticket loaded."); return
        ct=self.new_comment_edit.toPlainText().strip();
        if not ct:QMessageBox.warning(self,"Empty Comment","Comment cannot be empty.");return
        try:
            ut=add_comment_to_ticket(self.current_ticket_id,self.current_user.user_id,ct)
            if ut:QMessageBox.information(self,"Comment Added","Comment added.");self.new_comment_edit.clear();self.ticket_updated.emit(self.current_ticket_id);self.load_ticket_data(self.current_ticket_id)
            else:QMessageBox.warning(self,"Failed","Could not add comment.")
        except Exception as e:QMessageBox.critical(self,"Error",f"Error adding comment: {e}");print(f"Error:{e}",file=sys.stderr)
    @Slot()
    def handle_link_kb_article(self): # Unchanged from previous step
        dialog = KBSearchDialog(self)
        if dialog.exec() == QDialog.Accepted:
            link_data = dialog.get_selected_article_link_data()
            if link_data: article_id, article_title = link_data; link_text = f"[KB: {article_title}](kb://{article_id})"; self.new_comment_edit.insertPlainText(link_text + "\n")
    def clear_view(self): # Unchanged from previous step
        self.current_ticket_id=None;self.current_ticket_data=None
        for l in[self.ticket_id_label,self.requester_id_label,self.created_at_label,self.updated_at_label,self.sla_policy_label,self.response_due_label,self.resolution_due_label,self.responded_at_label,self.sla_status_label]:l.setText("N/A")
        for e in[self.title_edit,self.assignee_edit,self.description_edit,self.new_comment_edit]:e.clear()
        self.comments_display.clear();self.current_attachments_list_widget.clear()
        for c in[self.status_combo,self.priority_combo,self.type_combo]:c.setCurrentIndex(0)
        for f in[self.title_edit,self.description_edit,self.assignee_edit]:f.setReadOnly(True)
        for w in[self.status_combo,self.priority_combo,self.type_combo,self.update_ticket_button,self.add_comment_button,self.add_new_attachment_button,self.upload_staged_button,self.link_kb_button]:w.setEnabled(False)
        self.staged_files_for_upload.clear();self._update_staged_files_display()

if __name__ == '__main__':
    # ... (rest of __main__ as before) ...
    import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from models import User, Ticket; from ticket_manager import get_ticket, update_ticket, add_comment_to_ticket, add_attachment_to_ticket, remove_attachment_from_ticket, ATTACHMENT_DIR; from kb_manager import search_articles as kb_search_articles_main, get_article as kb_get_article_main; from kb_article import KBArticle as KBArticleMain
    except: KBArticleMain = KBArticle # Use fallback if main not available
    app = QApplication(sys.argv)
    class DU(User):
        def __init__(self,u="dv_user",r="Technician",uid="dv_uid"):self.username=u;self.role=r;self.user_id=uid;self.ROLES=User.ROLES if hasattr(User,'ROLES') else None # type: ignore
        def set_password(self,p):pass;def check_password(self,p):return False
    tu=DU()
    mdb={"T001":Ticket(id="T001",title="KB Link Test",requester_user_id="u1",created_by_user_id="u1",attachments=[{"attachment_id":"att1","original_filename":"t1.txt","stored_filename":"att1.txt","uploader_user_id":"u1","uploaded_at":datetime.now(timezone.utc).isoformat(),"filesize":1024,"mimetype":"text/plain"}],comments=[{'user_id':'u1','timestamp':datetime.now(timezone.utc).isoformat(),'text':'Please see [KB: VPN Guide](kb://kb_vpn_setup_001) for help.'},{'user_id':'u2','timestamp':datetime.now(timezone.utc).isoformat(),'text':'Also check http://example.com'}])}
    def mg(tid): return mdb.get(tid)
    def mu(tid,**kw): t=mdb.get(tid);[setattr(t,k,v) for k,v in kw.items()];t.updated_at=datetime.now(timezone.utc);return t
    def mac(tid,uid,txt):t=mdb.get(tid);t.comments.append({'user_id':uid,'text':txt,'timestamp':datetime.now(timezone.utc).isoformat()});t.updated_at=datetime.now(timezone.utc);return t
    def maat(tid,uid,src,oname):t=mdb.get(tid);nid=f"att_{len(t.attachments)+2}";t.attachments.append({'attachment_id':nid,'original_filename':oname,'stored_filename':nid+os.path.splitext(oname)[1]});t.updated_at=datetime.now(timezone.utc);return t
    def mrat(tid,attid):t=mdb.get(tid);t.attachments=[a for a in t.attachments if a['attachment_id']!=attid];t.updated_at=datetime.now(timezone.utc);return t
    def m_kb_search(q,sf=None):return [KBArticleMain(article_id="kb_vpn_setup_001",title="VPN Setup Guide",content="Content of VPN",author_user_id="admin")]
    def m_kb_get(aid):
        if aid=="kb_vpn_setup_001": return KBArticleMain(article_id=aid,title="VPN Setup Guide",content="## How to Setup VPN\n1. Download client\n2. Enter details\n3. Connect!",author_user_id="admin", category="Networking", keywords=["vpn", "remote"])
        return None

    _og=(ticket_manager.get_ticket,ticket_manager.update_ticket,ticket_manager.add_comment_to_ticket,ticket_manager.add_attachment_to_ticket,ticket_manager.remove_attachment_from_ticket,kb_manager.search_articles,kb_manager.get_article)
    ticket_manager.get_ticket,ticket_manager.update_ticket,ticket_manager.add_comment_to_ticket,ticket_manager.add_attachment_to_ticket,ticket_manager.remove_attachment_from_ticket,kb_manager.search_articles,kb_manager.get_article = mg,mu,mac,maat,mrat,m_kb_search,m_kb_get
    if not os.path.exists(ATTACHMENT_DIR):os.makedirs(ATTACHMENT_DIR)
    dv=TicketDetailView(current_user=tu);dv.load_ticket_data("T001");dv.show()
    app.exec()
    ticket_manager.get_ticket,ticket_manager.update_ticket,ticket_manager.add_comment_to_ticket,ticket_manager.add_attachment_to_ticket,ticket_manager.remove_attachment_from_ticket,kb_manager.search_articles,kb_manager.get_article = _og
