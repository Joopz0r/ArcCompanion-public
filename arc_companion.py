from __future__ import annotations
import argparse, os, sys, traceback
import ctypes
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from pynput import keyboard as pynput_keyboard
from PyQt6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu,
                             QMessageBox, QProgressDialog)
from PyQt6.QtGui import QIcon, QAction, QDesktopServices
from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt, QUrl, QSharedMemory

from modules.constants import Constants
from modules.overlay_ui import ItemOverlay, QuestOverlayUI
from modules.progress_hub_window import ProgressHubWindow
from modules.data_manager import ItemDatabase, DataManager
from modules.scanner import ItemScanner
from modules.update_checker import UpdateChecker
from modules.app_updater import AppUpdateChecker
from modules.config_manager import ConfigManager
from modules.remote_database import RemoteDatabaseDownloader

# --- SCIPY IMPORTS REMOVED HERE ---
# (They used to be here, but we deleted them because we use OpenCV now)

APP_VERSION = "1.3.1"
APP_UPDATE_URL = "https://arc-companion.xyz/check_update.php"

@dataclass
class Config:
    tesseract_path: Optional[str] = None; once: bool = False; debug: bool = False
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Config:
        return cls(tesseract_path=args.tesseract, once=args.once, debug=args.debug)

class HotkeyListener(QObject):
    item_check_triggered = pyqtSignal()
    quest_log_triggered = pyqtSignal()
    hub_triggered = pyqtSignal()

    def __init__(self, item_hotkey, quest_hotkey, hub_hotkey):
        super().__init__()
        self.item_hotkey_str = self._convert_to_pynput_format(item_hotkey)
        self.quest_hotkey_str = self._convert_to_pynput_format(quest_hotkey)
        self.hub_hotkey_str = self._convert_to_pynput_format(hub_hotkey)
        self.listener = None

    def _convert_to_pynput_format(self, hotkey_str):
        parts = hotkey_str.lower().replace(" ", "").split('+')
        formatted_parts = []
        modifiers = {'ctrl', 'shift', 'alt', 'cmd', 'enter', 'tab', 'esc', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'insert', 'delete', 'home', 'end', 'pageup', 'pagedown'}
        for part in parts:
            if part in modifiers: formatted_parts.append(f"<{part}>")
            else: formatted_parts.append(part)
        return '+'.join(formatted_parts)

    def run(self):
        print(f"Hotkey listener started. Mapping: Item='{self.item_hotkey_str}', Quest='{self.quest_hotkey_str}', Hub='{self.hub_hotkey_str}'")
        hotkeys = {
            self.item_hotkey_str: self._on_item_check,
            self.quest_hotkey_str: self._on_quest_log,
            self.hub_hotkey_str: self._on_hub
        }
        try:
            with pynput_keyboard.GlobalHotKeys(hotkeys) as self.listener: self.listener.join()
        except Exception as e: print(f"Error in Hotkey Listener: {e}")

    def stop(self):
        if self.listener: self.listener.stop()

    def _on_item_check(self): self.item_check_triggered.emit()
    def _on_quest_log(self): self.quest_log_triggered.emit()
    def _on_hub(self): self.hub_triggered.emit()

# --- SCAN WORKER (THREADING) ---
class ScanWorker(QObject):
    """
    Runs the screen scanning and OCR process in a separate thread.
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, scanner: ItemScanner, from_tray: bool):
        super().__init__()
        self.scanner = scanner
        self.from_tray = from_tray

    def run(self):
        try:
            # This calls the new OpenCV+MSS scanner
            result = self.scanner.scan_screen(full_screen=self.from_tray)
            self.finished.emit(result)
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))
            self.finished.emit(None)

class ArcCompanionApp(QObject):
    start_data_download = pyqtSignal(list)
    start_lang_download = pyqtSignal(str)

    def __init__(self, config: Config):
        super().__init__()
        self.app = QApplication.instance()
        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self.cleanup_threads)
        self.cmd_config = config

        # 1. Initialize Config Manager
        self.config_manager = ConfigManager()

        # 2. Initialize Data
        self.db = ItemDatabase()
        self.data_manager = DataManager(self.db.items)
        self.overlays = []
        self.scan_thread = None

        # 3. Initialize Scanner
        self.scanner = ItemScanner(self.cmd_config, self.data_manager)

        self.reload_settings(is_initial_load=True)

        # 4. Initialize Windows
        self.progress_hub = ProgressHubWindow(
            self.data_manager,
            self.config_manager,
            self.reload_settings,
            APP_VERSION,
            lambda: self.check_for_app_updates(manual=True),
            lang_code=self.json_lang_code
        )
        # NOTE: Do NOT connect to reload_progress here - it creates a new dict object
        # which breaks references held by manager windows. The in-memory data is already correct.

        self.progress_hub.settings_tab.request_data_update.connect(self.run_manual_data_check)
        self.progress_hub.settings_tab.request_lang_download.connect(self.run_lang_download)
        self.progress_hub.settings_tab.request_app_update.connect(lambda: self.check_for_app_updates(manual=True))
        self.progress_hub.settings_tab.hotkeys_updated.connect(self.restart_hotkeys)
        self.progress_hub.settings_tab.request_remote_database_download.connect(self.run_remote_database_download)

        self.progress_hub.show()

        # 5. Tray & Hotkeys
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon(Constants.ICON_FILE if os.path.exists(Constants.ICON_FILE) else self.app.style().standardIcon(self.app.style().StandardPixmap.SP_ComputerIcon)))
        self._build_tray_menu()
        self.tray.activated.connect(self.on_tray_icon_activated)
        self.tray.show()

        self.hotkey_thread = QThread()
        # 6. Startup Checks
        if self.ensure_data_exists():
            self.start_background_services()

    def start_background_services(self):
        """Starts hotkeys and app update checks after data is verified."""
        self._start_hotkey_service()
        self.check_for_app_updates(manual=False)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.restore_app()

    def _build_tray_menu(self):
        menu = QMenu()
        settings_action = QAction("Settings", self); settings_action.triggered.connect(self.show_settings_tab)
        hub_action = QAction("Progress Hub", self); hub_action.triggered.connect(self.restore_app)
        exit_action = QAction("Exit", self); exit_action.triggered.connect(self.quit_app)
        menu.addAction(settings_action); menu.addAction(hub_action)
        if self.cmd_config.debug:
            menu.addSeparator()
            test_ocr_action = QAction("Test Item Check (No Hotkey)", self)
            test_ocr_action.triggered.connect(lambda: self.process_item_check(from_tray=True))
            menu.addAction(test_ocr_action)
        menu.addSeparator(); menu.addAction(exit_action)
        self.tray.setContextMenu(menu)

    def _start_hotkey_service(self):
        hotkey_item = self.config_manager.get_item_hotkey()
        hotkey_quest = self.config_manager.get_quest_hotkey()
        hotkey_hub = self.config_manager.get_hub_hotkey()
        self.hotkey_worker = HotkeyListener(hotkey_item, hotkey_quest, hotkey_hub)
        self.hotkey_worker.moveToThread(self.hotkey_thread)
        self.hotkey_worker.item_check_triggered.connect(self.process_item_check)
        self.hotkey_worker.quest_log_triggered.connect(self.process_quest_log)
        self.hotkey_worker.hub_triggered.connect(self.restore_app)
        self.hotkey_thread.started.connect(self.hotkey_worker.run)
        self.hotkey_thread.start()

    def restart_hotkeys(self):
        print("Restarting hotkey service...")
        # 1. Stop existing
        if hasattr(self, 'hotkey_worker') and self.hotkey_worker:
            self.hotkey_worker.stop()

        if hasattr(self, 'hotkey_thread') and self.hotkey_thread:
            if self.hotkey_thread.isRunning():
                self.hotkey_thread.quit()
                self.hotkey_thread.wait()

        # 2. Re-create thread (QThreads are one-shot)
        self.hotkey_thread = QThread()
        self._start_hotkey_service()
        print("Hotkey service restarted.")

    def show_settings_tab(self):
        self.progress_hub.show()
        self.progress_hub.tabs.setCurrentIndex(4)

    def reload_settings(self, is_initial_load=False):
        self.config_manager.load()
        try:
            color_str = self.config_manager.get_ocr_color()
            self.target_color = tuple(map(int, color_str.split(',')))
        except ValueError: self.target_color = (249, 238, 223)

        self.ocr_lang_code = self.config_manager.get_language()
        self.json_lang_code = 'en'
        for _, (json_c, tess_c) in Constants.LANGUAGES.items():
            if tess_c == self.ocr_lang_code:
                self.json_lang_code = json_c; break

        full_screen = self.config_manager.get_full_screen_scan()
        save_debug = self.config_manager.get_save_debug_images()

        self.scanner.update_settings(self.target_color, self.ocr_lang_code, self.json_lang_code, full_screen_mode=full_screen, save_debug_images=save_debug)

        # --- NEW: Trigger Live Overlay Update ---
        for overlay in self.overlays:
            if hasattr(overlay, 'refresh_ui'):
                overlay.refresh_ui()
        # ----------------------------------------

        if is_initial_load: print(f"[INFO] Settings Loaded. Lang: {self.ocr_lang_code}")
        else: print("Settings reloaded.")

    # --- ITEM CHECK WITH THREADING ---
    def process_item_check(self, from_tray=False):
        # 1. Close overlays
        for overlay in self.overlays:
            overlay.close()
        self.overlays.clear()

        # 2. Prevent overlapping scans (CRASH FIX)
        if self.scan_thread:
            try:
                if self.scan_thread.isRunning():
                    print("[INFO] Scan already in progress.")
                    return
            except RuntimeError:
                # The C++ object was deleted, but Python reference exists.
                # We catch the error and reset the variable so we can start fresh.
                self.scan_thread = None

        # 3. Setup Worker
        self.scan_thread = QThread()
        self.scan_worker = ScanWorker(self.scanner, from_tray)
        self.scan_worker.moveToThread(self.scan_thread)

        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.finished.connect(self.handle_scan_result)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)

        self.scan_thread.start()

    def handle_scan_result(self, scan_result):
        if scan_result:
            self.display_item_overlay(scan_result)

    def process_quest_log(self):
        try:
            tracked = self.data_manager.get_filtered_quests(tracked_only=True, lang_code=self.json_lang_code)
            self.display_quest_overlay(tracked)
        except Exception as e: print(f"Error: {e}")

    def display_item_overlay(self, data):
        # Use simple instantiation instead of factory
        from modules.overlay_ui import ItemOverlay
        ov = ItemOverlay(data['item'], self.config_manager.parser, data['blueprint'], data['hideout'], data['project'], data['trade'], self.data_manager, data['note'], lang_code=self.json_lang_code, stash_count=data['stash_count'], is_collected_blueprint=data['is_collected_bp'])
        ov.show_smart()
        self.overlays.append(ov)

    def display_quest_overlay(self, tracked):
        ov = QuestOverlayUI.create_window(tracked, self.config_manager.parser, self.data_manager, lang_code=self.json_lang_code)
        self.overlays.append(ov)

    def ensure_data_exists(self):
        if not (os.path.exists(Constants.DATA_DIR) and os.path.exists(os.path.join(Constants.DATA_DIR, 'versions.json'))):
            msg = QMessageBox(self.progress_hub if hasattr(self, 'progress_hub') else None)
            msg.setWindowTitle("Missing Data"); msg.setText("Missing data. Download now?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if msg.exec() == QMessageBox.StandardButton.Yes:
                self.run_manual_data_check(initial=True)
                return False
            return False # User said no, but data is still missing
        return True

    def run_manual_data_check(self, initial=False):
        if hasattr(self, 'data_update_thread') and self.data_update_thread.isRunning(): return

        self.data_update_thread = QThread()
        self.data_updater = UpdateChecker()
        self.data_updater.moveToThread(self.data_update_thread)

        self.start_data_download.connect(self.data_updater.download_updates)
        self.data_updater.update_check_finished.connect(self._on_data_check_finished)

        if not initial:
            self.data_updater.checking_for_updates.connect(lambda: self.progress_hub.settings_tab.set_update_status("Checking..."))
            self.data_updater.download_progress.connect(lambda c, t, f: self.progress_hub.settings_tab.set_update_status(f"Downloading ({c}/{t}): {f}"))
            # Connect to our new handler instead of just setting status
            self.data_updater.update_complete.connect(self._on_manual_download_complete)
        else:
            self.progress_dialog = QProgressDialog("Connecting...", "Cancel", 0, 0, self.progress_hub)
            self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal); self.progress_dialog.show()
            self.data_updater.download_progress.connect(lambda c, t, f: self.progress_dialog.setLabelText(f"Downloading ({c}/{t}): {f}"))
            self.data_updater.update_complete.connect(self._on_initial_complete)

        self.data_update_thread.started.connect(self.data_updater.run_check)
        self.data_update_thread.finished.connect(self.data_updater.deleteLater)
        self.data_update_thread.start()

    def _on_manual_download_complete(self, success, message):
        """Called when a manual update download finishes."""
        self.progress_hub.settings_tab.set_update_status(message)
        self.data_update_thread.quit()

        if success:
            # Check if remote database download is enabled and trigger it
            if self.config_manager.get_remote_database_enabled():
                self.run_remote_database_download(auto_triggered=True)
            else:
                # Hot Reload: Store state -> Reload -> Restore state
                try:
                    current_tab_index = self.progress_hub.tabs.currentIndex()
                    was_visible = self.progress_hub.isVisible()
                    saved_geometry = self.progress_hub.saveGeometry()

                    self.reload_data_subsystems()

                    if was_visible:
                        self.progress_hub.restoreGeometry(saved_geometry)
                        self.progress_hub.show()
                        self.progress_hub.tabs.setCurrentIndex(current_tab_index)

                    QMessageBox.information(self.progress_hub, "Update Complete", "Data updated and reloaded successfully.")
                except Exception as e:
                    print(f"Error during hot reload: {e}")
                    QMessageBox.warning(self.progress_hub, "Reload Error", f"Data downloaded, but reload failed: {e}\\nPlease restart the app manually.")

    def _on_data_check_finished(self, files, msg):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            if files: self.progress_dialog.setMaximum(len(files)); self.start_data_download.emit(files)
            else: self.progress_dialog.close(); self.data_update_thread.quit()
        else:
            self.progress_hub.settings_tab.set_update_status(msg)
            if files:
                reply = QMessageBox.question(self.progress_hub, "Update", f"{msg}\nDownload now?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes: self.start_data_download.emit(files)
                else: self.data_update_thread.quit()
            else: self.data_update_thread.quit()

    def run_lang_download(self, lang_code):
        if hasattr(self, 'data_update_thread') and self.data_update_thread.isRunning(): return
        self.data_update_thread = QThread()
        self.data_updater = UpdateChecker()
        self.data_updater.moveToThread(self.data_update_thread)
        self.start_lang_download.connect(self.data_updater.download_language)

        self.data_updater.download_progress.connect(lambda c, t, f: self.progress_hub.settings_tab.set_update_status(f"Downloading Language... {c}%"))
        self.data_updater.update_complete.connect(lambda s, m: self.progress_hub.settings_tab.set_update_status(m))
        self.data_updater.update_complete.connect(self.data_update_thread.quit)

        self.data_update_thread.started.connect(lambda: self.start_lang_download.emit(lang_code))
        self.data_update_thread.finished.connect(self.data_updater.deleteLater)
        self.data_update_thread.start()

    def _on_initial_complete(self, success, message):
        self.progress_dialog.close(); self.data_update_thread.quit()
        if success:
            # Check if remote database download is enabled and trigger it
            if self.config_manager.get_remote_database_enabled():
                self.run_remote_database_download(auto_triggered=True, on_complete=lambda: self.reload_data_subsystems() or self.start_background_services())
            else:
                self.reload_data_subsystems()
                self.start_background_services()
        else: QMessageBox.critical(self.progress_hub, "Failed", message)

    def reload_data_subsystems(self):
        self.db = ItemDatabase(); self.data_manager = DataManager(self.db.items)
        self.scanner = ItemScanner(self.cmd_config, self.data_manager)
        self.progress_hub.cleanup()
        self.progress_hub = ProgressHubWindow(self.data_manager, self.config_manager, self.reload_settings, APP_VERSION, lambda: self.check_for_app_updates(manual=True), lang_code=self.json_lang_code)

        # --- RE-CONNECT SIGNALS ---
        # Critical for hot reload: Re-attach buttons to their handlers
        self.progress_hub.settings_tab.request_data_update.connect(self.run_manual_data_check)
        self.progress_hub.settings_tab.request_lang_download.connect(self.run_lang_download)
        self.progress_hub.settings_tab.request_app_update.connect(lambda: self.check_for_app_updates(manual=True))
        self.progress_hub.settings_tab.hotkeys_updated.connect(self.restart_hotkeys)
        self.progress_hub.settings_tab.request_remote_database_download.connect(self.run_remote_database_download)
        # --------------------------

        self._build_tray_menu()

    def run_remote_database_download(self, auto_triggered=False, on_complete=None):
        """Download and merge remote database recommendations"""
        if not self.config_manager.get_remote_database_enabled():
            if not auto_triggered:
                QMessageBox.information(self.progress_hub, "Remote Database", "Remote database downloads are disabled. Enable it in Settings > Data Management.")
            return

        if hasattr(self, 'remote_db_thread') and self.remote_db_thread and self.remote_db_thread.isRunning():
            if not auto_triggered:
                QMessageBox.information(self.progress_hub, "Download in Progress", "Remote database download is already in progress.")
            return

        self.remote_db_thread = QThread()
        self.remote_db_downloader = RemoteDatabaseDownloader(self.config_manager)
        self.remote_db_downloader.moveToThread(self.remote_db_thread)

        # Connect signals
        self.remote_db_downloader.download_progress.connect(
            lambda msg: self.progress_hub.settings_tab.set_remote_database_status(msg, "#3498db")
        )
        self.remote_db_downloader.status_update.connect(
            lambda status: self.progress_hub.settings_tab.set_remote_database_status(status, "#2ecc71" if status == "Ready" else "#e74c3c")
        )

        def on_download_complete(success, message):
            self.remote_db_thread.quit()
            if success:
                self.progress_hub.settings_tab.set_remote_database_status(message, "#2ecc71")
                # Reload data subsystems to pick up merged recommendations
                try:
                    current_tab_index = self.progress_hub.tabs.currentIndex()
                    was_visible = self.progress_hub.isVisible()
                    saved_geometry = self.progress_hub.saveGeometry()

                    self.reload_data_subsystems()

                    if was_visible:
                        self.progress_hub.restoreGeometry(saved_geometry)
                        self.progress_hub.show()
                        self.progress_hub.tabs.setCurrentIndex(current_tab_index)

                    if not auto_triggered:
                        QMessageBox.information(self.progress_hub, "Download Complete", message)
                    if on_complete:
                        on_complete()
                except Exception as e:
                    print(f"Error during reload after remote database download: {e}")
                    if not auto_triggered:
                        QMessageBox.warning(self.progress_hub, "Reload Error", f"Database downloaded, but reload failed: {e}\nPlease restart the app manually.")
            else:
                self.progress_hub.settings_tab.set_remote_database_status(message, "#e74c3c")
                if not auto_triggered:
                    QMessageBox.warning(self.progress_hub, "Download Failed", message)

        self.remote_db_downloader.download_complete.connect(on_download_complete)
        self.remote_db_thread.started.connect(self.remote_db_downloader.download_database)
        self.remote_db_thread.finished.connect(self.remote_db_downloader.deleteLater)
        self.remote_db_thread.start()

    def check_for_app_updates(self, manual=False):
        if hasattr(self, 'app_update_thread') and self.app_update_thread:
            try:
                if self.app_update_thread.isRunning():
                     if manual:
                         QMessageBox.information(self.progress_hub, "Check in Progress", "An update check is already in progress.")
                     return
            except RuntimeError:
                self.app_update_thread = None

        self.app_update_thread = QThread()
        self.app_update_worker = AppUpdateChecker(APP_VERSION, APP_UPDATE_URL)
        self.app_update_worker.moveToThread(self.app_update_thread)
        self.app_update_thread.started.connect(self.app_update_worker.run_check)
        self.app_update_worker.update_available.connect(lambda v, u: QMessageBox.question(self.progress_hub, "Update", f"New version {v} available. Open site?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes and QDesktopServices.openUrl(QUrl(u)))
        self.app_update_worker.check_finished.connect(self.app_update_thread.quit)
        self.app_update_thread.finished.connect(self.app_update_thread.deleteLater)
        if manual: self.app_update_worker.check_finished.connect(lambda: QMessageBox.information(self.progress_hub, "Up to Date", f"Version {APP_VERSION} is the latest."))
        self.app_update_thread.start()


    def cleanup_threads(self):
            # Hotkey Worker
            if hasattr(self, 'hotkey_worker') and self.hotkey_worker:
                try:
                    self.hotkey_worker.stop()
                except RuntimeError: pass

            # Hotkey Thread
            if hasattr(self, 'hotkey_thread') and self.hotkey_thread:
                try:
                    self.hotkey_thread.quit()
                    self.hotkey_thread.wait()
                except RuntimeError: pass

            # Scan Thread (The one causing the error)
            if hasattr(self, 'scan_thread') and self.scan_thread:
                try:
                    if self.scan_thread.isRunning():
                        self.scan_thread.quit()
                        self.scan_thread.wait()
                except RuntimeError:
                    pass # Thread was already deleted, which is fine

            # Data Update Thread
            if hasattr(self, 'data_update_thread') and self.data_update_thread:
                try:
                    self.data_update_thread.quit()
                    self.data_update_thread.wait()
                except RuntimeError: pass

            # Progress Hub
            if hasattr(self, 'progress_hub'):
                try:
                    self.progress_hub.cleanup()
                except RuntimeError: pass

    def quit_app(self): self.app.quit()
    def run(self): sys.exit(self.app.exec())

    def restore_app(self):
        self.progress_hub.show()
        # First restore from minimized state if needed
        if self.progress_hub.windowState() & Qt.WindowState.WindowMinimized:
            self.progress_hub.setWindowState(self.progress_hub.windowState() & ~Qt.WindowState.WindowMinimized)
        # Force window to the foreground on Windows
        self.progress_hub.setWindowFlags(self.progress_hub.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.progress_hub.show()
        self.progress_hub.setWindowFlags(self.progress_hub.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.progress_hub.show()
        self.progress_hub.activateWindow()
        self.progress_hub.raise_()

from modules.ui_components import set_dark_title_bar, DarkTitleBarProxy

def main():
    def get_tesseract_path():
        if getattr(sys, 'frozen', False): return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'Tesseract-OCR', 'tesseract.exe')
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Tesseract-OCR', 'tesseract.exe')
        return local if os.path.exists(local) else None

    parser = argparse.ArgumentParser(); parser.add_argument('--tesseract', default=get_tesseract_path()); parser.add_argument('--once', action='store_true'); parser.add_argument('--debug', action='store_true')
    config = Config.from_args(parser.parse_args())

    try:
        myappid = f'joopzor.arccompanion.client.{APP_VERSION}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError: pass

    try:
        app_instance = QApplication(sys.argv)
        app_instance.setStyleSheet(Constants.DARK_THEME_QSS)

        # Apply dark title bars globally
        dark_proxy = DarkTitleBarProxy()
        app_instance.installEventFilter(dark_proxy)
        # Keep reference to prevent GC
        app_instance._dark_proxy = dark_proxy

        if os.path.exists(Constants.ICON_FILE): app_instance.setWindowIcon(QIcon(Constants.ICON_FILE))
        shared_memory = QSharedMemory("ArcCompanion_Unique_Instance_Lock")
        if not shared_memory.create(1): QMessageBox.warning(None, "Already Running", "Arc Companion is already running."); sys.exit(0)
        app = ArcCompanionApp(config); app.run()
    except Exception as e:
        with open(os.path.join(os.path.expanduser("~"), "Desktop", "arc_companion_crash.log"), "w") as f: f.write(f"Crash: {datetime.now()}\n{traceback.format_exc()}")
        if not QApplication.instance(): _ = QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error", f"Crashed.\n{e}"); sys.exit(1)

if __name__ == '__main__': main()