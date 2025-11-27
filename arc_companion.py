from __future__ import annotations
import argparse, json, os, sys, re, configparser, time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import ImageEnhance
import pytesseract
import pyperclip
from pynput import keyboard as pynput_keyboard
import traceback  # For crash logging
from datetime import datetime # For crash logging timestamp

# RapidFuzz / Difflib check
try:
    from rapidfuzz import process, fuzz; _HAS_RAPIDFUZZ = True
except ImportError:
    import difflib; _HAS_RAPIDFUZZ = False

# PyQt6 Imports
from PyQt6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, 
                             QMessageBox, QProgressDialog)
from PyQt6.QtGui import QIcon, QAction, QDesktopServices
from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt, QUrl, QSharedMemory

# Module Imports
from modules.constants import Constants
from modules.overlay_ui import ItemOverlayUI, QuestOverlayUI
from modules.settings_window import SettingsWindow
from modules.progress_hub_window import ProgressHubWindow
from modules.data_manager import ItemDatabase, DataManager
from modules.image_processor import ImageProcessor
from modules.update_checker import UpdateChecker    # For Data Updates (Github/Data)
from modules.app_updater import AppUpdateChecker    # For App Updates (Website/Tracking)

# --- APP CONFIGURATION ---
APP_VERSION = "1.2.0"
# REPLACE THIS with your actual website JSON URL
APP_UPDATE_URL = "https://arc-companion.xyz/check_update.php" 
# -------------------------

@dataclass
class Config:
    tesseract_path: Optional[str] = None; once: bool = False; debug: bool = False
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Config:
        return cls(tesseract_path=args.tesseract, once=args.once, debug=args.debug)

class HotkeyListener(QObject):
    item_check_triggered = pyqtSignal()
    quest_log_triggered = pyqtSignal()
    
    def __init__(self, item_hotkey, quest_hotkey):
        super().__init__()
        self.item_hotkey_str = self._convert_to_pynput_format(item_hotkey)
        self.quest_hotkey_str = self._convert_to_pynput_format(quest_hotkey)
        self.listener = None

    def _convert_to_pynput_format(self, hotkey_str):
        parts = hotkey_str.lower().replace(" ", "").split('+')
        formatted_parts = []
        
        # Special keys that pynput expects in <brackets>
        modifiers = {
            'ctrl', 'shift', 'alt', 'cmd', 'enter', 'tab', 'esc', 
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'insert', 'delete', 'home', 'end', 'pageup', 'pagedown'
        }
        
        for part in parts:
            if part in modifiers:
                formatted_parts.append(f"<{part}>")
            else:
                formatted_parts.append(part)
        
        return '+'.join(formatted_parts)

    def run(self):
        print(f"Hotkey listener started. Mapping: Item='{self.item_hotkey_str}', Quest='{self.quest_hotkey_str}'")
        
        hotkeys = {
            self.item_hotkey_str: self._on_item_check,
            self.quest_hotkey_str: self._on_quest_log
        }

        try:
            with pynput_keyboard.GlobalHotKeys(hotkeys) as self.listener:
                self.listener.join()
        except Exception as e:
            print(f"Error in Hotkey Listener: {e}")

    def stop(self):
        if self.listener:
            self.listener.stop()

    def _on_item_check(self):
        self.item_check_triggered.emit()

    def _on_quest_log(self):
        self.quest_log_triggered.emit()

class ArcCompanionApp(QObject):
    # Signal to trigger the initial data download in the worker thread
    start_initial_download = pyqtSignal(list)

    def __init__(self, config: Config):
        super().__init__()
        # Note: QApplication is created in main() now to handle shared memory check
        self.app = QApplication.instance() 
        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self.cleanup_threads)
        self.cmd_config = config 
        self.user_settings = configparser.ConfigParser()
        
        # 1. Initialize core data systems (Attempt to load local data)
        self.db = ItemDatabase()
        self.data_manager = DataManager(self.db.items)
        self.overlays = []

        self.reload_settings(is_initial_load=True)

        # 2. Initialize Windows
        # Pass reload_settings to ProgressHub so the Settings Tab can use it
        # NEW: Pass APP_VERSION so About Tab can display it
        self.progress_hub = ProgressHubWindow(self.data_manager, self.reload_settings, APP_VERSION)
        self.progress_hub.progress_saved.connect(self.data_manager.reload_progress)
        
        # --- NEW: Open Progress Hub on Start ---
        self.progress_hub.show()
        # ---------------------------------------
        
        # 3. Setup System Tray
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon(Constants.ICON_FILE if os.path.exists(Constants.ICON_FILE) else self.app.style().standardIcon(self.app.style().StandardPixmap.SP_ComputerIcon)))
        menu = QMenu()
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings_tab)
        
        hub_action = QAction("Progress Hub", self)
        hub_action.triggered.connect(self.progress_hub.show)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_app)
        
        menu.addAction(settings_action)
        menu.addAction(hub_action)
        
        # Only show test action in debug mode
        if self.cmd_config.debug:
            menu.addSeparator()
            test_ocr_action = QAction("Test Item Check (No Hotkey)", self)
            test_ocr_action.triggered.connect(lambda: self.process_item_check(from_tray=True))
            menu.addAction(test_ocr_action)
        
        menu.addSeparator()
        menu.addAction(exit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.show()

        # 4. Start Hotkey Thread
        self.hotkey_thread = QThread()
        hotkey_item = self.user_settings.get('Hotkeys', 'price_check', fallback='ctrl+f')
        hotkey_quest = self.user_settings.get('Hotkeys', 'quest_log', fallback='ctrl+e')
        
        self.hotkey_worker = HotkeyListener(hotkey_item, hotkey_quest)
        self.hotkey_worker.moveToThread(self.hotkey_thread)
        
        self.hotkey_worker.item_check_triggered.connect(self.process_item_check)
        self.hotkey_worker.quest_log_triggered.connect(self.process_quest_log)
        
        self.hotkey_thread.started.connect(self.hotkey_worker.run)
        self.hotkey_thread.start()

        # 5. CHECK: Does data exist? (For first run)
        self.ensure_data_exists()

        # 6. CHECK: Is there a new app version? (From your website - with Tracking)
        self.check_for_app_updates()

    def show_settings_tab(self):
        self.progress_hub.show()
        # Assuming Settings is the 5th tab (0-4 index)
        self.progress_hub.tabs.setCurrentIndex(4) 

    # --- DATA CHECK & INITIAL DOWNLOAD LOGIC ---
    def ensure_data_exists(self):
        """Checks if the data folder exists/is populated. If not, prompts for download."""
        data_exists = os.path.exists(Constants.DATA_DIR) and os.path.exists(os.path.join(Constants.DATA_DIR, 'versions.json'))
        
        if not data_exists:
            msg = QMessageBox()
            msg.setWindowTitle("Missing Data")
            msg.setText("The application data (Items, Quests, Images) seems to be missing.\nThis is likely your first run.\n\nWould you like to download the data now?")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                self.start_initial_update()
            else:
                QMessageBox.warning(None, "Warning", "The application will not function correctly without data.")

    def start_initial_update(self):
        """Sets up the UpdateChecker solely for the initial download."""
        self.initial_update_thread = QThread()
        self.initial_update_worker = UpdateChecker()
        self.initial_update_worker.moveToThread(self.initial_update_thread)

        self.start_initial_download.connect(self.initial_update_worker.download_updates)
        
        self.initial_update_worker.update_check_finished.connect(self._on_initial_check_finished)
        self.initial_update_worker.download_progress.connect(self._on_initial_progress)
        self.initial_update_worker.update_complete.connect(self._on_initial_complete)
        
        self.initial_update_thread.finished.connect(self.initial_update_worker.deleteLater)
        self.initial_update_thread.start()

        # Create a Progress Dialog
        self.progress_dialog = QProgressDialog("Connecting to server...", "Cancel", 0, 0)
        self.progress_dialog.setWindowTitle("Downloading Data")
        self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        # Trigger check
        self.initial_update_worker.run_check()

    def _on_initial_check_finished(self, files_to_download, message):
        if files_to_download:
            self.progress_dialog.setLabelText(f"Found {len(files_to_download)} files. Starting download...")
            self.progress_dialog.setMaximum(len(files_to_download))
            self.start_initial_download.emit(files_to_download)
        else:
            self.progress_dialog.close()
            QMessageBox.information(None, "Data Check", "No data found to download, or server unreachable.")
            self.cleanup_initial_thread()

    def _on_initial_progress(self, current, total, filename):
        if self.progress_dialog.wasCanceled():
            self.cleanup_initial_thread()
            return
        self.progress_dialog.setValue(current)
        self.progress_dialog.setLabelText(f"Downloading: {filename}")

    def _on_initial_complete(self, success, message):
        self.progress_dialog.close()
        if success:
            QMessageBox.information(None, "Download Complete", "Data downloaded successfully!")
            self.reload_data_subsystems()
        else:
            QMessageBox.critical(None, "Download Failed", f"Failed to download data: {message}")
        self.cleanup_initial_thread()

    def cleanup_initial_thread(self):
        if hasattr(self, 'initial_update_thread') and self.initial_update_thread.isRunning():
            self.initial_update_thread.quit()
            self.initial_update_thread.wait()

    def reload_data_subsystems(self):
        """Re-initializes the database and managers after a fresh download."""
        print("Reloading data subsystems...")
        self.db = ItemDatabase()
        self.data_manager = DataManager(self.db.items)
        
        # Re-create Progress Hub with new data
        self.progress_hub.cleanup()
        self.progress_hub = ProgressHubWindow(self.data_manager, self.reload_settings, APP_VERSION)
        self.progress_hub.progress_saved.connect(self.data_manager.reload_progress)
        
        # Rebuild Tray Menu
        menu = self.tray.contextMenu()
        menu.clear()
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings_tab)
        
        hub_action = QAction("Progress Hub", self)
        hub_action.triggered.connect(self.progress_hub.show)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_app)
        
        menu.addAction(settings_action)
        menu.addAction(hub_action)
        
        # Only show test action in debug mode
        if self.cmd_config.debug:
            menu.addSeparator()
            test_ocr_action = QAction("Test Item Check (No Hotkey)", self)
            test_ocr_action.triggered.connect(lambda: self.process_item_check(from_tray=True))
            menu.addAction(test_ocr_action)
        
        menu.addSeparator()
        menu.addAction(exit_action)

    # --- APP UPDATE LOGIC (WEBSITE CHECK) ---
    def check_for_app_updates(self):
        self.app_update_thread = QThread()
        self.app_update_worker = AppUpdateChecker(APP_VERSION, APP_UPDATE_URL)
        self.app_update_worker.moveToThread(self.app_update_thread)

        # Connect signals
        self.app_update_thread.started.connect(self.app_update_worker.run_check)
        self.app_update_worker.update_available.connect(self.prompt_app_update)
        
        # Cleanup signals
        self.app_update_worker.check_finished.connect(self.app_update_thread.quit)
        self.app_update_worker.update_available.connect(self.app_update_thread.quit)
        self.app_update_thread.finished.connect(self.app_update_thread.deleteLater)

        self.app_update_thread.start()

    def prompt_app_update(self, new_version, url):
        msg = QMessageBox()
        msg.setWindowTitle("Update Available")
        msg.setText(f"A new version of Arc Companion is available!\n\nCurrent: {APP_VERSION}\nNew: {new_version}")
        msg.setInformativeText("Would you like to go to the download page?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(url))

    # --- CORE APP LOGIC ---
    def reload_settings(self, is_initial_load=False):
        self.user_settings.read(Constants.CONFIG_FILE)
        try:
            color_str = self.user_settings.get('OCR', 'target_color', fallback="249,238,223")
            self.target_color = tuple(map(int, color_str.split(',')))
        except (configparser.NoSectionError, ValueError):
            self.target_color = (249, 238, 223)
            
        # Load Language
        self.ocr_lang_code = self.user_settings.get('General', 'language', fallback='eng')
        
        # Determine JSON Language Code (e.g. 'spa' -> 'es') for data lookups
        self.json_lang_code = 'en' # Default
        for _, (json_c, tess_c) in Constants.LANGUAGES.items():
            if tess_c == self.ocr_lang_code:
                self.json_lang_code = json_c
                break
        
        if is_initial_load: 
            print(f"[INFO] Using target tooltip color: {self.target_color}")
            print(f"[INFO] OCR Language: {self.ocr_lang_code} (Data Lang: {self.json_lang_code})")
        else: 
            print("Settings reloaded. Note: Hotkey changes require an app restart.")

    def process_item_check(self, from_tray=False):
        print("\n--- Triggering Item Check ---")
        try:
            # --- CLEANUP START ---
            for overlay in self.overlays: overlay.close()
            self.overlays.clear()
            time.sleep(0.1) # Wait 100ms for the windows to visually disappear
            # --- CLEANUP END ---

            # If triggered from tray, scan full screen because mouse is at the bottom
            img = ImageProcessor.capture_and_process(self.target_color, full_screen=from_tray)
            if img is None:
                return
            
            if self.cmd_config.debug:
                if ImageProcessor.find_color_region(img, self.target_color):
                    print("[DEBUG] Tooltip color region found! Cropping to tooltip.")
            
            img = img.convert('L')
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            
            # --- LANGUAGE SUPPORT LOGIC ---
            custom_lang_file = os.path.join(Constants.TESSDATA_DIR, f"{self.ocr_lang_code}.traineddata")
            
            if os.path.exists(custom_lang_file):
                # Use the custom folder via Environment Variable to avoid path quoting issues
                os.environ["TESSDATA_PREFIX"] = Constants.TESSDATA_DIR
                tess_config = "--psm 6"
                lang = self.ocr_lang_code
            else:
                # Fallback logic - ensure we don't have a stray env var
                if "TESSDATA_PREFIX" in os.environ:
                    del os.environ["TESSDATA_PREFIX"]

                if self.ocr_lang_code != 'eng':
                    print(f"[WARN] Language file for '{self.ocr_lang_code}' not found in {Constants.TESSDATA_DIR}. Falling back to 'eng'.")
                tess_config = "--psm 6"
                lang = 'eng'
            # ------------------------------
            
            lines = pytesseract.image_to_string(img, lang=lang, config=tess_config).splitlines()
            if not lines:
                return
                
            cleaned = [re.sub(r'[^a-zA-Z0-9\s-]', '', l).strip() for l in lines if len(l.strip()) >= 3]
            
            item_names_lower = [name.lower() for name in self.data_manager.items.keys()]
            lower_to_actual_name = {name.lower(): name for name in self.data_manager.items.keys()}

            best_name, best_score = None, 0
            search_candidates = cleaned + [f"{cleaned[i]} {cleaned[i+1]}" for i in range(len(cleaned) - 1)] if len(cleaned) > 1 else cleaned
            
            for candidate in [c for c in search_candidates if len(c) >= 3]:
                if _HAS_RAPIDFUZZ:
                    result = process.extractOne(candidate.lower(), item_names_lower, scorer=fuzz.token_sort_ratio)
                    if result and result[1] > best_score:
                        best_score, best_name = result[1], lower_to_actual_name[result[0]]

            if best_score < 70:
                best_name = None

            if self.cmd_config.debug:
                print(f"[DEBUG] Best Match: '{best_name}' with score {best_score}")

            if best_name:
                print(f"Item Found: {best_name}. Preparing overlay...")
                
                # Fetch Item Details and Note
                item_details = self.data_manager.get_item_by_name(best_name)
                item_id = item_details.get('id') if item_details else None
                user_note = self.data_manager.get_item_note(item_id) if item_id else ""
                
                data = {
                    "item": item_details, 
                    "trade": self.data_manager.find_trades_for_item(best_name),
                    "hideout": self.data_manager.find_hideout_requirements(best_name), 
                    "project": self.data_manager.find_project_requirements(best_name),
                    "blueprint": f"{best_name} Blueprint" in self.data_manager.items,
                    "note": user_note
                }
                self.display_item_overlay(data)
                
        except Exception as e:
            import traceback
            print(f"--- FATAL ERROR in process_item_check: {e} ---")
            traceback.print_exc()

    def process_quest_log(self):
        try:
            print("Processing Quest Log display...")
            tracked = self.data_manager.get_filtered_quests(tracked_only=True)
            self.display_quest_overlay(tracked)
        except Exception as e:
            print(f"--- ERROR in process_quest_log: {e} ---")

    def display_item_overlay(self, data):
        # Pass the current JSON language code to the overlay for localization
        ov = ItemOverlayUI.create_window(
            data['item'], self.user_settings, data['blueprint'], 
            data['hideout'], data['project'], data['trade'], 
            self.data_manager, data['note'], 
            lang_code=self.json_lang_code
        )
        self.overlays.append(ov)

    def display_quest_overlay(self, tracked):
        ov = QuestOverlayUI.create_window(tracked, self.user_settings)
        self.overlays.append(ov)

    def cleanup_threads(self):
        print("Cleaning up threads...")
        if hasattr(self, 'hotkey_worker') and self.hotkey_worker:
            self.hotkey_worker.stop()
            self.hotkey_worker = None
        
        if hasattr(self, 'hotkey_thread') and self.hotkey_thread and self.hotkey_thread.isRunning():
            self.hotkey_thread.quit()
            self.hotkey_thread.wait()

        if hasattr(self, 'settings_win'):
            self.settings_win.cleanup()
            
        if hasattr(self, 'progress_hub'):
            self.progress_hub.cleanup()
            
        self.cleanup_initial_thread()

    def quit_app(self):
        print("Shutting down...")
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

def main():
    def get_tesseract_path():
        # If running as a PyInstaller one-file EXE, tesseract should be bundled
        if getattr(sys, 'frozen', False):
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            return os.path.join(base_path, 'Tesseract-OCR', 'tesseract.exe')
        return None

    parser = argparse.ArgumentParser()
    parser.add_argument('--tesseract', default=get_tesseract_path())
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--debug', action='store_true', help='Enable detailed console logging.')
    
    args = parser.parse_args()
    config = Config.from_args(args)
    
    if config.tesseract_path: 
        pytesseract.pytesseract.tesseract_cmd = config.tesseract_path
    
    # --- CRASH HANDLER WRAPPER ---
    try:
        # 1. Create QApplication FIRST (Needed for QSharedMemory/MessageBox)
        app_instance = QApplication(sys.argv)
        
        # 2. SINGLE INSTANCE CHECK (QSharedMemory)
        shared_memory = QSharedMemory("ArcCompanion_Unique_Instance_Lock")
        
        if not shared_memory.create(1):
            QMessageBox.warning(None, "Already Running", 
                                "Arc Companion is already running!\nCheck your system tray.")
            sys.exit(0)

        # 3. Start App Logic
        app = ArcCompanionApp(config)
        app.run()
        
    except Exception as e:
        # If app crashes, write log to Desktop
        error_msg = traceback.format_exc()
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            log_file = os.path.join(desktop, "arc_companion_crash.log")
            
            with open(log_file, "w") as f:
                f.write(f"Crash Time: {datetime.now()}\n")
                f.write(error_msg)
                
            # Try to show a popup if Qt is still alive
            if not QApplication.instance(): 
                _ = QApplication(sys.argv)
            QMessageBox.critical(None, "Fatal Error", f"The application crashed.\nLog saved to Desktop.\n\nError: {e}")
        except:
            print("CRITICAL FAIL:", e)
        sys.exit(1)

if __name__ == '__main__':
    main()