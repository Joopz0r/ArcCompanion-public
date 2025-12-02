from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, 
                             QLabel, QSizePolicy, QTextEdit)
from PyQt6.QtCore import pyqtSignal, Qt, QUrl, QSize
from PyQt6.QtGui import QIcon, QPixmap, QDesktopServices, QCursor, QFont
import os
from .constants import Constants
from .hideout_manager_window import HideoutManagerWindow
from .quest_manager_window import QuestManagerWindow
from .project_manager_window import ProjectManagerWindow
from .item_database_window import ItemDatabaseWindow
from .settings_window import SettingsWindow

class ClickableBanner(QLabel):
    def __init__(self, image_path, target_url, fallback_text="Support!", bg_color="#333", parent=None):
        super().__init__(parent)
        self.target_url = target_url
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.original_pixmap = None
        
        # Policy: Expand horizontally, but keep fixed height range
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(90)  # Force them to be at least this tall
        self.setMaximumHeight(120) # Don't get too huge
        self.setScaledContents(False) # We handle scaling manually for quality

        # Check if image exists
        if image_path and os.path.exists(image_path):
            self.original_pixmap = QPixmap(image_path)
            self.update_pixmap()
            self.setStyleSheet("QLabel { border: 1px solid #3E4451; border-radius: 4px; background-color: #1A1F2B; } QLabel:hover { border: 1px solid #4476ED; }")
        else:
            # Fallback text style (CSS Button look)
            self.setText(fallback_text)
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Use provided bg_color (Discord Blurple or Dark Grey)
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color}; 
                    color: white; 
                    font-weight: bold; 
                    font-size: 16px;
                    border-radius: 5px; 
                    border: 1px solid #3E4451;
                }}
                QLabel:hover {{
                    border: 1px solid #ffffff;
                    background-color: {bg_color}dd; /* Slight transparency on hover */
                }}
            """)

    def resizeEvent(self, event):
        if self.original_pixmap:
            self.update_pixmap()
        super().resizeEvent(event)

    def update_pixmap(self):
        if not self.original_pixmap: return
        
        # Scale image to fit the label size while keeping aspect ratio
        # mode=Qt.AspectRatioMode.KeepAspectRatioByExpanding ensures it fills the height
        scaled = self.original_pixmap.scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self.target_url))

# --- NEW CLASS: ABOUT TAB ---
class AboutTab(QWidget):
    def __init__(self, app_version, check_update_func=None):
        super().__init__()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # App Title
        title_lbl = QLabel("Arc Companion")
        title_lbl.setStyleSheet("font-size: 28px; font-weight: bold; color: #E5C07B;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        # Version
        version_lbl = QLabel(f"Version: {app_version}")
        version_lbl.setStyleSheet("font-size: 16px; color: #ABB2BF;")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_lbl)

        # --- UPDATE CHECK BUTTON ---
        if check_update_func:
            check_btn = QPushButton("Check for App Updates")
            check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            check_btn.setFixedWidth(200)
            check_btn.setStyleSheet("""
                QPushButton { background-color: #3E4451; color: white; border: 1px solid #555; padding: 6px; border-radius: 4px; font-weight: bold;}
                QPushButton:hover { background-color: #4B5363; border-color: #777; }
            """)
            check_btn.clicked.connect(check_update_func)
            
            # Center the button
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(check_btn)
            btn_layout.addStretch()
            layout.addLayout(btn_layout)
        # ---------------------------
        
        layout.addSpacing(10)
        
        # Links Section
        def make_link(text, url, subtext=None):
            lbl = QLabel(f"<a href='{url}' style='color: #61AFEF; text-decoration: none;'>{text}</a>")
            if subtext:
                lbl.setText(f"{subtext} <a href='{url}' style='color: #61AFEF; text-decoration: none;'>{text}</a>")
            lbl.setOpenExternalLinks(True)
            lbl.setFont(QFont("Segoe UI", 14))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lbl

        # Website Link
        layout.addWidget(make_link("www.arc-companion.xyz", "https://www.arc-companion.xyz"))
        
        # Data Credit
        layout.addWidget(make_link("RaidTheory/arcraiders-data", "https://github.com/RaidTheory/arcraiders-data", "Special thanks to:"))
        
        layout.addSpacing(20)
        
        # Patch Notes Header
        patch_lbl = QLabel("Patch Notes")
        patch_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #E0E6ED; margin-bottom: 5px;")
        layout.addWidget(patch_lbl)
        
        # Patch Notes Box
        self.patch_notes = QTextEdit()
        self.patch_notes.setReadOnly(True)
        self.patch_notes.setStyleSheet("""
            QTextEdit {
                background-color: #232834;
                color: #E0E6ED;
                border: 1px solid #3E4451;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
                font-family: "Segoe UI";
            }
        """)
        
        # --- PATCH NOTES CONTENT ---
        notes = f"""
<b>v{app_version} - Localization & Polish Update</b><br>
<br>
<b>New Features:</b><br>
• Added Multi-Language Support (Game Language setting).<br>
• Added Settings Tab directly to the Hub.<br>
• Added Discord & Support Banners.<br>
• Added 'Check for Updates' button in About tab.<br>
<br>
<b>Improvements:</b><br>
• Fixed Quest Overlay closing immediately when mouse no close.<br>
• Progress Hub now opens automatically on startup.<br>
• Fixed duplicate items appearing in Item Database.<br>
• Settings window is now embedded as a tab for easier access.<br>
<br>
<b>Bug Fixes:</b><br>
• Fixed scrolling issue in Settings where mouse wheel changed values.<br>
• Fixed overlay capture logic to ensure previous overlays close first.<br>
        """
        self.patch_notes.setHtml(notes)
        layout.addWidget(self.patch_notes)

# --- MAIN PROGRESS HUB ---
class ProgressHubWindow(QWidget):
    progress_saved = pyqtSignal()

    # ADDED app_update_checker_func argument
    def __init__(self, data_manager, settings_callback=None, app_version="1.0.0", app_update_checker_func=None):
        super().__init__()
        self.data_manager = data_manager

        self.setWindowTitle("Arc Companion - Progress Hub")
        self.resize(760, 850) 
        
        if os.path.exists(Constants.ICON_FILE):
            self.setWindowIcon(QIcon(Constants.ICON_FILE))
        
        self.setStyleSheet(Constants.DARK_THEME_QSS)

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        
        # --- Banners Layout (Horizontal) ---
        banner_layout = QHBoxLayout()
        banner_layout.setSpacing(15)
        banner_layout.setContentsMargins(5, 5, 5, 5)

        # 1. Support Banner
        self.support_banner = ClickableBanner(
            Constants.BANNER_IMAGE_PATH, 
            "https://ko-fi.com/joopz0r",
            "☕ Support the Dev",
            bg_color="#333" 
        )
        
        # 2. Discord Banner
        self.discord_banner = ClickableBanner(
            Constants.DISCORD_IMAGE_PATH, 
            "https://discord.gg/RzjPhXCXfH",
            "Join Discord",
            bg_color="#5865F2" 
        )
        
        banner_layout.addWidget(self.support_banner)
        banner_layout.addWidget(self.discord_banner)
        
        main_layout.addLayout(banner_layout)

        # --- Tabs ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.hideout_tab = HideoutManagerWindow(
            self.data_manager.hideout_data, 
            self.data_manager.user_progress, 
            self.data_manager, 
            Constants.RARITY_COLORS
        )
        self.quest_tab = QuestManagerWindow(
            self.data_manager, 
            self.data_manager.user_progress
        )
        self.project_tab = ProjectManagerWindow(
            self.data_manager.project_data, 
            self.data_manager.user_progress, 
            self.data_manager, 
            Constants.RARITY_COLORS
        )
        self.item_db_tab = ItemDatabaseWindow(self.data_manager)
        self.settings_tab = SettingsWindow(on_save_callback=settings_callback)
        
        # Connect language change signal
        self.settings_tab.language_changed.connect(self._on_language_changed)
        
        # --- NEW: ABOUT TAB ---
        # Pass the update checker function to the About Tab
        self.about_tab = AboutTab(app_version, app_update_checker_func)

        self.tabs.addTab(self.quest_tab, "Quests")
        self.tabs.addTab(self.hideout_tab, "Hideout")
        self.tabs.addTab(self.project_tab, "Expeditions")
        self.tabs.addTab(self.item_db_tab, "Item Database")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.about_tab, "About") # Added Index 5
        
        if hasattr(self.hideout_tab, '_perform_save'): self.hideout_tab._perform_save()
        if hasattr(self.quest_tab, '_perform_save'): self.quest_tab._perform_save()
        if hasattr(self.project_tab, '_perform_save'): self.project_tab._perform_save()
        if hasattr(self.item_db_tab, '_perform_save'): self.item_db_tab._perform_save()

        # --- Bottom Buttons ---
        bottom_layout = QHBoxLayout()
        main_layout.addLayout(bottom_layout)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("action_button_red")
        self.reset_btn.clicked.connect(self.handle_reset)
        bottom_layout.addWidget(self.reset_btn)

        bottom_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self.close_btn)

        self.tabs.currentChanged.connect(self.update_reset_button)
        self.update_reset_button(self.tabs.currentIndex())

        self.hide()

    def update_reset_button(self, index):
        current_widget = self.tabs.widget(index)
        if current_widget == self.hideout_tab:
            self.reset_btn.setText("Reset Hideout")
            self.reset_btn.setVisible(True)
        elif current_widget == self.quest_tab:
            self.reset_btn.setText("Reset Quests")
            self.reset_btn.setVisible(True)
        elif current_widget == self.project_tab:
            self.reset_btn.setText("Reset Expeditions")
            self.reset_btn.setVisible(True)
        else:
            self.reset_btn.setVisible(False)

    def handle_reset(self):
        current_widget = self.tabs.currentWidget()
        if current_widget == self.hideout_tab:
            self.hideout_tab.reset_hideout_progress_confirmation()
        elif current_widget == self.quest_tab:
            self.quest_tab.reset_quest_progress_confirmation()
        elif current_widget == self.project_tab:
            self.project_tab.reset_project_progress_confirmation()

    def _on_language_changed(self, lang_code):
        """Called when user changes language in Settings tab."""
        # Update tab content
        if hasattr(self.quest_tab, 'refresh_language'):
            self.quest_tab.refresh_language(lang_code)
        if hasattr(self.hideout_tab, 'refresh_language'):
            self.hideout_tab.refresh_language(lang_code)
        if hasattr(self.project_tab, 'refresh_language'):
            self.project_tab.refresh_language(lang_code)
        if hasattr(self.item_db_tab, 'refresh_language'):
            self.item_db_tab.refresh_language(lang_code)
        
        # Update tab labels
        tab_names = {
            'en': ['Quests', 'Hideout', 'Expeditions', 'Item Database', 'Settings', 'About'],
            'pt': ['Missões', 'Refúgio', 'Expedições', 'Base de Itens', 'Configurações', 'Sobre'],
            'es': ['Misiones', 'Refugio', 'Expediciones', 'Base de Datos de Objetos', 'Ajustes', 'Acerca de'],
            'fr': ['Quêtes', 'Refuge', 'Expéditions', 'Base de Données d\'Objets', 'Paramètres', 'À Propos'],
            'de': ['Quests', 'Versteck', 'Expeditionen', 'Gegenstandsdatenbank', 'Einstellungen', 'Über'],
            'ru': ['Задания', 'Убежище', 'Экспедиции', 'База Предметов', 'Настройки', 'О программе'],
            'pl': ['Zadania', 'Kryjówka', 'Ekspedycje', 'Baza Przedmiotów', 'Ustawienia', 'O programie'],
            'it': ['Missioni', 'Rifugio', 'Spedizioni', 'Database Oggetti', 'Impostazioni', 'Informazioni'],
            'ja': ['クエスト', '隠れ家', '遠征', 'アイテムデータベース', '設定', '情報'],
            'zh-CN': ['任务', '藏身处', '远征', '物品数据库', '设置', '关于'],
            'kr': ['퀘스트', '은신처', '원정', '아이템 데이터베이스', '설정', '정보']
        }
        
        # Default to English if language not found
        labels = tab_names.get(lang_code, tab_names['en'])
        
        for i, label in enumerate(labels):
            self.tabs.setTabText(i, label)
    
    def closeEvent(self, event):
        for tab in [self.hideout_tab, self.quest_tab, self.project_tab, self.item_db_tab]:
            if hasattr(tab, '_perform_save'):
                tab._perform_save()
        super().closeEvent(event)

    def cleanup(self):
        if hasattr(self.item_db_tab, 'cleanup'):
            self.item_db_tab.cleanup()
        if hasattr(self.settings_tab, 'cleanup'):
            self.settings_tab.cleanup()