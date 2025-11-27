import os
import sys

def get_base_path():
    """
    Determines the base path for resources (icons/images bundled inside the EXE).
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return sys._MEIPASS
    except AttributeError:
        return os.path.abspath(".")

def get_writable_data_dir():
    """
    Determines where to save User Data (JSONs, downloaded images).
    """
    if getattr(sys, 'frozen', False):
        local_app_data = os.getenv('LOCALAPPDATA')
        base = os.path.join(local_app_data, 'ArcCompanion', 'data')
    else:
        base = os.path.join(os.path.abspath("."), 'data')
    
    os.makedirs(base, exist_ok=True)
    return base

class Constants:
    # --- DYNAMIC DATA PATH ---
    DATA_DIR = get_writable_data_dir()
    
    ITEMS_DIR = os.path.join(DATA_DIR, 'items')
    HIDEOUT_DIR = os.path.join(DATA_DIR, 'hideout')
    QUESTS_DIR = os.path.join(DATA_DIR, 'quests')
    
    # --- TESSERACT LANGUAGES ---
    TESSDATA_DIR = os.path.join(DATA_DIR, 'tessdata')
    
    LANGUAGES = {
        "English": ("en", "eng"),
        "German": ("de", "deu"),
        "French": ("fr", "fra"),
        "Spanish": ("es", "spa"),
        "Portuguese": ("pt", "por"),
        "Polish": ("pl", "pol"),
        "Russian": ("ru", "rus"),
        "Italian": ("it", "ita"),
        "Japanese": ("ja", "jpn"),
        "Chinese (Simplified)": ("zh-CN", "chi_sim"),
        "Chinese (Traditional)": ("zh-TW", "chi_tra"),
        "Korean": ("kr", "kor"),
        "Turkish": ("tr", "tur"),
        "Ukrainian": ("uk", "ukr")
    }

    # --- File Paths (External) ---
    CONFIG_FILE = os.path.join(DATA_DIR, 'config.ini')
    PROGRESS_FILE = os.path.join(DATA_DIR, 'progress.json')
    TRADES_FILE = os.path.join(DATA_DIR, 'trades.json') 
    PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json') 

    # --- INTERNAL RESOURCES ---
    ICON_FILE = os.path.join(get_base_path(), 'arccompanion.ico')
    
    if getattr(sys, 'frozen', False):
        _ASSETS_DIR = os.path.join(sys._MEIPASS, 'bundled_assets')
    else:
        _ASSETS_DIR = os.path.join(os.path.abspath("."), "data", "images")
    
    _COIN_SVG = os.path.join(_ASSETS_DIR, 'coins.svg')
    _COIN_PNG = os.path.join(_ASSETS_DIR, 'coins.png')
    
    COIN_ICON_PATH = _COIN_SVG if os.path.exists(_COIN_SVG) else _COIN_PNG
    
    # Banners
    BANNER_IMAGE_PATH = os.path.join(_ASSETS_DIR, 'support_banner.png')
    DISCORD_IMAGE_PATH = os.path.join(_ASSETS_DIR, 'discord_banner.png') # NEW

    # PyQt Stylesheet
    DARK_THEME_QSS = """
    QWidget {
        font-family: "Segoe UI";
        font-size: 14px;
        color: #E0E6ED;
    }
    
    ProgressHubWindow, ItemDatabaseWindow, SettingsWindow {
        background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, 
                                          stop:0 #2B303B, stop:1 #1A1F26);
    }

    HideoutManagerWindow, QuestManagerWindow, ProjectManagerWindow, BaseManagerWindow {
        background-color: transparent;
    }
    
    QWidget#scroll_content {
        background-color: transparent;
    }

    QFrame#StationFrame, QFrame#QuestFrame, QFrame#ProjectFrame, QFrame#card {
        background-color: #1A1F2B;
        border: 1px solid #333;
        border-radius: 5px;
        margin-top: 8px;
    }

    QFrame#StationFrame { border-top: 3px solid #4476ED; }
    QFrame#QuestFrame   { border-top: 3px solid #4CAF50; }
    QFrame#ProjectFrame { border-top: 3px solid #ED9A44; }

    QLabel[objectName="Header"] {
        font-size: 18px;
        font-weight: bold;
        color: #E0E6ED;
        border: none;
        padding-bottom: 5px;
    }

    QLineEdit {
        background-color: #232834;
        border: 1px solid #333;
        padding: 6px;
        border-radius: 4px;
        color: white;
    }
    QLineEdit:focus {
        border: 1px solid #4476ED;
    }
    
    QComboBox {
        background-color: #232834;
        border: 1px solid #333;
        border-radius: 4px;
        padding: 5px 10px;
        color: #E0E6ED;
        min-width: 120px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #1A1F2B;
        selection-background-color: #4476ED;
        color: #E0E6ED;
        border: 1px solid #333;
    }

    QPushButton {
        background-color: #3E4451;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #4B5363;
    }
    QPushButton:disabled {
        background-color: #2C323C;
        color: #5C6370;
    }
    
    QPushButton[objectName="inv_button"] {
        background-color: #232834;
        border: 1px solid #333;
        padding: 4px;
        font-weight: bold;
        border-radius: 4px;
    }
    QPushButton[objectName="inv_button"]:hover {
        background-color: #4476ED;
        border: 1px solid #4476ED;
    }

    QPushButton[objectName="action_button_green"] {
        background-color: rgba(76, 175, 80, 0.2); 
        color: #4CAF50;
        border: 1px solid #4CAF50;
    }
    QPushButton[objectName="action_button_green"]:hover {
        background-color: rgba(76, 175, 80, 0.4);
    }

    QPushButton[objectName="action_button_red"] {
        background-color: rgba(211, 47, 47, 0.2);
        color: #ef5350;
        border: 1px solid #ef5350;
    }
    QPushButton[objectName="action_button_red"]:hover {
        background-color: rgba(211, 47, 47, 0.4);
    }

    QScrollArea {
        border: none;
        background-color: transparent;
    }
    
    QScrollBar:vertical {
        border: none;
        background: #1A1F26;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #3E4451;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #555;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    QCheckBox {
        spacing: 8px;
        color: #E0E6ED;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #333;
        border-radius: 3px;
        background-color: #232834;
    }
    QCheckBox::indicator:hover {
        border: 1px solid #4476ED;
    }
    QCheckBox::indicator:checked {
        background-color: #4476ED;
        border: 1px solid #4476ED;
        image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBvbHlsaW5lIHBvaW50cz0iMjAgNiA5IDE3IDQgMTIiPjwvcG9seWxpbmU+PC9zdmc+);
    }

    QProgressBar {
        border: 1px solid #333;
        border-radius: 4px;
        background-color: #232834;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #4476ED;
        border-radius: 3px; 
    }
    QProgressBar[complete="true"]::chunk {
        background-color: #4CAF50;
    }

    QTabWidget::pane {
        border: 1px solid #333;
        border-radius: 4px;
        background-color: transparent;
    }
    QTabBar::tab {
        background-color: #232834;
        color: #9DA5B4;
        padding: 10px 20px;
        border: 1px solid #333;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }
    QTabBar::tab:hover {
        background-color: #2C323C;
        color: white;
    }
    QTabBar::tab:selected {
        background-color: #4476ED; 
        color: white;
        border: 1px solid #444;
        border-bottom: 1px solid #232834;
    }

    QToolTip {
        background-color: #1A1F2B;
        color: #E0E6ED;
        border: 1px solid #333;
        padding: 8px;
        font-size: 13px;
    }

    QMessageBox {
        background-color: #2B303B;
    }
    QMessageBox QLabel {
        color: #E0E6ED;
    }
    """

    RARITY_COLORS = {
        "Common": "#B0B0B0",
        "Uncommon": "#98C379",  
        "Rare": "#61AFEF",      
        "Epic": "#C678DD",      
        "Legendary": "#E5C07B"  
    }
    QUEST_HEADER_COLOR = "#E5C07B" 
    QUEST_OBJECTIVE_COLOR = "#E0E6ED"