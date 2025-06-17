import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QGroupBox, QApplication, QMessageBox
)
from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QFont, QShowEvent


from typing import Optional, List, Dict, Any

try:
    from models import User
    from user_manager import list_all_users, create_user, update_user_profile
except ModuleNotFoundError:
    print("Error: models.py or user_manager.py not found for UserManagementView.", file=sys.stderr)
    class User:
        ROLES = type('ROLES', (), {'__args__': ('Admin', 'User')})() # type: ignore
        user_id: str = "fb_uid"; username: str = "fb_user"; role: Any = "User"
        is_active: bool = True; force_password_reset: bool = False
        def __init__(self, username, role, user_id_val="fb_uid",is_active=True,force_password_reset=False):
            self.username=username; self.role=role; self.user_id=user_id_val; self.is_active=is_active; self.force_password_reset=force_password_reset
    def list_all_users(filters=None, sort_by='u', reverse_sort=False): return []
    def create_user(u,p,r,ia=True,fpr=False): return None
    def update_user_profile(uid,r=None,ia=None,fpr=None): return None

MIN_PASSWORD_LENGTH = 8 # Consistent with ChangePasswordDialog

class UserManagementView(QWidget):
    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.selected_user_id: Optional[str] = None
        self.users_list_data: List[User] = []

        self.setWindowTitle("User Management")
        main_layout = QVBoxLayout(self)

        # --- Filter/Search Section ---
        filter_groupbox = QGroupBox("Filters & Search")
        filter_layout = QGridLayout(filter_groupbox)
        filter_layout.addWidget(QLabel("Username:"), 0, 0); self.username_search_edit = QLineEdit(); self.username_search_edit.setPlaceholderText("Search Username..."); filter_layout.addWidget(self.username_search_edit, 0, 1)
        filter_layout.addWidget(QLabel("Role:"), 0, 2); self.role_filter_combo = QComboBox(); self.role_filter_combo.addItem("All Roles");
        if hasattr(User, 'ROLES') and User.ROLES and hasattr(User.ROLES, '__args__'): self.role_filter_combo.addItems(User.ROLES.__args__) # type: ignore
        filter_layout.addWidget(self.role_filter_combo, 0, 3)
        filter_layout.addWidget(QLabel("Status:"), 1, 0); self.active_filter_combo = QComboBox(); self.active_filter_combo.addItems(["All", "Active", "Inactive"]); filter_layout.addWidget(self.active_filter_combo, 1, 1)
        filter_layout.addWidget(QLabel("Force Reset:"), 1, 2); self.force_reset_filter_combo = QComboBox(); self.force_reset_filter_combo.addItems(["All", "Yes", "No"]); filter_layout.addWidget(self.force_reset_filter_combo, 1, 3)
        filter_buttons_layout = QHBoxLayout(); self.apply_filters_button = QPushButton("Apply Filters"); filter_buttons_layout.addWidget(self.apply_filters_button)
        self.refresh_list_button = QPushButton("Refresh All / Clear Filters"); filter_buttons_layout.addWidget(self.refresh_list_button); filter_buttons_layout.addStretch(); filter_layout.addLayout(filter_buttons_layout, 2, 0, 1, 4)
        main_layout.addWidget(filter_groupbox)

        # --- User List Section ---
        user_list_groupbox = QGroupBox("Users"); user_list_layout = QVBoxLayout(user_list_groupbox)
        self.users_table = QTableWidget(); self.users_table.setColumnCount(5); self.users_table.setHorizontalHeaderLabels(["Username", "Role", "Is Active", "Force Reset", "User ID"])
        self.users_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection); self.users_table.verticalHeader().setVisible(False)
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch);
        for i in range(1,5): self.users_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        user_list_layout.addWidget(self.users_table); main_layout.addWidget(user_list_groupbox)

        # --- Edit/Add User Section ---
        details_groupbox = QGroupBox("User Details"); details_main_layout = QVBoxLayout(details_groupbox)
        form_layout = QFormLayout(); self.detail_user_id_label = QLabel("User ID: N/A"); form_layout.addRow(self.detail_user_id_label)
        self.detail_username_edit = QLineEdit()
        form_layout.addRow(QLabel("Username:"), self.detail_username_edit)
        self.detail_role_combo = QComboBox();
        if hasattr(User, 'ROLES') and User.ROLES and hasattr(User.ROLES, '__args__'): self.detail_role_combo.addItems(User.ROLES.__args__) # type: ignore
        form_layout.addRow(QLabel("Role:"), self.detail_role_combo)

        self.phone_edit = QLineEdit(); form_layout.addRow("Phone:", self.phone_edit)
        self.email_edit = QLineEdit(); form_layout.addRow("Email:", self.email_edit)
        self.department_edit = QLineEdit(); form_layout.addRow("Department:", self.department_edit)

        checkbox_layout = QHBoxLayout()
        self.detail_is_active_check = QCheckBox("Is Active")
        checkbox_layout.addWidget(self.detail_is_active_check)
        self.detail_force_reset_check = QCheckBox("Force Password Reset")
        checkbox_layout.addWidget(self.detail_force_reset_check); form_layout.addRow(checkbox_layout)
        self.password_group_widget = QWidget(); password_qform_layout = QFormLayout(self.password_group_widget); password_qform_layout.setContentsMargins(0,0,0,0)
        self.detail_new_password_edit = QLineEdit(); self.detail_new_password_edit.setEchoMode(QLineEdit.Password)
        password_qform_layout.addRow(QLabel("New Password:"), self.detail_new_password_edit)
        self.detail_confirm_password_edit = QLineEdit(); self.detail_confirm_password_edit.setEchoMode(QLineEdit.Password)
        password_qform_layout.addRow(QLabel("Confirm Password:"), self.detail_confirm_password_edit)
        form_layout.addRow(self.password_group_widget)
        self.message_label = QLabel(""); self.message_label.setAlignment(Qt.AlignCenter); form_layout.addRow(self.message_label)
        details_main_layout.addLayout(form_layout)
        form_action_buttons_layout = QHBoxLayout(); self.add_new_button = QPushButton("Add New User Mode"); form_action_buttons_layout.addWidget(self.add_new_button)
        self.save_button = QPushButton("Save Changes"); form_action_buttons_layout.addWidget(self.save_button); form_action_buttons_layout.addStretch(); details_main_layout.addLayout(form_action_buttons_layout)
        main_layout.addWidget(details_groupbox)
        self.setLayout(main_layout)

        # Connections
        self.apply_filters_button.clicked.connect(self.handle_apply_filters)
        self.refresh_list_button.clicked.connect(self.handle_refresh_list)
        self.users_table.itemSelectionChanged.connect(self.handle_user_selection)
        self.add_new_button.clicked.connect(self.handle_add_new_user_mode)
        self.save_button.clicked.connect(self.handle_save_changes)

        self.handle_refresh_list() # Initial load and form reset

    def _set_form_for_new_user(self, is_new: bool):
        self.detail_username_edit.setReadOnly(not is_new)
        self.password_group_widget.setVisible(is_new)
        if is_new:
            self.selected_user_id = None
            self.detail_user_id_label.setText("User ID: <new_auto_generated>")
            self.detail_username_edit.clear()
            self.detail_role_combo.setCurrentIndex(0) if self.detail_role_combo.count() > 0 else None
            self.detail_is_active_check.setChecked(True)
            self.detail_force_reset_check.setChecked(False)
            self.phone_edit.clear()
            self.email_edit.clear()
            self.department_edit.clear()
            self.detail_new_password_edit.clear(); self.detail_confirm_password_edit.clear()
            self.users_table.clearSelection()
            self.message_label.setText("Enter details for the new user.")
            self.detail_username_edit.setFocus()
        else: # Editing existing, or form disabled (after selection cleared)
            self.password_group_widget.setVisible(False) # Password change via force_reset or user themselves
            if not self.selected_user_id: # If no actual user is selected (e.g. after refresh)
                self.detail_user_id_label.setText("User ID: N/A")
                self.detail_username_edit.clear()
                self.detail_role_combo.setCurrentIndex(-1)
                self.phone_edit.clear()
                self.email_edit.clear()
                self.department_edit.clear()
                self.detail_is_active_check.setChecked(False)
                self.detail_force_reset_check.setChecked(False)
                self.message_label.setText("Select a user from the list to edit, or click 'Add New'.")

    @Slot()
    def _load_and_display_users(self):
        filters: Dict[str, Any] = {}
        username_query = self.username_search_edit.text().strip()
        if username_query: filters['username'] = username_query

        role_query = self.role_filter_combo.currentText()
        if role_query != "All Roles": filters['role'] = role_query

        active_query = self.active_filter_combo.currentText()
        if active_query == "Active": filters['is_active'] = True
        elif active_query == "Inactive": filters['is_active'] = False

        reset_query = self.force_reset_filter_combo.currentText()
        if reset_query == "Yes": filters['force_password_reset'] = True
        elif reset_query == "No": filters['force_password_reset'] = False

        try:
            self.users_list_data = list_all_users(filters=filters, sort_by='username')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load users: {e}")
            self.users_list_data = []

        self.users_table.setRowCount(0)
        self.users_table.setRowCount(len(self.users_list_data))
        for row, user in enumerate(self.users_list_data):
            username_item = QTableWidgetItem(user.username); username_item.setData(Qt.UserRole, user.user_id)
            self.users_table.setItem(row, 0, username_item)
            self.users_table.setItem(row, 1, QTableWidgetItem(user.role))
            self.users_table.setItem(row, 2, QTableWidgetItem("Yes" if user.is_active else "No"))
            self.users_table.setItem(row, 3, QTableWidgetItem("Yes" if user.force_password_reset else "No"))
            self.users_table.setItem(row, 4, QTableWidgetItem(user.user_id[:8] + "...")) # Shortened ID

        self.users_table.resizeColumnsToContents()
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        # Re-select or clear form based on whether the selected user is still in the filtered list
        if self.selected_user_id:
            matching_user = next((u for u in self.users_list_data if u.user_id == self.selected_user_id), None)
            if matching_user:
                # Try to re-select in table (might not work perfectly if sorting changed order significantly)
                for r in range(self.users_table.rowCount()):
                    if self.users_table.item(r,0).data(Qt.UserRole) == self.selected_user_id:
                        self.users_table.selectRow(r)
                        break
            else: # Previously selected user is no longer in the filtered list
                self._set_form_for_new_user(False) # Reset form to disabled state
                self.selected_user_id = None # Clear selection as it's not visible
        else: # No user was selected before
            self._set_form_for_new_user(False) # Ensure form is in a sensible default state (disabled)


    @Slot()
    def handle_apply_filters(self): self._load_and_display_users()
    @Slot()
    def handle_refresh_list(self):
        self.username_search_edit.clear()
        self.role_filter_combo.setCurrentIndex(0) # "All Roles"
        self.active_filter_combo.setCurrentIndex(0) # "All"
        self.force_reset_filter_combo.setCurrentIndex(0) # "All"
        self._load_and_display_users()
        self._set_form_for_new_user(True) # Reset form to "new user" mode

    @Slot()
    def handle_user_selection(self):
        selected_items = self.users_table.selectedItems()
        if not selected_items: self._set_form_for_new_user(False); return # No selection or selection cleared

        selected_row = self.users_table.currentRow()
        if selected_row < 0: self._set_form_for_new_user(False); return

        user_id_item = self.users_table.item(selected_row, 0) # Username item has user_id in UserRole
        if not user_id_item: self._set_form_for_new_user(False); return

        self.selected_user_id = user_id_item.data(Qt.UserRole)
        user = next((u for u in self.users_list_data if u.user_id == self.selected_user_id), None)

        if user:
            self._set_form_for_new_user(False) # Configure form for editing
            self.detail_user_id_label.setText(f"User ID: {user.user_id}")
            self.detail_username_edit.setText(user.username)
            self.detail_role_combo.setCurrentText(user.role)
            self.phone_edit.setText(user.phone or "")
            self.email_edit.setText(user.email or "")
            self.department_edit.setText(user.department or "")
            self.detail_is_active_check.setChecked(user.is_active)
            self.detail_force_reset_check.setChecked(user.force_password_reset)
            self.message_label.setText(f"Editing user: {user.username}")
        else: # Should not happen if table selection is valid and users_list_data is current
            self._set_form_for_new_user(True)
            self.message_label.setText("Error: Selected user not found in local data.")


    @Slot()
    def handle_add_new_user_mode(self): self._set_form_for_new_user(True)

    @Slot()
    def handle_save_changes(self):
        username = self.detail_username_edit.text().strip()
        role = self.detail_role_combo.currentText()
        is_active = self.detail_is_active_check.isChecked()
        force_reset = self.detail_force_reset_check.isChecked()

        phone = self.phone_edit.text().strip()
        email = self.email_edit.text().strip()
        department = self.department_edit.text().strip()

        try:
            if self.selected_user_id: # Editing existing user
                if not username: # Username cannot be emptied for existing user (models.User validates non-empty on init)
                    QMessageBox.warning(self, "Validation Error", "Username cannot be empty.")
                    return

                update_payload = {
                    "role": role,
                    "is_active": is_active,
                    "force_password_reset": force_reset,
                    "phone": phone if phone else None,
                    "email": email if email else None,
                    "department": department if department else None
                }
                updated_user = update_user_profile(self.selected_user_id, **update_payload)
                if updated_user:
                    self.message_label.setText(f"User '{updated_user.username}' updated successfully.");
                    QMessageBox.information(self, "Success", f"User '{updated_user.username}' updated.")
                else:
                    self.message_label.setText(f"Failed to update user '{username}'.");
                    QMessageBox.warning(self, "Update Failed", "Could not update user details.")
            else: # Adding new user
                if not username: QMessageBox.warning(self, "Input Error", "Username cannot be empty."); return
                password = self.detail_new_password_edit.text()
                confirm_password = self.detail_confirm_password_edit.text()
                if not password: QMessageBox.warning(self, "Input Error", "Password cannot be empty for new user."); return
                if len(password) < MIN_PASSWORD_LENGTH: QMessageBox.warning(self, "Input Error", f"Password must be at least {MIN_PASSWORD_LENGTH} characters."); return
                if password != confirm_password: QMessageBox.warning(self, "Input Error", "Passwords do not match."); return

                new_user = create_user(
                    username,
                    password,
                    role,
                    is_active=is_active,
                    force_password_reset=force_reset,
                    phone=phone if phone else None,
                    email=email if email else None,
                    department=department if department else None
                )
                self.message_label.setText(f"User '{new_user.username}' created successfully.");
                QMessageBox.information(self, "Success", f"User '{new_user.username}' created.")
                self._set_form_for_new_user(True) # Reset for another new user

            self._load_and_display_users() # Refresh table
        except ValueError as ve:
            self.message_label.setText(f"Error: {ve}"); QMessageBox.critical(self, "Validation Error", str(ve))
        except Exception as e:
            self.message_label.setText("An unexpected error occurred."); QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
            print(f"Error saving user: {e}", file=sys.stderr)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if event.isAccepted():
            self.handle_refresh_list() # Load all users and reset form to new

if __name__ == '__main__':
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try: from models import User
    except: pass

    app = QApplication(sys.argv)
    class DUFMV(User):
        def __init__(self, u="admin", r="TechManager", uid="admin_uid"):
            self.username=u; self.role=r; self.user_id=uid #type: ignore
            if not hasattr(User, 'ROLES') or User.ROLES is None or not hasattr(User.ROLES, '__args__'):
                 class TR: __args__ = ('EndUser', 'Technician', 'Engineer', 'TechManager', 'EngManager')
                 User.ROLES = TR #type: ignore
            self.ROLES = User.ROLES #type: ignore
        def set_password(self,p):pass
        def check_password(self,p):return False

    # Mock user_manager functions for standalone UI test
    _MOCK_USERS_DB: List[User] = []
    _original_list_all_users = user_manager.list_all_users
    _original_create_user = user_manager.create_user
    _original_update_user_profile = user_manager.update_user_profile

    def mock_list_all(filters=None, sort_by='username', reverse_sort=False):
        print(f"MOCK list_all_users with filters: {filters}"); users_copy = list(_MOCK_USERS_DB) # Operate on copy
        # Simplified filtering for mock
        if filters:
            if 'username' in filters: users_copy = [u for u in users_copy if filters['username'].lower() in u.username.lower()]
            if 'role' in filters: users_copy = [u for u in users_copy if u.role == filters['role']]
            if 'is_active' in filters: users_copy = [u for u in users_copy if u.is_active == filters['is_active']]
        users_copy.sort(key=lambda u: getattr(u, sort_by, ""), reverse=reverse_sort)
        return users_copy

    def mock_create(username, password, role, is_active=True, force_password_reset=False):
        print(f"MOCK create_user: {username}, Role: {role}")
        if any(u.username == username for u in _MOCK_USERS_DB): raise ValueError("Username already exists.")
        new_user = User(username=username, role=role, is_active=is_active, force_password_reset=force_password_reset)
        new_user.user_id = f"user_{len(_MOCK_USERS_DB)+1}" # Simple ID
        # new_user.set_password(password) # Not needed for mock as hash not stored directly
        _MOCK_USERS_DB.append(new_user); return new_user

    def mock_update(user_id, role=None, is_active=None, force_password_reset=None):
        print(f"MOCK update_user_profile: {user_id}")
        for u in _MOCK_USERS_DB:
            if u.user_id == user_id:
                if role is not None: u.role = role
                if is_active is not None: u.is_active = is_active
                if force_password_reset is not None: u.force_password_reset = force_password_reset
                return u
        return None

    user_manager.list_all_users = mock_list_all
    user_manager.create_user = mock_create
    user_manager.update_user_profile = mock_update

    # Populate with some initial mock users
    mock_create("test_enduser", "pass", "EndUser")
    mock_create("test_tech", "pass", "Technician", is_active=False)
    mock_create("test_manager", "pass", "TechManager", force_password_reset=True)

    test_admin_user = DUFMV()
    view = UserManagementView(current_user=test_admin_user); view.show()
    app.exec()

    user_manager.list_all_users = _original_list_all_users
    user_manager.create_user = _original_create_user
    user_manager.update_user_profile = _original_update_user_profile
