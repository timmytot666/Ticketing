import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QVBoxLayout,
    QStackedWidget,
    QMenuBar, # Added QMenu
    QMenu,    # Added QMenu
    QStatusBar,
    QMessageBox
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Slot, Qt, QTimer

from typing import Optional, Dict, Any
from datetime import datetime

try:
    from models import User
    from notification_manager import get_notifications_for_user, check_and_send_sla_alerts
    from ui_create_ticket_view import CreateTicketView
    from ui_my_tickets_view import MyTicketsView
    from ui_inbox_view import InboxView
    from ui_all_tickets_view import AllTicketsView
    from ui_ticket_detail_view import TicketDetailView
    from ui_dashboard_view import DashboardView
    from ui_reporting_view import ReportingView
    from ui_kb_article_view import KBArticleView
    from ui_user_management_view import UserManagementView # Added
except ModuleNotFoundError:
    print("Error: Critical module not found. Using fallbacks.", file=sys.stderr)
    def check_and_send_sla_alerts(): print("Warning: Fallback check_and_send_sla_alerts called.")
    class User:
        ROLES = None; user_id: str
        def __init__(self, username: str, role: str, user_id_val: str = "fb_uid", *args, **kwargs):
            self.username=username; self.role=role; self.user_id=user_id_val
        def set_password(self,p): pass
    def get_notifications_for_user(uid, unread_only=False): return []
    class FallbackView(QWidget):
        def __init__(self, name, cu=None, parent=None):
            super().__init__(parent); QVBoxLayout(self).addWidget(QLabel(f"Fallback: {name}"))
            class DummySignal: connect = lambda self, slot: None # type: ignore
            self.notifications_updated=DummySignal(); self.ticket_selected=DummySignal(); self.ticket_updated=DummySignal(); self.navigate_back=DummySignal() # type: ignore
    CreateTicketView=type('CreateTicketView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"CreateTicketView",cu,p)})
    MyTicketsView=type('MyTicketsView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"MyTicketsView",cu,p)})
    InboxView=type('InboxView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"InboxView",cu,p)})
    AllTicketsView=type('AllTicketsView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"AllTicketsView",cu,p)})
    TicketDetailView=type('TicketDetailView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"TicketDetailView",cu,p)})
    DashboardView=type('DashboardView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"DashboardView",cu,p)})
    ReportingView=type('ReportingView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"ReportingView",cu,p)})
    KBArticleView=type('KBArticleView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"KBArticleView",cu,p)})
    UserManagementView=type('UserManagementView',(FallbackView,),{"__init__":lambda s,cu,p=None:FallbackView.__init__(s,"UserManagementView",cu,p)})


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

        self.sla_check_timer = QTimer(self)
        self.sla_check_timer.timeout.connect(self._run_sla_checks_and_refresh_ui)
        self.sla_check_timer.start(15 * 60 * 1000)

    def _run_sla_checks_and_refresh_ui(self): # Unchanged
        print(f"Running periodic SLA checks at {datetime.now()}...")
        try:
            check_and_send_sla_alerts(); self.update_notification_indicator()
        except Exception as e: print(f"Error during SLA check/UI refresh: {e}", file=sys.stderr)

    def update_notification_indicator(self): # Unchanged
        if not hasattr(self,'current_user') or not self.current_user or not hasattr(self.current_user,'user_id'):
            if hasattr(self,'notification_indicator_label'): self.notification_indicator_label.setText("Notifications: N/A"); return
        try:
            unread_notifications = get_notifications_for_user(self.current_user.user_id, unread_only=True)
            if hasattr(self,'notification_indicator_label'): self.notification_indicator_label.setText(f"Unread Notifications: {len(unread_notifications)}")
        except Exception as e: print(f"Error updating notification indicator: {e}", file=sys.stderr); hasattr(self,'notification_indicator_label') and self.notification_indicator_label.setText("Notifications: Error")

    def _create_menu_bar(self): # Modified
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File"); self.new_ticket_action = QAction("New Ticket...", self); file_menu.addAction(self.new_ticket_action)
        file_menu.addSeparator(); exit_action = QAction("E&xit", self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)

        self.view_menu = menu_bar.addMenu("&View")
        self.my_tickets_action = QAction("My Tickets", self); self.view_menu.addAction(self.my_tickets_action)
        self.view_inbox_action = QAction("View Inbox", self); self.view_menu.addAction(self.view_inbox_action)
        self.view_menu.addSeparator();
        self.all_tickets_action = QAction("All Tickets", self); self.view_menu.addAction(self.all_tickets_action)

        tools_menu = menu_bar.addMenu("&Tools") # Ensured Tools menu is created or fetched
        self.dashboard_action = QAction("Dashboard", self); tools_menu.addAction(self.dashboard_action)
        self.reporting_action = QAction("Reporting", self); tools_menu.addAction(self.reporting_action)
        self.kb_management_action = QAction("Knowledge Base", self); tools_menu.addAction(self.kb_management_action)
        tools_menu.addSeparator() # Separator before User Management
        self.user_management_action = QAction("User Management", self); tools_menu.addAction(self.user_management_action) # Added

        help_menu = menu_bar.addMenu("&Help"); about_action = QAction("About", self); help_menu.addAction(about_action)

        self.new_ticket_action.triggered.connect(self.show_create_ticket_view)
        self.my_tickets_action.triggered.connect(self.show_my_tickets_view)
        self.view_inbox_action.triggered.connect(self.show_inbox_view)
        self.all_tickets_action.triggered.connect(self.show_all_tickets_view)
        self.dashboard_action.triggered.connect(self.show_dashboard_view)
        self.reporting_action.triggered.connect(self.show_reporting_view)
        self.kb_management_action.triggered.connect(self.show_kb_management_view)
        self.user_management_action.triggered.connect(self.show_user_management_view) # Connected
        about_action.triggered.connect(self.on_placeholder_action)

    def _create_status_bar(self): # Unchanged
        status_bar = self.statusBar()
        self.user_status_label = QLabel(f"Logged in as: {self.current_user.username} ({self.current_user.role})")
        status_bar.addPermanentWidget(self.user_status_label)
        self.notification_indicator_label = QLabel("Notifications: 0")
        status_bar.addWidget(self.notification_indicator_label)

    def _create_central_widget(self): # Modified
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
        self.reporting_view = ReportingView(self.current_user, self); self.stacked_widget.addWidget(self.reporting_view)
        self.kb_article_view = KBArticleView(self.current_user, self); self.stacked_widget.addWidget(self.kb_article_view)
        self.user_management_view = UserManagementView(self.current_user, self); self.stacked_widget.addWidget(self.user_management_view) # Added

        self.setCentralWidget(self.stacked_widget)

    def _get_ui_config_for_role(self, role: User.ROLES) -> Dict[str, Any]: # type: ignore # Modified
        actions_enabled = {
            'new_ticket':False, 'my_tickets':False, 'all_tickets':False,
            'dashboard':False, 'view_inbox':True, 'reporting': False,
            'kb_management': False, 'user_management': False # Added user_management
        }
        target_page = self.welcome_page

        if role == 'EndUser':
            actions_enabled.update({'new_ticket': True, 'my_tickets': True})
            target_page = self.my_tickets_view
        elif role in ['Technician', 'Engineer']:
            actions_enabled.update({'my_tickets': True, 'all_tickets': True, 'kb_management': True})
            target_page = self.all_tickets_view
        elif role in ['TechManager', 'EngManager']: # Assuming these are admin-like roles
            actions_enabled.update({
                'my_tickets': True, 'all_tickets': True,
                'dashboard': True, 'reporting': True, 'kb_management': True,
                'user_management': True # Enabled for managers
            })
            target_page = self.dashboard_view

        return {'actions_enabled': actions_enabled, 'target_page_widget': target_page}

    def setup_ui_for_role(self, role: User.ROLES): # type: ignore # Modified
        config = self._get_ui_config_for_role(role)
        actions_map = {
            'new_ticket': self.new_ticket_action, 'my_tickets': self.my_tickets_action,
            'all_tickets': self.all_tickets_action, 'dashboard': self.dashboard_action,
            'view_inbox': self.view_inbox_action, 'reporting': self.reporting_action,
            'kb_management': self.kb_management_action,
            'user_management': self.user_management_action # Added
        }
        for key, enabled in config['actions_enabled'].items():
            action_widget = actions_map.get(key)
            if action_widget: action_widget.setEnabled(enabled)

        target_widget = config.get('target_page_widget', self.welcome_page)
        if hasattr(self, 'stacked_widget'):
            if target_widget and self.stacked_widget.indexOf(target_widget) != -1: self.stacked_widget.setCurrentWidget(target_widget)
            elif hasattr(self,'welcome_page') and self.stacked_widget.indexOf(self.welcome_page)!=-1: self.stacked_widget.setCurrentWidget(self.welcome_page)
            elif self.stacked_widget.count()>0: self.stacked_widget.setCurrentIndex(0)

    # ... (show_... slots for other views as before) ...
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
    def show_reporting_view(self):
        if hasattr(self, 'reporting_view'): self.stacked_widget.setCurrentWidget(self.reporting_view)
        else: QMessageBox.critical(self, "Error", "Reporting page is not available.")
    @Slot()
    def show_kb_management_view(self):
        if hasattr(self, 'kb_article_view'): self.stacked_widget.setCurrentWidget(self.kb_article_view)
        else: QMessageBox.critical(self, "Error", "Knowledge Base page is not available.")

    @Slot() # New slot
    def show_user_management_view(self):
        if hasattr(self, 'user_management_view') and hasattr(self, 'stacked_widget'):
            self.stacked_widget.setCurrentWidget(self.user_management_view)
        else:
            QMessageBox.critical(self, "Error", "User Management page is not available.")

    @Slot(str) # Unchanged
    def show_ticket_detail_view(self, ticket_id: str):
        if hasattr(self, 'ticket_detail_view'): self.ticket_detail_view.load_ticket_data(ticket_id); self.stacked_widget.setCurrentWidget(self.ticket_detail_view)
        else: QMessageBox.critical(self, "Error", "Ticket Detail page is not available.")
    @Slot(str) # Unchanged
    def handle_ticket_updated_in_detail_view(self, ticket_id: str):
        if hasattr(self,'all_tickets_view') and self.all_tickets_view.isVisible(): self.all_tickets_view.load_and_display_tickets()
        if hasattr(self,'my_tickets_view') and self.my_tickets_view.isVisible(): self.my_tickets_view.load_my_tickets_data()
        self.update_notification_indicator()
    @Slot() # Unchanged
    def on_placeholder_action(self): sender=self.sender(); isinstance(sender,QAction) and QMessageBox.information(self,"Action Triggered",f"Placeholder: {sender.text()}")

if __name__ == '__main__':
    import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    app = QApplication(sys.argv)
    class DUFM(User):
        def __init__(self,u,r,uid="uid_dum_main"):super().__init__(username=u,role=r,user_id_val=uid) # type: ignore
    # Test with a TechManager role to see User Management by default (if it was their default page)
    # Or just ensure the menu item is enabled.
    test_user = DUFM(username="main_test_admin", role="TechManager")
    main_window = MainWindow(user=test_user)
    main_window.show(); sys.exit(app.exec())
