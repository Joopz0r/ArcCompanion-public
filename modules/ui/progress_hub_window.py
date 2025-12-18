from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, 
                             QLabel, QSizePolicy, QTextEdit)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QFont
import os
from modules.core.constants import Constants
from .hideout_manager_window import HideoutManagerWindow
from .quest_manager_window import QuestManagerWindow
from .project_manager_window import ProjectManagerWindow
from .item_database_window import ItemDatabaseWindow
from .settings_window import SettingsWindow
from .ui_components import ClickableBanner, set_dark_title_bar, ensure_window_within_screen
import random

class AboutTab(QWidget):
    def __init__(self, app_version, check_update_func=None):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(15)
        title_lbl = QLabel("Arc Companion"); title_lbl.setStyleSheet("font-size: 28px; font-weight: bold; color: #E5C07B;"); title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title_lbl)
        version_lbl = QLabel(f"Version: {app_version}"); version_lbl.setStyleSheet("font-size: 16px; color: #ABB2BF;"); version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version_lbl)
        if check_update_func:
            check_btn = QPushButton("Check for App Updates"); check_btn.setCursor(Qt.CursorShape.PointingHandCursor); check_btn.setFixedWidth(200); check_btn.setStyleSheet("QPushButton { background-color: #3E4451; color: white; border: 1px solid #555; padding: 6px; border-radius: 4px; font-weight: bold;} QPushButton:hover { background-color: #4B5363; border-color: #777; }")
            check_btn.clicked.connect(check_update_func)
            btn_layout = QHBoxLayout(); btn_layout.addStretch(); btn_layout.addWidget(check_btn); btn_layout.addStretch(); layout.addLayout(btn_layout)
        layout.addSpacing(10)
        def make_link(text, url, subtext=None):
            lbl = QLabel(f"<a href='{url}' style='color: #61AFEF; text-decoration: none;'>{text}</a>")
            if subtext: lbl.setText(f"{subtext} <a href='{url}' style='color: #61AFEF; text-decoration: none;'>{text}</a>")
            lbl.setOpenExternalLinks(True); lbl.setFont(QFont("Segoe UI", 14)); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); return lbl
        layout.addWidget(make_link("www.arc-companion.xyz", "https://www.arc-companion.xyz"))
        layout.addWidget(make_link("Open Source", "https://github.com/Joopz0r/ArcCompanion-public"))
        layout.addWidget(make_link("RaidTheory/arcraiders-data", "https://github.com/RaidTheory/arcraiders-data", "Special thanks to:"))
        layout.addSpacing(20)
        patch_lbl = QLabel("Patch Notes"); patch_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #E0E6ED; margin-bottom: 5px;"); layout.addWidget(patch_lbl)
        self.patch_notes = QTextEdit(); self.patch_notes.setReadOnly(True); self.patch_notes.setStyleSheet("QTextEdit { background-color: #232834; color: #E0E6ED; border: 1px solid #3E4451; border-radius: 4px; padding: 10px; font-size: 13px; font-family: 'Segoe UI'; }")
        self.patch_notes.setHtml(f"""
        <b>{app_version} - New Features & Major Improvements</b><br><br>

        <b>Core Systems</b><br>
        - <b>Backup System:</b> New Backup/Restore tab in settings<br>
        - <b>Hyperspeed OCR:</b> Faster and more accurate tooltip reading<br>
        - <b>Live Settings:</b> Hotkeys and overlay settings update instantly<br>
        - <b>Anchor Mode:</b> Pin Item Overlay to fixed position<br>
        - <b>Opacity Slider:</b> Control overlay transparency<br><br>

        <b>Item Overlay Enhancements</b><br>
        - Drag-and-drop reordering for overlay sections<br>
        - Display storage quantities in overlay<br>
        - Added color picker for OCR color<br>
        - Roman Numeral OCR Fix (Il -> II)<br>
        - Smart Tooltip Cropping & Language Filtering<br><br>

        <b>Quest & Hideout Management</b><br>
        - <b>Quest Overlay:</b> Map names, search bar, and map filters<br>
        - <b>Hideout Manager:</b> Remembers section states between sessions<br><br>

        <b>Item Database</b><br>
        - Quick filter buttons (Blueprints, Storage)<br>
        - Blueprint progress counter and collection tracking<br>
        - Dedicated inspector panel for item details<br>
        - Improved filtering and multi-language search<br><br>

        <b>UI/UX Improvements</b><br>
        - Dark Theme applied to all popups<br>
        - <b>Progress Hub:</b> New Reset buttons properly clear data<br>
        - <b>Window:</b> Prevented off-screen sticking<br>
        - <b>Settings:</b> Reorganized into tabbed interface<br>
        - Dynamic Monitor Detection<br><br>

        <b>Bug Fixes</b><br>
        - Fixed unresponsive app buttons after updates<br>
        - Fixed overlay text size setting<br>
        - Fixed inventory sync issues<br>
        - Fixed Quest Hub items disappearing<br>
        - Resolved JSON parsing errors<br>
        - Fixed future hideout/projects settings<br>
        """)
        layout.addWidget(self.patch_notes)

class ProgressHubWindow(QWidget):
    # This signal bubbles up auto-saves from children tabs to the main app
    progress_saved = pyqtSignal()

    def __init__(self, data_manager, config_manager, settings_callback=None, app_version="1.0.0", app_update_checker_func=None, lang_code="en"):
        super().__init__()
        self.data_manager = data_manager
        self.config_manager = config_manager
        self.lang_code = lang_code 
        
        # Apply dark title bar
        set_dark_title_bar(self)

        self.setWindowTitle("Arc Companion - Progress Hub")
        self.resize(760, 850) 
        if os.path.exists(Constants.ICON_FILE): self.setWindowIcon(QIcon(Constants.ICON_FILE))
        self.setStyleSheet(Constants.DARK_THEME_QSS)

        main_layout = QVBoxLayout(self)
        # Banner Area
        self.banner_container = QWidget()
        banner_layout = QHBoxLayout(self.banner_container)
        banner_layout.setSpacing(15)
        banner_layout.setContentsMargins(5, 5, 5, 5)
        
        self.support_banner = ClickableBanner(Constants.BANNER_IMAGE_PATH, "https://ko-fi.com/joopz0r", "☕ Support the Dev", bg_color="#333")
        self.discord_banner = ClickableBanner(Constants.DISCORD_IMAGE_PATH, "https://discord.gg/RzjPhXCXfH", "Join Discord", bg_color="#5865F2")
        
        banner_layout.addWidget(self.support_banner)
        banner_layout.addWidget(self.discord_banner)
        main_layout.addWidget(self.banner_container)

        # Banner Toggle Button
        self.toggle_banner_btn = QPushButton("▲")
        self.toggle_banner_btn.setText("▼") 
        
        self.toggle_banner_btn.setFixedSize(100, 12) # Slimmer height, wider width
        self.toggle_banner_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_banner_btn.setToolTip("Hide Banner")
        self.toggle_banner_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5C6370;
                border: none;
                border-top: 1px solid #3E4451;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
                font-size: 10px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #2C323C;
                color: #E5C07B;
            }
        """)
        self.toggle_banner_btn.clicked.connect(self.toggle_banner)
        
        # Center the toggle button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.toggle_banner_btn)
        btn_layout.addStretch()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(0) # Remove spacing
        main_layout.addLayout(btn_layout)

        # --- RESTORE WINDOW STATE ---
        # Geometry
        x, y, w, h = self.config_manager.get_window_geometry()
        
        # Ensure non-zero size defaults
        if w <= 0: w = 760
        if h <= 0: h = 850
        
        if x != -1 and y != -1:
            # 1. Validate bound (ensure it's on a screen)
            safe_x, safe_y = ensure_window_within_screen(x, y)
            
            # 2. Resize Content (w, h)
            self.resize(w, h)
            
            # 3. Move Frame (x, y)
            self.move(safe_x, safe_y)
        else:
            self.resize(w, h)


        # Banner State
        banner_visible = self.config_manager.get_banner_visible()
        if not banner_visible:
            self.banner_container.hide()
            self.toggle_banner_btn.setText("▲")
            self.toggle_banner_btn.setToolTip("Show Banner")
        else:
            self.banner_container.show()
            self.toggle_banner_btn.setText("▼")
            self.toggle_banner_btn.setToolTip("Hide Banner")

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Initialize Tabs
        self.hideout_tab = HideoutManagerWindow(self.data_manager.hideout_data, self.data_manager.user_progress, self.data_manager, Constants.RARITY_COLORS, lang_code=self.lang_code)
        self.quest_tab = QuestManagerWindow(self.data_manager, self.data_manager.user_progress, lang_code=self.lang_code)
        self.project_tab = ProjectManagerWindow(self.data_manager.project_data, self.data_manager.user_progress, self.data_manager, Constants.RARITY_COLORS, lang_code=self.lang_code)
        self.item_db_tab = ItemDatabaseWindow(self.data_manager, lang_code=self.lang_code)
        self.settings_tab = SettingsWindow(self.config_manager, data_manager=self.data_manager, on_save_callback=settings_callback)
        self.about_tab = AboutTab(app_version, app_update_checker_func)

        # Add Tabs
        self.tabs.addTab(self.quest_tab, "Quests")
        self.tabs.addTab(self.hideout_tab, "Hideout")
        self.tabs.addTab(self.project_tab, "Projects")
        self.tabs.addTab(self.item_db_tab, "Item Database")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.about_tab, "About")
        
        # Connect signals
        self.settings_tab.data_restored.connect(self.on_data_restored)

        # --- CONNECT SIGNALS FOR AUTO-SAVE ---
        # When any tab triggers an auto-save, we emit our own signal
        self.hideout_tab.progress_saved.connect(self.progress_saved.emit)
        self.quest_tab.progress_saved.connect(self.progress_saved.emit)
        self.project_tab.progress_saved.connect(self.progress_saved.emit)
        self.item_db_tab.progress_saved.connect(self.progress_saved.emit)
        self.settings_tab.progress_saved.connect(self.progress_saved.emit)

        bottom_layout = QHBoxLayout(); main_layout.addLayout(bottom_layout)
        self.reset_btn = QPushButton("Reset"); self.reset_btn.setObjectName("action_button_red"); self.reset_btn.clicked.connect(self.handle_reset)
        bottom_layout.addWidget(self.reset_btn); bottom_layout.addStretch()
        self.close_btn = QPushButton("Close"); self.close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self.close_btn)

        self.tabs.currentChanged.connect(self.update_reset_button)
        self.update_reset_button(self.tabs.currentIndex())
        self.hide()

    def on_data_restored(self):
        """Called when data is restored from backup. Reloads all tabs."""
        self.hideout_tab.reload_data()
        self.quest_tab.reload_data()
        self.project_tab.reload_data()

    def update_reset_button(self, index):
        current_widget = self.tabs.widget(index)
        if current_widget == self.hideout_tab: self.reset_btn.setText("Reset Hideout"); self.reset_btn.setVisible(True)
        elif current_widget == self.quest_tab: self.reset_btn.setText("Reset Quests"); self.reset_btn.setVisible(True)
        elif current_widget == self.project_tab: self.reset_btn.setText("Reset Projects"); self.reset_btn.setVisible(True)
        elif current_widget == self.item_db_tab: self.reset_btn.setText("Reset Item Data"); self.reset_btn.setVisible(True)
        else: self.reset_btn.setVisible(False)

    def handle_reset(self):
        current_widget = self.tabs.currentWidget()
        if hasattr(current_widget, 'confirm_reset'):
            current_widget.confirm_reset()
        elif hasattr(current_widget, 'reset_state'):
            current_widget.reset_state()

    def closeEvent(self, event):
        # Save Window State
        self.config_manager.set_window_geometry(self.x(), self.y(), self.width(), self.height())
        self.config_manager.set_banner_visible(self.banner_container.isVisible())
        self.config_manager.save()

        # Force a final save on all tabs before closing
        for tab in [self.hideout_tab, self.quest_tab, self.project_tab, self.item_db_tab]:
            if hasattr(tab, 'save_state'): tab.save_state()
        super().closeEvent(event)

    def toggle_banner(self):
        if self.banner_container.isVisible():
            self.banner_container.hide()
            self.toggle_banner_btn.setText("▲") # Pointing up to show/expand? Or just swapped from before.
            self.toggle_banner_btn.setToolTip("Show Banner")
        else:
            self.banner_container.show()
            self.toggle_banner_btn.setText("▼")
            self.toggle_banner_btn.setToolTip("Hide Banner")

    def cleanup(self):
        if hasattr(self, 'item_db_tab'):
            self.item_db_tab.cleanup()