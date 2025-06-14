import sys
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QApplication
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QShowEvent # Moved QShowEvent

from typing import Optional, List, Dict, Any # Added Dict, Any
from datetime import datetime, date, timedelta, timezone

# Matplotlib imports
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("Warning: Matplotlib not found. Chart functionality will be disabled.", file=sys.stderr)
    MATPLOTLIB_AVAILABLE = False
    # Fallback QWidget to act as a canvas placeholder if matplotlib is not available
    class FigureCanvas(QWidget):
        def __init__(self, figure=None, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            self.error_label = QLabel("Matplotlib is not installed. Chart cannot be displayed.")
            self.error_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.error_label)
        def draw(self): pass # Dummy draw method

    class Figure: # Dummy Figure class
        def __init__(self, figsize=None, dpi=None): pass
        def clear(self): pass
        def add_subplot(self, *args, **kwargs):
            # Return a dummy Axes object with a text method
            class DummyAx:
                def text(self, x, y, s, **kwargs): pass
                def pie(self, sizes, labels, autopct, startangle, colors): pass
                def axis(self, *args, **kwargs): pass
            return DummyAx()

try:
    from models import User, Ticket
    from ticket_manager import list_tickets
except ModuleNotFoundError:
    print("Error: models.py or ticket_manager.py not found. Using fallbacks.", file=sys.stderr)
    class User:
        ROLES = None; user_id: str
        def __init__(self, username: str, role: str, user_id_val: str = "fb_uid", *args, **kwargs):
            self.username=username; self.role=role; self.user_id=user_id_val
    class Ticket:
        status: Optional[str] = None; updated_at: Optional[datetime] = None # Minimal for dummy
        def __init__(self, **kwargs): # Basic init for dummy
            for k, v in kwargs.items(): setattr(self, k, v)
            if not self.updated_at: self.updated_at = datetime.now(timezone.utc)
            if not self.status: self.status = "Open"

    def list_tickets() -> List[Ticket]: return []

class DashboardView(QWidget):
    def __init__(self, current_user: User, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_user = current_user
        self.status_counts: Dict[str, int] = {}

        self.setWindowTitle("System Dashboard")
        main_layout = QVBoxLayout(self)

        # Metrics Section (Layout unchanged)
        metrics_layout = QGridLayout(); metrics_layout.setSpacing(20)
        title_font = QFont(); title_font.setPointSize(14); title_font.setBold(True)
        metric_font = QFont(); metric_font.setPointSize(12)
        dashboard_title = QLabel("Ticket Overview"); dashboard_title.setFont(title_font)
        dashboard_title.setAlignment(Qt.AlignCenter); main_layout.addWidget(dashboard_title)
        self.open_tickets_label = QLabel("Open Tickets: N/A"); self.open_tickets_label.setFont(metric_font)
        metrics_layout.addWidget(self.open_tickets_label, 0, 0)
        self.in_progress_tickets_label = QLabel("In Progress Tickets: N/A"); self.in_progress_tickets_label.setFont(metric_font)
        metrics_layout.addWidget(self.in_progress_tickets_label, 0, 1)
        self.resolved_today_label = QLabel("Resolved Today: N/A"); self.resolved_today_label.setFont(metric_font)
        metrics_layout.addWidget(self.resolved_today_label, 1, 0)
        self.on_hold_tickets_label = QLabel("On Hold Tickets: N/A"); self.on_hold_tickets_label.setFont(metric_font)
        metrics_layout.addWidget(self.on_hold_tickets_label, 1, 1)
        main_layout.addLayout(metrics_layout); main_layout.addSpacing(20)

        # Chart Section - Modified
        chart_section_title = QLabel("Ticket Status Distribution"); chart_section_title.setFont(title_font)
        chart_section_title.setAlignment(Qt.AlignCenter); main_layout.addWidget(chart_section_title)

        self.chart_container_widget = QWidget() # Renamed from chart_placeholder_widget for clarity
        self.chart_container_widget.setMinimumSize(400, 300)
        self.chart_container_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        chart_layout = QVBoxLayout(self.chart_container_widget) # Use this layout for the canvas
        chart_layout.setContentsMargins(0,0,0,0) # Ensure canvas fills the container

        self.figure = Figure(figsize=(5, 3), dpi=100) # dpi can be adjusted
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas)

        main_layout.addWidget(self.chart_container_widget, 1) # Add container with stretch factor

        # Refresh Button (Layout unchanged)
        self.refresh_button = QPushButton("Refresh Dashboard")
        self.refresh_button.clicked.connect(self.load_dashboard_data)
        button_layout = QHBoxLayout(); button_layout.addStretch()
        button_layout.addWidget(self.refresh_button); button_layout.addStretch()
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    @Slot()
    def load_dashboard_data(self):
        print("Dashboard refresh requested...")
        self._update_metrics_display()
        self._update_pie_chart() # Added call

    def _update_metrics_display(self):
        try:
            all_tickets: List[Ticket] = list_tickets()
        except Exception as e:
            print(f"Error fetching tickets for dashboard: {e}", file=sys.stderr)
            self.open_tickets_label.setText("Open Tickets: Error")
            self.in_progress_tickets_label.setText("In Progress Tickets: Error")
            self.on_hold_tickets_label.setText("On Hold Tickets: Error")
            self.resolved_today_label.setText("Resolved Today: Error")
            self.status_counts = {}
            return

        open_count, in_progress_count, on_hold_count, resolved_today_count = 0, 0, 0, 0
        closed_total_count = 0 # For pie chart, to differentiate 'resolved today' from all closed
        today = date.today()

        for ticket in all_tickets:
            status = getattr(ticket, 'status', None) # Robust access
            updated_at_dt = getattr(ticket, 'updated_at', None)

            if status == 'Open': open_count += 1
            elif status == 'In Progress': in_progress_count += 1
            elif status == 'On Hold': on_hold_count += 1 # Assuming 'On Hold' is a valid status
            elif status == 'Closed':
                closed_total_count +=1
                if updated_at_dt and isinstance(updated_at_dt, datetime):
                    # Compare dates in UTC or make timezone naive for simple date part comparison
                    ticket_update_date = updated_at_dt.astimezone(timezone.utc).date() if updated_at_dt.tzinfo else updated_at_dt.date()
                    if ticket_update_date == today:
                        resolved_today_count += 1

        self.open_tickets_label.setText(f"Open Tickets: {open_count}")
        self.in_progress_tickets_label.setText(f"In Progress Tickets: {in_progress_count}")
        self.on_hold_tickets_label.setText(f"On Hold Tickets: {on_hold_count}")
        self.resolved_today_label.setText(f"Resolved Today: {resolved_today_count}")

        self.status_counts = {
            'Open': open_count, 'In Progress': in_progress_count, 'On Hold': on_hold_count,
            'Closed': closed_total_count # Pie chart might show all closed, or just active ones
        }
        # Example for pie: focus on active tickets
        self.active_status_counts = {'Open': open_count, 'In Progress': in_progress_count, 'On Hold': on_hold_count}


    def _update_pie_chart(self):
        if not MATPLOTLIB_AVAILABLE: # Check if matplotlib was imported successfully
            # If canvas is the fallback QWidget with an error label, it's already showing it.
            # If a different placeholder strategy was used, update it here.
            if hasattr(self, 'chart_info_label') and isinstance(self.canvas, QWidget) and not isinstance(self.canvas, type(FigureCanvas)):
                 # This assumes chart_info_label was the initial placeholder.
                 # If self.canvas itself is the fallback QWidget, it shows its own error message.
                 pass
            return

        if not hasattr(self, 'active_status_counts') or not self.active_status_counts: # Use active_status_counts
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'No data available for chart', horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return

        chart_data = {k: v for k, v in self.active_status_counts.items() if v > 0}

        if not chart_data:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'No active tickets to display', horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return

        labels = list(chart_data.keys())
        sizes = list(chart_data.values())
        # Define specific colors or let Matplotlib choose
        # colors = ['#66b3ff','#ff9999','#99ff99','#ffcc99'] # Example: Blue, Red, Green, Orange
        # pie_colors = colors[:len(labels)]

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140) # Removed colors for default
        ax.axis('equal')
        # self.figure.suptitle('Active Ticket Statuses', fontsize=10) # Optional title
        self.canvas.draw()


    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if event.isAccepted():
            self.load_dashboard_data()


if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    try:
        from models import User, Ticket
        from ticket_manager import list_tickets
    except: pass

    app = QApplication(sys.argv)

    class DummyUserForDashboard(User): # Same as before
        def __init__(self, username="dash_user", role="TechManager", user_id_val="dash_uid_001"):
            self.username=username; self.role=role # type: ignore
            self.user_id=user_id_val
            if not hasattr(self, 'ROLES') or self.ROLES is None:
                 class TempRoles: __args__ = ('TechManager', 'EndUser')
                 User.ROLES = TempRoles; self.ROLES = TempRoles # type: ignore
        def set_password(self,p):pass; def check_password(self,p):return False

    test_user = DummyUserForDashboard()

    _original_list_tickets = ticket_manager.list_tickets # Store original
    def mock_list_tickets_dashboard_chart():
        print("MOCK: list_tickets() called for dashboard chart")
        return [
            Ticket(status='Open', updated_at=datetime.now(timezone.utc)),
            Ticket(status='Open', updated_at=datetime.now(timezone.utc)),
            Ticket(status='Open', updated_at=datetime.now(timezone.utc)),
            Ticket(status='In Progress', updated_at=datetime.now(timezone.utc)),
            Ticket(status='In Progress', updated_at=datetime.now(timezone.utc)),
            Ticket(status='On Hold', updated_at=datetime.now(timezone.utc)),
            Ticket(status='Closed', updated_at=datetime.now(timezone.utc)),
            Ticket(status='Closed', updated_at=datetime.now(timezone.utc) - timedelta(days=1)),
        ]
    ticket_manager.list_tickets = mock_list_tickets_dashboard_chart

    dashboard_view = DashboardView(current_user=test_user)
    dashboard_view.show()

    exit_code = app.exec()
    ticket_manager.list_tickets = _original_list_tickets # Restore
    sys.exit(exit_code)
