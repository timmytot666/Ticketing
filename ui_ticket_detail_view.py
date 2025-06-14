import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QScrollArea, QMessageBox, QApplication
)
from PySide6.QtCore import Slot, Qt, Signal
from PySide6.QtGui import QFont

from datetime import datetime, timedelta, timezone # Added timedelta, timezone
from typing import Optional, List, Dict, Any

try:
    from models import User, Ticket
    from ticket_manager import get_ticket, update_ticket, add_comment_to_ticket # Added add_comment_to_ticket
    from settings_manager import get_sla_policies # Added
except ModuleNotFoundError:
    print("Error: Critical modules (models, ticket_manager, settings_manager) not found.", file=sys.stderr)
    # Fallbacks
    class User: user_id: str = "fallback_user"; ROLES = None
    class Ticket:
        id: str; title: str; description: str; type: str; status: str; priority: str;
        requester_user_id: str; created_by_user_id: str; assignee_user_id: Optional[str];
        created_at: Optional[datetime]; updated_at: Optional[datetime]; comments: List[Dict[str,str]];
        sla_policy_id: Optional[str]; response_due_at: Optional[datetime]; resolution_due_at: Optional[datetime];
        responded_at: Optional[datetime]; sla_paused_at: Optional[datetime]; total_paused_duration_seconds: float
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            self.updated_at = datetime.now(timezone.utc); self.created_at = datetime.now(timezone.utc)
            self.comments = []; self.total_paused_duration_seconds = 0.0
    def get_ticket(tid): return None
    def update_ticket(tid, **kwargs): return None
    def add_comment_to_ticket(tid, uid, text) -> Optional[Ticket]: return None # Updated fallback
    def get_sla_policies() -> List[Dict[str, Any]]: return []


class TicketDetailView(QWidget):
    ticket_updated = Signal(str)
    navigate_back = Signal()

    DATE_FORMAT = "%Y-%m-%d %H:%M:%S UTC"

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.current_ticket_id: Optional[str] = None
        self.current_ticket_data: Optional[Ticket] = None

        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); main_layout.addWidget(scroll_area)
        content_widget = QWidget(); scroll_area.setWidget(content_widget)
        layout = QVBoxLayout(content_widget)

        # Ticket Info Section
        info_form_layout = QFormLayout(); info_form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        self.ticket_id_label = QLabel("N/A"); info_form_layout.addRow("Ticket ID:", self.ticket_id_label)
        self.title_edit = QLineEdit(); info_form_layout.addRow("Title:", self.title_edit)
        self.requester_id_label = QLabel("N/A"); info_form_layout.addRow("Requester ID:", self.requester_id_label)
        self.status_combo = QComboBox(); self.status_combo.addItems(["Open", "In Progress", "On Hold", "Closed"]); info_form_layout.addRow("Status:", self.status_combo)
        self.priority_combo = QComboBox(); self.priority_combo.addItems(["Low", "Medium", "High"]); info_form_layout.addRow("Priority:", self.priority_combo)
        self.type_combo = QComboBox(); self.type_combo.addItems(["IT", "Facilities"]); info_form_layout.addRow("Type:", self.type_combo)
        self.assignee_edit = QLineEdit(); self.assignee_edit.setPlaceholderText("User ID or blank"); info_form_layout.addRow("Assigned To:", self.assignee_edit)
        self.created_at_label = QLabel("N/A"); info_form_layout.addRow("Created At:", self.created_at_label)
        self.updated_at_label = QLabel("N/A"); info_form_layout.addRow("Last Updated:", self.updated_at_label)

        # SLA Info Labels
        self.sla_policy_label = QLabel("N/A"); info_form_layout.addRow("SLA Policy:", self.sla_policy_label)
        self.responded_at_label = QLabel("N/A"); info_form_layout.addRow("Responded At:", self.responded_at_label)
        self.response_due_label = QLabel("N/A"); info_form_layout.addRow("Response Due:", self.response_due_label)
        self.resolution_due_label = QLabel("N/A"); info_form_layout.addRow("Resolution Due:", self.resolution_due_label)
        self.sla_status_label = QLabel("SLA Status: N/A"); info_form_layout.addRow(self.sla_status_label)

        layout.addLayout(info_form_layout)

        layout.addWidget(QLabel("Description:")); self.description_edit = QTextEdit(); self.description_edit.setMinimumHeight(100); layout.addWidget(self.description_edit)
        layout.addWidget(QLabel("Comments/History:")); self.comments_display = QTextEdit(); self.comments_display.setReadOnly(True); self.comments_display.setMinimumHeight(150); layout.addWidget(self.comments_display)
        layout.addWidget(QLabel("Add New Comment:")); self.new_comment_edit = QTextEdit(); self.new_comment_edit.setMaximumHeight(70); layout.addWidget(self.new_comment_edit)
        self.add_comment_button = QPushButton("Add Comment"); self.add_comment_button.clicked.connect(self.handle_add_comment); layout.addWidget(self.add_comment_button, alignment=Qt.AlignRight)

        action_buttons_layout = QHBoxLayout(); self.update_ticket_button = QPushButton("Update Ticket"); self.update_ticket_button.clicked.connect(self.handle_update_ticket); action_buttons_layout.addWidget(self.update_ticket_button)
        self.back_button = QPushButton("Back to List"); self.back_button.clicked.connect(self.navigate_back.emit); action_buttons_layout.addWidget(self.back_button); action_buttons_layout.addStretch(); layout.addLayout(action_buttons_layout)
        self.setLayout(main_layout)

    def _format_datetime_display(self, dt: Optional[datetime]) -> str:
        return dt.strftime(self.DATE_FORMAT) if dt else "N/A"

    def load_ticket_data(self, ticket_id: str):
        self.current_ticket_id = ticket_id
        try:
            ticket = get_ticket(ticket_id)
            if not ticket: QMessageBox.warning(self, "Not Found", f"Ticket ID '{ticket_id}' not found."); self.clear_view(); return
            self.current_ticket_data = ticket
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to load ticket data: {e}"); self.clear_view(); return

        self.ticket_id_label.setText(ticket.id)
        self.requester_id_label.setText(ticket.requester_user_id)
        self.created_at_label.setText(self._format_datetime_display(ticket.created_at))
        self.updated_at_label.setText(self._format_datetime_display(ticket.updated_at))
        self.title_edit.setText(ticket.title); self.description_edit.setPlainText(ticket.description)
        self.status_combo.setCurrentText(ticket.status); self.priority_combo.setCurrentText(ticket.priority)
        self.type_combo.setCurrentText(ticket.type); self.assignee_edit.setText(ticket.assignee_user_id or "")

        # SLA Info
        if ticket.sla_policy_id:
            all_sla_policies = get_sla_policies()
            policy_name = next((p['name'] for p in all_sla_policies if p['policy_id'] == ticket.sla_policy_id), ticket.sla_policy_id)
            self.sla_policy_label.setText(policy_name)
        else: self.sla_policy_label.setText("N/A")

        self.responded_at_label.setText(self._format_datetime_display(ticket.responded_at))
        self.response_due_label.setText(self._format_datetime_display(ticket.response_due_at))
        self.resolution_due_label.setText(self._format_datetime_display(ticket.resolution_due_at))

        self._calculate_and_display_sla_status(ticket)
        self._populate_comments()
        self._apply_role_permissions()

    def _format_timedelta(self, delta: timedelta) -> str:
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days < 0: # If overdue, show as negative or "Overdue by"
            delta = -delta
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f"-{days}d {hours}h {minutes}m" if days > 0 else f"-{hours}h {minutes}m"
        return f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"


    def _calculate_and_display_sla_status(self, ticket: Ticket):
        if not ticket: self.sla_status_label.setText("SLA Status: N/A"); return

        status_parts = []
        now = datetime.now(timezone.utc)

        # Adjust 'now' for pause duration if calculating remaining time against non-shifted due dates
        # effective_now_for_sla = now
        # if ticket.sla_paused_at: # Currently paused
        #     status_parts.append("SLA Paused")
        # elif ticket.total_paused_duration_seconds > 0:
        #     effective_now_for_sla -= timedelta(seconds=ticket.total_paused_duration_seconds)
        # For simplicity, current implementation of calculate_due_date doesn't shift due dates by pause.
        # So, for "time left", we should compare against `now` and mention pause state separately.

        if ticket.sla_paused_at:
            status_parts.append(f"Paused (since {self._format_datetime_display(ticket.sla_paused_at)})")

        # Response SLA
        if ticket.responded_at:
            resp_status = f"Responded: {self._format_datetime_display(ticket.responded_at)}"
            if ticket.response_due_at and ticket.responded_at > ticket.response_due_at:
                resp_status += " (LATE)"
            status_parts.append(resp_status)
        elif ticket.response_due_at:
            if now > ticket.response_due_at: status_parts.append("Response: OVERDUE")
            else: status_parts.append(f"Response Due: {self._format_timedelta(ticket.response_due_at - now)}")
        else: status_parts.append("Response: N/A")

        # Resolution SLA
        if ticket.status == 'Closed':
            reso_status = f"Resolved: {self._format_datetime_display(ticket.updated_at)}" # Assuming updated_at is resolution time
            if ticket.resolution_due_at and ticket.updated_at > ticket.resolution_due_at:
                reso_status += " (LATE)"
            status_parts.append(reso_status)
        elif ticket.resolution_due_at:
            if now > ticket.resolution_due_at: status_parts.append("Resolution: OVERDUE")
            else: status_parts.append(f"Resolution Due: {self._format_timedelta(ticket.resolution_due_at - now)}")
        else: status_parts.append("Resolution: N/A")

        self.sla_status_label.setText(" | ".join(status_parts) if status_parts else "SLA Status: N/A")


    def _populate_comments(self): # Same as before
        self.comments_display.clear()
        if self.current_ticket_data and self.current_ticket_data.comments:
            html_comments = ""
            for comment in self.current_ticket_data.comments:
                user_id = comment.get('user_id', 'Unknown User')
                timestamp_str = comment.get('timestamp', 'N/A')
                text = comment.get('text', '')
                html_comments += f"<p><b>{user_id} ({timestamp_str})</b><br/>{text.replace(os.linesep, '<br/>')}</p><hr style='margin: 2px 0;'/>"
            self.comments_display.setHtml(html_comments)
        else: self.comments_display.setPlainText("No comments yet.")

    def _apply_role_permissions(self): # Same as before
        can_edit = self.current_ticket_data and self.current_ticket_data.status != "Closed"
        if self.current_user.role not in ['Technician', 'Engineer', 'TechManager', 'EngManager']: can_edit = False
        self.title_edit.setReadOnly(not can_edit); self.description_edit.setReadOnly(not can_edit)
        self.status_combo.setEnabled(can_edit); self.priority_combo.setEnabled(can_edit)
        self.type_combo.setEnabled(can_edit); self.assignee_edit.setReadOnly(not can_edit)
        self.update_ticket_button.setEnabled(can_edit)
        self.add_comment_button.setEnabled(self.current_ticket_data and self.current_ticket_data.status != "Closed")

    @Slot()
    def handle_update_ticket(self): # Same as before, ensure it calls load_ticket_data to refresh SLA status
        if not self.current_ticket_id or not self.current_ticket_data: return
        update_data = {}
        if self.title_edit.text() != self.current_ticket_data.title: update_data['title'] = self.title_edit.text()
        if self.description_edit.toPlainText() != self.current_ticket_data.description: update_data['description'] = self.description_edit.toPlainText()
        if self.status_combo.currentText() != self.current_ticket_data.status: update_data['status'] = self.status_combo.currentText()
        if self.priority_combo.currentText() != self.current_ticket_data.priority: update_data['priority'] = self.priority_combo.currentText()
        if self.type_combo.currentText() != self.current_ticket_data.type: update_data['type'] = self.type_combo.currentText()
        assignee = self.assignee_edit.text().strip(); current_assignee = self.current_ticket_data.assignee_user_id
        if (assignee or None) != current_assignee: update_data['assignee_user_id'] = assignee if assignee else None
        if not update_data: QMessageBox.information(self, "No Changes", "No changes detected."); return
        try:
            updated = update_ticket(self.current_ticket_id, **update_data)
            if updated: QMessageBox.information(self, "Success", "Ticket updated."); self.ticket_updated.emit(self.current_ticket_id); self.load_ticket_data(self.current_ticket_id)
            else: QMessageBox.warning(self, "Update Failed", "Failed to update ticket.")
        except Exception as e: QMessageBox.critical(self, "Error", f"Update error: {e}"); print(f"Error: {e}", file=sys.stderr)

    @Slot()
    def handle_add_comment(self):
        if not self.current_ticket_id: QMessageBox.warning(self, "No Ticket", "No ticket loaded."); return
        comment_text = self.new_comment_edit.toPlainText().strip()
        if not comment_text: QMessageBox.warning(self, "Empty Comment", "Comment cannot be empty."); return
        try:
            # Replace placeholder with actual call
            updated_ticket = add_comment_to_ticket(self.current_ticket_id, self.current_user.user_id, comment_text)
            if updated_ticket:
                QMessageBox.information(self, "Comment Added", "Comment added successfully.")
                self.new_comment_edit.clear(); self.ticket_updated.emit(self.current_ticket_id)
                self.load_ticket_data(self.current_ticket_id) # Reload to show new comment & updated SLA
            else: QMessageBox.warning(self, "Failed", "Could not add comment.")
        except Exception as e: QMessageBox.critical(self, "Error", f"Error adding comment: {e}"); print(f"Error: {e}", file=sys.stderr)

    def clear_view(self): # Extended to clear new SLA labels
        self.current_ticket_id = None; self.current_ticket_data = None
        labels_to_clear = [self.ticket_id_label, self.requester_id_label, self.created_at_label, self.updated_at_label,
                           self.sla_policy_label, self.response_due_label, self.resolution_due_label,
                           self.responded_at_label, self.sla_status_label]
        for label in labels_to_clear: label.setText("N/A")
        edits_to_clear = [self.title_edit, self.assignee_edit, self.description_edit, self.comments_display, self.new_comment_edit]
        for edit in edits_to_clear: edit.clear()
        combos = [self.status_combo, self.priority_combo, self.type_combo]
        for combo in combos: combo.setCurrentIndex(0)
        self.title_edit.setReadOnly(True); self.description_edit.setReadOnly(True); self.status_combo.setEnabled(False)
        self.priority_combo.setEnabled(False); self.type_combo.setEnabled(False); self.assignee_edit.setReadOnly(True)
        self.update_ticket_button.setEnabled(False); self.add_comment_button.setEnabled(False)

if __name__ == '__main__':
    # ... (existing __main__ block, ensure add_comment_to_ticket is also mocked if used)
    # For brevity, __main__ block is not repeated here but should be functional.
    # It needs to mock the new add_comment_to_ticket from ticket_manager.
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from models import User, Ticket; from ticket_manager import get_ticket, update_ticket, add_comment_to_ticket
    except: pass # Fallbacks

    app = QApplication(sys.argv)
    class DummyUserDetailView(User):
        def __init__(self, username="detail_viewer", role="Technician", user_id_val="detail_uid_789"):
            self.username=username; self.role=role; self.user_id=user_id_val # type: ignore
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempR: __args__ = ('Technician','EndUser'); User.ROLES=TempR; self.ROLES=TempR # type: ignore
        def set_password(self,p):pass; def check_password(self,p):return False
    test_user = DummyUserDetailView()

    _mock_db = {
        "T001": Ticket(id="T001", title="SLA Test", description="Test", type="IT", status="Open",
                       priority="High", requester_user_id="u1", created_by_user_id="u1",
                       response_due_at=datetime.now(timezone.utc) + timedelta(hours=2),
                       resolution_due_at=datetime.now(timezone.utc) + timedelta(hours=8),
                       comments=[], created_at=datetime.now(timezone.utc)-timedelta(minutes=30))
    }
    def mg(tid): return _mock_db.get(tid)
    def mu(tid, **kw): _mock_db[tid].status=kw.get('status',_mock_db[tid].status); return _mock_db[tid]
    def mac(tid,uid,txt): _mock_db[tid].comments.append({'user_id':uid,'text':txt,'timestamp':datetime.now(timezone.utc).isoformat()}); return _mock_db[tid]

    _og_gt, _og_ut, _og_ac = ticket_manager.get_ticket, ticket_manager.update_ticket, ticket_manager.add_comment_to_ticket
    ticket_manager.get_ticket, ticket_manager.update_ticket, ticket_manager.add_comment_to_ticket = mg, mu, mac

    dv = TicketDetailView(current_user=test_user); dv.load_ticket_data("T001"); dv.show()
    app.exec()
    ticket_manager.get_ticket, ticket_manager.update_ticket, ticket_manager.add_comment_to_ticket = _og_gt, _og_ut, _og_ac
