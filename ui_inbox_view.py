import sys
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView,
    QApplication, # For direct test
    QMessageBox
)
from PySide6.QtCore import Slot, Qt, Signal, QShowEvent
from PySide6.QtGui import QFont

from datetime import datetime
from typing import Optional, List

try:
    from models import User, Notification
    from notification_manager import get_notifications_for_user, mark_notification_as_read, mark_multiple_notifications_as_read
except ModuleNotFoundError:
    print("Error: Critical modules (models, notification_manager) not found.", file=sys.stderr)
    # Fallbacks
    class User: user_id: str = "fallback_user"
    class Notification:
        notification_id: str; message: str; ticket_id: Optional[str]; timestamp: datetime; is_read: bool
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            self.timestamp = datetime.now()
            self.is_read = False
    def get_notifications_for_user(user_id, unread_only=False): return []
    def mark_notification_as_read(nid): return False
    def mark_multiple_notifications_as_read(nids): return 0
    # raise # Or re-raise

class InboxView(QWidget):
    notifications_updated = Signal() # Signal to notify main window to update its indicator

    COLUMN_STATUS = 0
    COLUMN_MESSAGE = 1
    COLUMN_TICKET_ID = 2
    COLUMN_DATE = 3

    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user

        self.setWindowTitle("My Notifications Inbox")

        main_layout = QVBoxLayout(self)

        # Action Buttons Layout
        actions_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_user_notifications)
        actions_layout.addWidget(self.refresh_button)

        self.mark_as_read_button = QPushButton("Mark Selected as Read")
        self.mark_as_read_button.clicked.connect(self.handle_mark_selected_as_read)
        actions_layout.addWidget(self.mark_as_read_button)
        actions_layout.addStretch() # Push buttons to the left
        main_layout.addLayout(actions_layout)

        # Notifications Table
        self.notifications_table = QTableWidget()
        self.notifications_table.setColumnCount(4)
        self.notifications_table.setHorizontalHeaderLabels([
            "Status", "Message", "Ticket ID", "Date"
        ])
        self.notifications_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notifications_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.notifications_table.setSelectionMode(QAbstractItemView.ExtendedSelection) # Allow multiple rows
        self.notifications_table.verticalHeader().setVisible(False)
        self.notifications_table.horizontalHeader().setStretchLastSection(False) # Date column fixed
        self.notifications_table.horizontalHeader().setSectionResizeMode(self.COLUMN_MESSAGE, QHeaderView.Stretch)
        self.notifications_table.horizontalHeader().setSectionResizeMode(self.COLUMN_STATUS, QHeaderView.ResizeToContents)
        self.notifications_table.horizontalHeader().setSectionResizeMode(self.COLUMN_TICKET_ID, QHeaderView.ResizeToContents)
        self.notifications_table.horizontalHeader().setSectionResizeMode(self.COLUMN_DATE, QHeaderView.ResizeToContents)

        self.notifications_table.itemDoubleClicked.connect(self.handle_item_double_click)
        main_layout.addWidget(self.notifications_table)

        self.setLayout(main_layout)

    @Slot()
    def load_user_notifications(self):
        if hasattr(self.current_user, 'user_id'):
            self._populate_notifications_table(self.current_user.user_id)
        else:
            print("Error: current_user has no user_id attribute.", file=sys.stderr)
            self.notifications_table.setRowCount(0)
            QMessageBox.critical(self, "Error", "Cannot load notifications: User information is missing.")


    def _populate_notifications_table(self, user_id: str):
        self.notifications_table.setRowCount(0)
        try:
            notifications: List[Notification] = get_notifications_for_user(user_id=user_id, unread_only=False)
        except Exception as e:
            print(f"Error fetching notifications: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"Could not load notifications: {e}")
            return

        if notifications: # Sort by timestamp descending (most recent first)
            notifications.sort(key=lambda n: n.timestamp, reverse=True)

        self.notifications_table.setRowCount(len(notifications))
        bold_font = QFont()
        bold_font.setBold(True)

        for row_num, notification in enumerate(notifications):
            # Store notification_id in UserRole of the first item for easy retrieval
            status_item = QTableWidgetItem("Unread" if not notification.is_read else "Read")
            status_item.setData(Qt.UserRole, notification.notification_id)

            message_item = QTableWidgetItem(notification.message)
            ticket_id_item = QTableWidgetItem(notification.ticket_id if notification.ticket_id else "N/A")
            date_str = notification.timestamp.strftime("%Y-%m-%d %H:%M:%S") if notification.timestamp else "N/A"
            date_item = QTableWidgetItem(date_str)

            if not notification.is_read:
                status_item.setFont(bold_font)
                message_item.setFont(bold_font)
                # ticket_id_item.setFont(bold_font) # Optional: bold other columns too
                # date_item.setFont(bold_font)

            self.notifications_table.setItem(row_num, self.COLUMN_STATUS, status_item)
            self.notifications_table.setItem(row_num, self.COLUMN_MESSAGE, message_item)
            self.notifications_table.setItem(row_num, self.COLUMN_TICKET_ID, ticket_id_item)
            self.notifications_table.setItem(row_num, self.COLUMN_DATE, date_item)

        # self.notifications_table.resizeColumnsToContents() # Alternative to specific resize modes


    @Slot()
    def handle_mark_selected_as_read(self):
        selected_items = self.notifications_table.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select one or more notifications to mark as read.")
            return

        ids_to_mark = []
        # Use selectedRows to avoid processing multiple items from the same row if full row select is off
        selected_rows = self.notifications_table.selectionModel().selectedRows()
        for index in selected_rows:
            first_item_in_row = self.notifications_table.item(index.row(), self.COLUMN_STATUS)
            if first_item_in_row:
                notification_id = first_item_in_row.data(Qt.UserRole)
                if notification_id:
                    ids_to_mark.append(notification_id)

        # Remove duplicates if any (though selectedRows should give unique rows)
        ids_to_mark = list(set(ids_to_mark))

        if not ids_to_mark:
            QMessageBox.information(self, "No Action", "No valid notification IDs found in selection.")
            return

        try:
            count_marked = mark_multiple_notifications_as_read(ids_to_mark)
            if count_marked > 0:
                QMessageBox.information(self, "Success", f"{count_marked} notification(s) marked as read.")
                self.load_user_notifications() # Refresh the view
                self.notifications_updated.emit() # Notify main window
            else:
                QMessageBox.information(self, "No Change", "Selected notifications were already read or not found.")
        except Exception as e:
            print(f"Error marking notifications as read: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"Could not mark notifications as read: {e}")


    @Slot(QTableWidgetItem)
    def handle_item_double_click(self, item: QTableWidgetItem):
        row = item.row()
        status_cell_item = self.notifications_table.item(row, self.COLUMN_STATUS)
        if not status_cell_item: return

        notification_id = status_cell_item.data(Qt.UserRole)
        if not notification_id: return

        # Check if it's already read from the display to avoid unnecessary backend call
        # This is an optimization; backend `mark_notification_as_read` handles already-read state.
        is_currently_read = status_cell_item.text() == "Read"
        if is_currently_read:
             # Optionally, navigate to ticket or show details. For now, just info.
            QMessageBox.information(self, "Notification", f"Notification '{notification_id}' is already read.")
            return

        try:
            success = mark_notification_as_read(notification_id)
            if success:
                # QMessageBox.information(self, "Success", f"Notification '{notification_id}' marked as read.")
                self.load_user_notifications() # Refresh view
                self.notifications_updated.emit() # Notify main window
            else: # Already read or not found by backend
                QMessageBox.information(self, "No Change", "Notification was already read or could not be updated.")
        except Exception as e:
            print(f"Error marking notification as read on double click: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Error", f"Could not mark notification as read: {e}")

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if event.isAccepted():
            self.load_user_notifications()


if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Re-import after path adjustment
    try: from models import User, Notification
    except: pass # Fallbacks at top of file will be used

    app = QApplication(sys.argv)

    class DummyUserForInbox(User):
        def __init__(self, username="inbox_user", role="EndUser", user_id_val="inbox_uid_001"):
            self.username = username; self.role = role # type: ignore
            self.user_id = user_id_val
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempRoles: __args__ = ('EndUser',)
                 User.ROLES = TempRoles #type: ignore
                 self.ROLES = TempRoles #type: ignore
        def set_password(self, p): pass
        def check_password(self, p): return False

    test_user = DummyUserForInbox()

    # Mock notification_manager functions
    _original_get_notifications = notification_manager.get_notifications_for_user
    _original_mark_read = notification_manager.mark_notification_as_read
    _original_mark_multiple_read = notification_manager.mark_multiple_notifications_as_read

    _mock_db_notifications = [
        Notification(notification_id="N001", user_id=test_user.user_id, message="Your ticket T001 was updated.", ticket_id="T001", timestamp=datetime.now(timezone.utc), is_read=False),
        Notification(notification_id="N002", user_id=test_user.user_id, message="A new announcement was posted.", ticket_id=None, timestamp=datetime.now(timezone.utc) - timedelta(hours=1), is_read=False),
        Notification(notification_id="N003", user_id=test_user.user_id, message="Your ticket T002 was closed.", ticket_id="T002", timestamp=datetime.now(timezone.utc) - timedelta(days=1), is_read=True),
    ]

    def mock_get_notifications(user_id, unread_only=False):
        print(f"MOCK get_notifications_for_user(user_id={user_id}, unread_only={unread_only})")
        res = [n for n in _mock_db_notifications if n.user_id == user_id]
        if unread_only: res = [n for n in res if not n.is_read]
        return res

    def mock_mark_read(notification_id):
        print(f"MOCK mark_notification_as_read(notification_id={notification_id})")
        for n in _mock_db_notifications:
            if n.notification_id == notification_id and not n.is_read:
                n.is_read = True
                return True
        return False

    def mock_mark_multiple_read(notification_ids):
        print(f"MOCK mark_multiple_notifications_as_read(notification_ids={notification_ids})")
        count = 0
        for nid in notification_ids:
            if mock_mark_read(nid): # Reuse single mark logic
                count += 1
        return count

    notification_manager.get_notifications_for_user = mock_get_notifications
    notification_manager.mark_notification_as_read = mock_mark_read
    notification_manager.mark_multiple_notifications_as_read = mock_mark_multiple_read

    inbox_view = InboxView(current_user=test_user)

    def test_signal_handler():
        print("TEST: notifications_updated signal received!")
        # In a real app, this might trigger MainWindow.update_notification_indicator
        # For this test, we can just check if it was emitted by checking print output or a flag.
    inbox_view.notifications_updated.connect(test_signal_handler)

    inbox_view.show()
    exit_code = app.exec()

    # Restore original functions
    notification_manager.get_notifications_for_user = _original_get_notifications
    notification_manager.mark_notification_as_read = _original_mark_read
    notification_manager.mark_multiple_notifications_as_read = _original_mark_multiple_read

    sys.exit(exit_code)
