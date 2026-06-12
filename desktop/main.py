"""
Woodul Creations - Desktop Application
PyQt5-based desktop client for management system
"""

import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QStatusBar, QMessageBox,
    QSplitter, QMenuBar, QMenu
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/desktop_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WoodfulCreationsApp(QMainWindow):
    """Main application window for Woodful Creations Desktop Client"""

    def __init__(self):
        """Initialize the application"""
        super().__init__()
        self.setWindowTitle("Woodful Creations - Management System")
        self.setGeometry(100, 100, 1400, 900)
        
        # Application metadata
        self.app_version = "1.0.0"
        self.app_name = "Woodful Creations"
        
        logger.info(f"Starting {self.app_name} v{self.app_version}")
        
        # Set application style
        self.setup_styles()
        
        # Initialize UI
        self.init_ui()
        
        # Show window
        self.show()
        logger.info("Application window displayed")

    def setup_styles(self):
        """Setup application styles and themes"""
        # Modern stylesheet inspired by Woodful's aesthetic
        stylesheet = """
        QMainWindow {
            background-color: #f5f5f5;
        }
        QMenuBar {
            background-color: #ffffff;
            color: #333333;
            border-bottom: 1px solid #e0e0e0;
        }
        QMenuBar::item:selected {
            background-color: #e8f5e9;
        }
        QMenu {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #e0e0e0;
        }
        QMenu::item:selected {
            background-color: #e8f5e9;
        }
        QTabBar::tab {
            background-color: #eeeeee;
            color: #333333;
            padding: 8px 20px;
            border: 1px solid #e0e0e0;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom: 3px solid #2e7d32;
        }
        QTabWidget::pane {
            border: 1px solid #e0e0e0;
        }
        QPushButton {
            background-color: #2e7d32;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1b5e20;
        }
        QPushButton:pressed {
            background-color: #0d3d1a;
        }
        QStatusBar {
            background-color: #ffffff;
            border-top: 1px solid #e0e0e0;
        }
        """
        self.setStyleSheet(stylesheet)

    def init_ui(self):
        """Initialize the user interface"""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.create_status_bar()
        
        # Create tab widget for different sections
        self.create_tab_widget(main_layout)
        
        central_widget.setLayout(main_layout)

    def create_menu_bar(self):
        """Create menu bar with options"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        
        open_action = file_menu.addAction("Open")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.on_open)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        
        # View Menu
        view_menu = menubar.addMenu("View")
        
        refresh_action = view_menu.addAction("Refresh")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.on_refresh)
        
        # Tools Menu
        tools_menu = menubar.addMenu("Tools")
        
        settings_action = tools_menu.addAction("Settings")
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.on_settings)
        
        # Help Menu
        help_menu = menubar.addMenu("Help")
        
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self.on_about)
        
        help_action = help_menu.addAction("Help")
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.on_help)

    def create_status_bar(self):
        """Create status bar"""
        self.statusbar = self.statusBar()
        self.statusbar.showMessage(
            f"{self.app_name} v{self.app_version} - Ready | "
            f"Started at {datetime.now().strftime('%H:%M:%S')}"
        )

    def create_tab_widget(self, parent_layout):
        """Create tab widget with different sections"""
        tab_widget = QTabWidget()
        
        # Stock Inventory Tab
        stock_tab = QWidget()
        stock_layout = QVBoxLayout()
        stock_layout.addWidget(QLabel("Stock Inventory Management"))
        stock_layout.addWidget(self.create_placeholder_content("stock_inventory"))
        stock_tab.setLayout(stock_layout)
        tab_widget.addTab(stock_tab, "[STOCK] Inventory")
        
        # Estimates Tab
        estimates_tab = QWidget()
        estimates_layout = QVBoxLayout()
        estimates_layout.addWidget(QLabel("Cost Estimates & Quotations"))
        estimates_layout.addWidget(self.create_placeholder_content("estimates"))
        estimates_tab.setLayout(estimates_layout)
        tab_widget.addTab(estimates_tab, "[ESTIMATES] Quotations")
        
        # Clients Tab
        clients_tab = QWidget()
        clients_layout = QVBoxLayout()
        clients_layout.addWidget(QLabel("Client Management"))
        clients_layout.addWidget(self.create_placeholder_content("clients"))
        clients_tab.setLayout(clients_layout)
        tab_widget.addTab(clients_tab, "[CLIENTS] Management")
        
        # Attendance Tab
        attendance_tab = QWidget()
        attendance_layout = QVBoxLayout()
        attendance_layout.addWidget(QLabel("Attendance & Salary Management"))
        attendance_layout.addWidget(self.create_placeholder_content("attendance"))
        attendance_tab.setLayout(attendance_layout)
        tab_widget.addTab(attendance_tab, "[ATTENDANCE] Tracking")
        
        # Interviews Tab
        interviews_tab = QWidget()
        interviews_layout = QVBoxLayout()
        interviews_layout.addWidget(QLabel("Interview Tracking"))
        interviews_layout.addWidget(self.create_placeholder_content("interviews"))
        interviews_tab.setLayout(interviews_layout)
        tab_widget.addTab(interviews_tab, "[INTERVIEWS] Status")
        
        # Payments Tab
        payments_tab = QWidget()
        payments_layout = QVBoxLayout()
        payments_layout.addWidget(QLabel("Payment Management"))
        payments_layout.addWidget(self.create_placeholder_content("payments"))
        payments_tab.setLayout(payments_layout)
        tab_widget.addTab(payments_tab, "[PAYMENTS] Tracking")
        
        # Analytics Tab
        analytics_tab = QWidget()
        analytics_layout = QVBoxLayout()
        analytics_layout.addWidget(QLabel("Analytics & Reports"))
        analytics_layout.addWidget(self.create_placeholder_content("analytics"))
        analytics_tab.setLayout(analytics_layout)
        tab_widget.addTab(analytics_tab, "[ANALYTICS] Reports")
        
        # Chat Tab
        chat_tab = QWidget()
        chat_layout = QVBoxLayout()
        chat_layout.addWidget(QLabel("AI Chat Assistant"))
        chat_layout.addWidget(self.create_placeholder_content("chat"))
        chat_tab.setLayout(chat_layout)
        tab_widget.addTab(chat_tab, "[CHAT] Assistant")
        
        parent_layout.addWidget(tab_widget)

    def create_placeholder_content(self, section_name):
        """Create placeholder content for sections"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel(f"Loading {section_name.replace('_', ' ').title()}...")
        label.setAlignment(Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(label)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget

    def on_open(self):
        """Handle open action"""
        logger.info("Open action triggered")
        self.statusbar.showMessage("Opening file...")

    def on_refresh(self):
        """Handle refresh action"""
        logger.info("Refresh action triggered")
        self.statusbar.showMessage("Refreshing data...")

    def on_settings(self):
        """Handle settings action"""
        logger.info("Settings action triggered")
        QMessageBox.information(self, "Settings", "Settings dialog will open here")

    def on_about(self):
        """Handle about action"""
        about_text = f"""
        <h2>{self.app_name}</h2>
        <p>Version: {self.app_version}</p>
        <p>A comprehensive business management system for Woodful Creations</p>
        <p>Features:</p>
        <ul>
            <li>Stock Inventory Management</li>
            <li>Cost Estimates and Quotations</li>
            <li>Client Management</li>
            <li>Attendance and Salary Tracking</li>
            <li>Interview Management</li>
            <li>Payment Tracking</li>
            <li>Advanced Analytics</li>
            <li>AI Chat Assistant</li>
        </ul>
        <p>Copyright 2024 Woodful Creations. All rights reserved.</p>
        """
        QMessageBox.about(self, "About", about_text)

    def on_help(self):
        """Handle help action"""
        logger.info("Help action triggered")
        QMessageBox.information(
            self,
            "Help",
            "Help documentation will be displayed here.\n\n"
            "For detailed documentation, visit the project wiki."
        )

    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit the application?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.info("Application closed by user")
            event.accept()
        else:
            event.ignore()


def main():
    """Main entry point"""
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Woodful Creations")
    app.setApplicationVersion("1.0.0")
    
    # Create and show main window
    window = WoodfulCreationsApp()
    
    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()