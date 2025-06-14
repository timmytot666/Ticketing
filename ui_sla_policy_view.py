import sys
import uuid
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QFormLayout,
    QMessageBox, QSpinBox, QApplication, QAbstractItemView, QHeaderView
)
from PySide6.QtCore import Slot, Qt, Signal
from PySide6.QtGui import QFont # For section titles

from typing import Optional, List, Dict, Any

try:
    from models import User # For current_user type hint
    # No direct model for SLA Policy, using Dict[str, Any]
    from settings_manager import get_sla_policies, save_sla_policies
except ModuleNotFoundError:
    print("Error: Critical modules (models, settings_manager) not found for SLAPolicyView.", file=sys.stderr)
    # Fallbacks
    class User: user_id: str = "fallback_user"
    def get_sla_policies() -> List[Dict[str, Any]]: return []
    def save_sla_policies(policies: List[Dict[str, Any]]) -> bool: return False
    # raise # Or re-raise


class SLAPolicyView(QWidget):
    # Could add a signal if other parts of the app need to know about policy changes
    # policies_updated = Signal()

    COLUMN_NAME = 0
    COLUMN_PRIORITY = 1
    COLUMN_TYPE = 2
    COLUMN_RESPONSE = 3
    COLUMN_RESOLUTION = 4

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user # For potential role-based restrictions later
        self.policies: List[Dict[str, Any]] = []
        self.selected_policy_id: Optional[str] = None

        self.setWindowTitle("SLA Policy Management")

        main_hbox_layout = QHBoxLayout(self) # Main layout: table on left, form on right

        # --- Left Side: Policies Table ---
        table_v_layout = QVBoxLayout()
        table_title = QLabel("SLA Policies"); title_font = QFont(); title_font.setBold(True); title_font.setPointSize(12); table_title.setFont(title_font)
        table_v_layout.addWidget(table_title, alignment=Qt.AlignCenter)

        self.policies_table = QTableWidget()
        self.policies_table.setColumnCount(5)
        self.policies_table.setHorizontalHeaderLabels([
            "Name", "Priority", "Ticket Type", "Response (hrs)", "Resolution (hrs)"
        ])
        self.policies_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.policies_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.policies_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.policies_table.verticalHeader().setVisible(False)
        self.policies_table.horizontalHeader().setStretchLastSection(True)
        self.policies_table.itemSelectionChanged.connect(self.handle_policy_selection)
        table_v_layout.addWidget(self.policies_table)

        main_hbox_layout.addLayout(table_v_layout, 2) # Table takes 2/3 of space

        # --- Right Side: Policy Form ---
        form_v_layout = QVBoxLayout()
        form_title = QLabel("Edit / Add Policy"); form_title.setFont(title_font)
        form_v_layout.addWidget(form_title, alignment=Qt.AlignCenter)

        self.policy_form = QFormLayout()
        self.policy_form.setRowWrapPolicy(QFormLayout.WrapAllRows)

        self.policy_id_label = QLabel("ID: <new>")
        self.policy_form.addRow(self.policy_id_label) # Display only, not editable by user

        self.name_edit = QLineEdit(); self.policy_form.addRow("Name:", self.name_edit)

        self.priority_combo = QComboBox(); self.priority_combo.addItems(["High", "Medium", "Low"])
        self.policy_form.addRow("Priority:", self.priority_combo)

        self.type_combo = QComboBox(); self.type_combo.addItems(["All", "IT", "Facilities"])
        self.policy_form.addRow("Ticket Type:", self.type_combo)

        self.response_hours_spin = QSpinBox(); self.response_hours_spin.setRange(0, 999); self.response_hours_spin.setSuffix(" hrs")
        self.policy_form.addRow("Response Time:", self.response_hours_spin)

        self.resolve_hours_spin = QSpinBox(); self.resolve_hours_spin.setRange(0, 9999); self.resolve_hours_spin.setSuffix(" hrs")
        self.policy_form.addRow("Resolution Time:", self.resolve_hours_spin)

        form_v_layout.addLayout(self.policy_form)
        form_v_layout.addStretch() # Push form elements up

        # Form Action Buttons
        form_button_layout = QHBoxLayout()
        self.add_new_button = QPushButton("Add New (Clear Form)")
        self.add_new_button.clicked.connect(self.prepare_for_new_policy)
        form_button_layout.addWidget(self.add_new_button)

        self.save_button = QPushButton("Save Policy")
        self.save_button.clicked.connect(self.handle_save_policy)
        form_button_layout.addWidget(self.save_button)
        form_v_layout.addLayout(form_button_layout)

        self.delete_button = QPushButton("Delete Selected Policy")
        self.delete_button.clicked.connect(self.handle_delete_policy)
        self.delete_button.setEnabled(False) # Initially disabled
        form_v_layout.addWidget(self.delete_button, alignment=Qt.AlignRight)

        main_hbox_layout.addLayout(form_v_layout, 1) # Form takes 1/3 of space

        self.setLayout(main_hbox_layout)
        self._load_and_display_policies()


    def _load_and_display_policies(self):
        try:
            self.policies = get_sla_policies()
            # Sort by name for consistent display, can also sort by priority then type etc.
            self.policies.sort(key=lambda p: (p.get('priority', 'Z'), p.get('ticket_type', 'Z'), p.get('name', '')))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load SLA policies: {e}")
            self.policies = []

        self.policies_table.setRowCount(0) # Clear table
        self.policies_table.setRowCount(len(self.policies))

        for row_num, policy in enumerate(self.policies):
            name_item = QTableWidgetItem(policy.get("name", "N/A"))
            name_item.setData(Qt.UserRole, policy.get("policy_id")) # Store ID in first item's UserRole
            self.policies_table.setItem(row_num, self.COLUMN_NAME, name_item)
            self.policies_table.setItem(row_num, self.COLUMN_PRIORITY, QTableWidgetItem(policy.get("priority", "N/A")))
            self.policies_table.setItem(row_num, self.COLUMN_TYPE, QTableWidgetItem(policy.get("ticket_type", "N/A")))
            self.policies_table.setItem(row_num, self.COLUMN_RESPONSE, QTableWidgetItem(str(policy.get("response_time_hours", 0))))
            self.policies_table.setItem(row_num, self.COLUMN_RESOLUTION, QTableWidgetItem(str(policy.get("resolution_time_hours", 0))))

        self.policies_table.resizeColumnsToContents()
        if self.policies_table.columnCount() > self.COLUMN_RESOLUTION : # Ensure last column stretches if needed
             self.policies_table.horizontalHeader().setStretchLastSection(True)

        self.clear_form_and_selection()


    @Slot()
    def handle_policy_selection(self):
        selected_items = self.policies_table.selectedItems()
        if not selected_items: # Selection cleared
            self.clear_form_and_selection()
            return

        selected_row = self.policies_table.currentRow() # selectedItems()[0].row()
        if selected_row < 0 or selected_row >= len(self.policies):
            self.clear_form_and_selection()
            return

        # Retrieve policy_id from UserRole of the first item in the selected row
        policy_id_item = self.policies_table.item(selected_row, self.COLUMN_NAME)
        if not policy_id_item: return

        policy_id = policy_id_item.data(Qt.UserRole)

        selected_policy = next((p for p in self.policies if p.get("policy_id") == policy_id), None)

        if selected_policy:
            self.selected_policy_id = policy_id
            self.policy_id_label.setText(f"ID: {selected_policy.get('policy_id', 'N/A')}")
            self.name_edit.setText(selected_policy.get("name", ""))
            self.priority_combo.setCurrentText(selected_policy.get("priority", "Medium"))
            self.type_combo.setCurrentText(selected_policy.get("ticket_type", "All"))
            self.response_hours_spin.setValue(int(selected_policy.get("response_time_hours", 0)))
            self.resolve_hours_spin.setValue(int(selected_policy.get("resolution_time_hours", 0)))
            self.delete_button.setEnabled(True)
        else:
            self.clear_form_and_selection()


    @Slot()
    def prepare_for_new_policy(self):
        self.clear_form_and_selection()

    def clear_form_and_selection(self):
        self.policies_table.clearSelection()
        self.selected_policy_id = None
        self.policy_id_label.setText("ID: <new policy>")
        self.name_edit.clear()
        self.priority_combo.setCurrentIndex(self.priority_combo.findText("Medium", Qt.MatchFixedString))
        self.type_combo.setCurrentIndex(self.type_combo.findText("All", Qt.MatchFixedString))
        self.response_hours_spin.setValue(0)
        self.resolve_hours_spin.setValue(0)
        self.delete_button.setEnabled(False)
        self.name_edit.setFocus() # Set focus to name for new entry

    @Slot()
    def handle_save_policy(self):
        name = self.name_edit.text().strip()
        priority = self.priority_combo.currentText()
        ticket_type = self.type_combo.currentText()
        response_hours = self.response_hours_spin.value()
        resolve_hours = self.resolve_hours_spin.value()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Policy Name cannot be empty.")
            return
        # Hours validation (already handled by QSpinBox min/max, but good to be explicit if needed)
        if response_hours < 0 or resolve_hours < 0:
            QMessageBox.warning(self, "Validation Error", "Response and Resolution hours cannot be negative.")
            return

        policy_data = {
            "name": name, "priority": priority, "ticket_type": ticket_type,
            "response_time_hours": response_hours, "resolution_time_hours": resolve_hours
        }

        if self.selected_policy_id: # Editing existing policy
            policy_data["policy_id"] = self.selected_policy_id
            # Find and update in self.policies list
            found = False
            for i, p in enumerate(self.policies):
                if p.get("policy_id") == self.selected_policy_id:
                    self.policies[i].update(policy_data)
                    found = True
                    break
            if not found:
                QMessageBox.critical(self, "Error", "Selected policy not found for update. Please refresh.")
                return
        else: # Adding new policy
            policy_data["policy_id"] = "sla_" + uuid.uuid4().hex[:10] # Generate a new unique ID
            self.policies.append(policy_data)

        try:
            if save_sla_policies(self.policies):
                QMessageBox.information(self, "Success", "SLA Policies saved successfully.")
                self._load_and_display_policies() # Refresh table and form
            else:
                QMessageBox.critical(self, "Save Error", "Failed to save SLA policies to file.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred: {e}")


    @Slot()
    def handle_delete_policy(self):
        if not self.selected_policy_id:
            QMessageBox.warning(self, "No Selection", "No policy selected for deletion.")
            return

        policy_name_to_delete = ""
        for p in self.policies:
            if p.get("policy_id") == self.selected_policy_id:
                policy_name_to_delete = p.get("name", self.selected_policy_id)
                break

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete policy: '{policy_name_to_delete}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.policies = [p for p in self.policies if p.get("policy_id") != self.selected_policy_id]
            try:
                if save_sla_policies(self.policies):
                    QMessageBox.information(self, "Success", f"Policy '{policy_name_to_delete}' deleted.")
                    self._load_and_display_policies()
                else:
                    QMessageBox.critical(self, "Delete Error", "Failed to save changes after deletion.")
            except Exception as e:
                 QMessageBox.critical(self, "Delete Error", f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Ensure settings_manager has its fallbacks if models isn't fully available
    try: from models import User
    except: pass

    app = QApplication(sys.argv)

    class DummyUserForSLAPolicyView(User):
        def __init__(self, username="sla_admin", role="EngManager", user_id_val="sla_admin_uid"):
            self.username = username; self.role = role # type: ignore
            self.user_id = user_id_val
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempRoles: __args__ = ('EngManager', 'EndUser')
                 User.ROLES = TempRoles; self.ROLES = TempRoles # type: ignore
        def set_password(self,p):pass; def check_password(self,p):return False

    test_user = DummyUserForSLAPolicyView()

    # For direct testing, you might want to use a temporary settings file
    # or ensure app_settings.json is in a known state.
    # Here, we rely on the actual settings_manager functions and app_settings.json.

    sla_view = SLAPolicyView(current_user=test_user)
    sla_view.show()
    sys.exit(app.exec())
