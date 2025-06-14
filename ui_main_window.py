import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QVBoxLayout,
    QStackedWidget,
    QMenuBar,
    QStatusBar,
    QMessageBox
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Slot, Qt, QTimer # Added QTimer

from typing import Optional, Dict, Any

try:
    from models import User
    from notification_manager import get_notifications_for_user
    from ui_create_ticket_view import CreateTicketView
    from ui_my_tickets_view import MyTicketsView
    from ui_inbox_view import InboxView
    from ui_all_tickets_view import AllTicketsView
    from ui_ticket_detail_view import TicketDetailView
    from ui_dashboard_view import DashboardView
    from ui_reporting_view import ReportingView
    from notification_manager import check_and_send_sla_alerts # For QTimer
except ModuleNotFoundError:
    print("Error: Critical module not found. Using fallbacks.", file=sys.stderr)
    # Add check_and_send_sla_alerts to fallbacks if needed by __init__ directly
    def check_and_send_sla_alerts(): print("Warning: Fallback check_and_send_sla_alerts called.")
    class User:
        ROLES = None; user_id: str
        def __init__(self, username: str, role: str, user_id_val: str = "fb_uid", *args, **kwargs):
            self.username=username; self.role=role; self.user_id=user_id_val
        def set_password(self,p): pass
    def get_notifications_for_user(uid, unread_only=False): return []
    class FallbackView(QWidget):
        def __init__(self, name, cu=None, parent=None):
            super().__init__(parent)
            QVBoxLayout(self).addWidget(QLabel(f"Fallback: {name}"))
            class DummySignal: connect = lambda self, slot: None # type: ignore
            self.notifications_updated = DummySignal() # type: ignore
            self.ticket_selected = DummySignal() # type: ignore
            self.ticket_updated = DummySignal() # type: ignore
            self.navigate_back = DummySignal() # type: ignore
    CreateTicketView = type('CreateTicketView', (FallbackView,), {"__init__": lambda s,cu,p=None: FallbackView.__init__(s,"CreateTicketView",cu,p)})
    MyTicketsView = type('MyTicketsView', (FallbackView,), {"__init__": lambda s,cu,p=None: FallbackView.__init__(s,"MyTicketsView",cu,p)})
    InboxView = type('InboxView', (FallbackView,), {"__init__": lambda s,cu,p=None: FallbackView.__init__(s,"InboxView",cu,p)})
    AllTicketsView = type('AllTicketsView', (FallbackView,), {"__init__": lambda s,cu,p=None: FallbackView.__init__(s,"AllTicketsView",cu,p)})
    TicketDetailView = type('TicketDetailView', (FallbackView,), {"__init__": lambda s,cu,p=None: FallbackView.__init__(s,"TicketDetailView",cu,p)})
    DashboardView = type('DashboardView', (FallbackView,), {"__init__": lambda s,cu,p=None: FallbackView.__init__(s,"DashboardView",cu,p)})
    ReportingView = type('ReportingView', (FallbackView,), {"__init__": lambda s,cu,p=None: FallbackView.__init__(s,"ReportingView",cu,p)})


class MainWindow(QMainWindow):
    def __init__(self, user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user: User = user
        self.setWindowTitle("Ticketing System")
        self.resize(1024, 768)

        self._create_menu_bar()
        self._create_status_bar()
        self._create_central_widget()

        self.setup_ui_for_role(self.current_user.role)
        self.update_notification_indicator()

        # SLA Check Timer
        self.sla_check_timer = QTimer(self)
        self.sla_check_timer.timeout.connect(self._run_sla_checks_and_refresh_ui)
        self.sla_check_timer.start(15 * 60 * 1000) # Every 15 minutes
        # self.sla_check_timer.start(30 * 1000) # For testing: 30 seconds

    def _run_sla_checks_and_refresh_ui(self):
        print(f"Running periodic SLA checks at {datetime.now()}...") # For debugging
        try:
            check_and_send_sla_alerts() # This function handles its own errors internally
            self.update_notification_indicator() # Refresh indicator after alerts might create new notifications
            # Optionally, refresh current view if it might be affected by SLA changes (e.g. ticket list views)
            # current_view = self.stacked_widget.currentWidget()
            # if isinstance(current_view, (AllTicketsView, MyTicketsView)):
            #    current_view.load_and_display_tickets() # Or a more specific refresh method
        except Exception as e:
            print(f"Error during scheduled SLA check or UI refresh: {e}", file=sys.stderr)


    def update_notification_indicator(self):
        if not hasattr(self, 'current_user') or not self.current_user or not hasattr(self.current_user, 'user_id'):
            if hasattr(self, 'notification_indicator_label'): self.notification_indicator_label.setText("Notifications: N/A")
            return
        try:
            unread_notifications = get_notifications_for_user(self.current_user.user_id, unread_only=True)
            count = len(unread_notifications)
            if hasattr(self, 'notification_indicator_label'): self.notification_indicator_label.setText(f"Unread Notifications: {count}")
        except Exception as e:
            print(f"Error updating notification indicator: {e}", file=sys.stderr)
            if hasattr(self, 'notification_indicator_label'): self.notification_indicator_label.setText("Notifications: Error")

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu("&File"); self.new_ticket_action = QAction("New Ticket...", self); file_menu.addAction(self.new_ticket_action)
        file_menu.addSeparator(); exit_action = QAction("E&xit", self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        # View Menu
        self.view_menu = menu_bar.addMenu("&View") # Store as self.view_menu
        self.my_tickets_action = QAction("My Tickets", self); self.view_menu.addAction(self.my_tickets_action)
        self.view_inbox_action = QAction("View Inbox", self); self.view_menu.addAction(self.view_inbox_action)
        self.view_menu.addSeparator();
        self.all_tickets_action = QAction("All Tickets", self); self.view_menu.addAction(self.all_tickets_action)
        self.dashboard_action = QAction("Dashboard", self); self.view_menu.addAction(self.dashboard_action)
        self.reporting_action = QAction("Reporting", self); self.view_menu.addSeparator(); self.view_menu.addAction(self.reporting_action) # Added Reporting
        # Help Menu
        help_menu = menu_bar.addMenu("&Help"); about_action = QAction("About", self); help_menu.addAction(about_action)

        # Connections
        self.new_ticket_action.triggered.connect(self.show_create_ticket_view)
        self.my_tickets_action.triggered.connect(self.show_my_tickets_view)
        self.view_inbox_action.triggered.connect(self.show_inbox_view)
        self.all_tickets_action.triggered.connect(self.show_all_tickets_view)
        self.dashboard_action.triggered.connect(self.show_dashboard_view)
        self.reporting_action.triggered.connect(self.show_reporting_view) # Connected
        about_action.triggered.connect(self.on_placeholder_action)

    def _create_status_bar(self):
        status_bar = self.statusBar()
        self.user_status_label = QLabel(f"Logged in as: {self.current_user.username} ({self.current_user.role})")
        status_bar.addPermanentWidget(self.user_status_label)
        self.notification_indicator_label = QLabel("Notifications: 0")
        status_bar.addWidget(self.notification_indicator_label)

    def _create_central_widget(self):
        self.stacked_widget = QStackedWidget()
        self.welcome_page = QWidget(); QVBoxLayout(self.welcome_page).addWidget(QLabel(f"Welcome {self.current_user.username}!")); self.stacked_widget.addWidget(self.welcome_page)

        self.create_ticket_view = CreateTicketView(self.current_user, self); self.stacked_widget.addWidget(self.create_ticket_view)
        self.my_tickets_view = MyTicketsView(self.current_user, self); self.stacked_widget.addWidget(self.my_tickets_view)
        self.inbox_view = InboxView(self.current_user, self); self.inbox_view.notifications_updated.connect(self.update_notification_indicator); self.stacked_widget.addWidget(self.inbox_view)
        self.all_tickets_view = AllTicketsView(self.current_user, self); self.all_tickets_view.ticket_selected.connect(self.show_ticket_detail_view); self.stacked_widget.addWidget(self.all_tickets_view)
        self.ticket_detail_view = TicketDetailView(self.current_user, self);
        self.ticket_detail_view.ticket_updated.connect(self.handle_ticket_updated_in_detail_view)
        self.ticket_detail_view.navigate_back.connect(self.show_all_tickets_view)
        self.stacked_widget.addWidget(self.ticket_detail_view)
        self.dashboard_view = DashboardView(self.current_user, self); self.stacked_widget.addWidget(self.dashboard_view)
        self.reporting_view = ReportingView(self.current_user, self); self.stacked_widget.addWidget(self.reporting_view) # Added

        self.setCentralWidget(self.stacked_widget)

    def _get_ui_config_for_role(self, role: User.ROLES) -> Dict[str, Any]: # type: ignore
        actions_enabled = {
            'new_ticket':False, 'my_tickets':False, 'all_tickets':False,
            'dashboard':False, 'view_inbox':True, 'reporting': False # Added reporting
        }
        target_page = self.welcome_page

        if role == 'EndUser':
            actions_enabled.update({'new_ticket': True, 'my_tickets': True})
            target_page = self.my_tickets_view
        elif role in ['Technician', 'Engineer']:
            actions_enabled.update({'my_tickets': True, 'all_tickets': True})
            target_page = self.all_tickets_view
        elif role in ['TechManager', 'EngManager']:
            actions_enabled.update({
                'my_tickets': True, 'all_tickets': True,
                'dashboard': True, 'reporting': True # Enabled reporting for managers
            })
            target_page = self.dashboard_view

        return {'actions_enabled': actions_enabled, 'target_page_widget': target_page}

    def setup_ui_for_role(self, role: User.ROLES): # type: ignore
        config = self._get_ui_config_for_role(role)
        actions_map = {
            'new_ticket': self.new_ticket_action, 'my_tickets': self.my_tickets_action,
            'all_tickets': self.all_tickets_action, 'dashboard': self.dashboard_action,
            'view_inbox': self.view_inbox_action, 'reporting': self.reporting_action # Added
        }
        for key, enabled in config['actions_enabled'].items():
            action_widget = actions_map.get(key)
            if action_widget:
                action_widget.setEnabled(enabled)

        target_widget = config.get('target_page_widget', self.welcome_page)
        if hasattr(self, 'stacked_widget'): # Ensure stacked_widget exists
            if target_widget and self.stacked_widget.indexOf(target_widget) != -1:
                self.stacked_widget.setCurrentWidget(target_widget)
            elif hasattr(self, 'welcome_page') and self.stacked_widget.indexOf(self.welcome_page) != -1:
                self.stacked_widget.setCurrentWidget(self.welcome_page)
            elif self.stacked_widget.count() > 0:
                self.stacked_widget.setCurrentIndex(0)

    @Slot()
    def show_create_ticket_view(self):
        if hasattr(self, 'create_ticket_view'): self.stacked_widget.setCurrentWidget(self.create_ticket_view)
    @Slot()
    def show_my_tickets_view(self):
        if hasattr(self, 'my_tickets_view'): self.stacked_widget.setCurrentWidget(self.my_tickets_view)
    @Slot()
    def show_inbox_view(self):
        if hasattr(self, 'inbox_view'): self.stacked_widget.setCurrentWidget(self.inbox_view)
    @Slot()
    def show_all_tickets_view(self):
        if hasattr(self, 'all_tickets_view'): self.stacked_widget.setCurrentWidget(self.all_tickets_view)
    @Slot()
    def show_dashboard_view(self):
        if hasattr(self, 'dashboard_view'): self.stacked_widget.setCurrentWidget(self.dashboard_view)
        else: QMessageBox.critical(self, "Error", "Dashboard page is not available.")
    @Slot()
    def show_reporting_view(self): # New slot
        if hasattr(self, 'reporting_view'): self.stacked_widget.setCurrentWidget(self.reporting_view)
        else: QMessageBox.critical(self, "Error", "Reporting page is not available.")

    @Slot(str)
    def show_ticket_detail_view(self, ticket_id: str):
        if hasattr(self, 'ticket_detail_view'):
            self.ticket_detail_view.load_ticket_data(ticket_id)
            self.stacked_widget.setCurrentWidget(self.ticket_detail_view)
        else: QMessageBox.critical(self, "Error", "Ticket Detail page is not available.")

    @Slot(str)
    def handle_ticket_updated_in_detail_view(self, ticket_id: str):
        if hasattr(self, 'all_tickets_view') and self.all_tickets_view.isVisible():
            self.all_tickets_view.load_and_display_tickets()
        if hasattr(self, 'my_tickets_view') and self.my_tickets_view.isVisible():
             self.my_tickets_view.load_my_tickets_data()
        self.update_notification_indicator()

    @Slot()
    def on_placeholder_action(self):
        sender = self.sender()
        if isinstance(sender, QAction): QMessageBox.information(self, "Action Triggered", f"Placeholder: {sender.text()}")

if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    app = QApplication(sys.argv)
    class DummyUserForMain(User):
        def __init__(self, u, r, uid="uid_dummy_main"): super().__init__(username=u,role=r,user_id_val=uid)
    test_user = DummyUserForMain(username="main_test_mgr_reporter", role="EngManager") # Test with EngManager
    main_window = MainWindow(user=test_user)
    main_window.show()
    sys.exit(app.exec())
