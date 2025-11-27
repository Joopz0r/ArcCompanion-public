from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QCheckBox, QSlider, QPushButton, 
                             QScrollArea, QMessageBox, QListWidget, QListWidgetItem, QAbstractItemView, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QKeySequence
import configparser
import os
from .constants import Constants
from .update_checker import UpdateChecker

# --- CUSTOM WIDGETS TO PREVENT ACCIDENTAL SCROLLING ---
class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        # Ignore the wheel event so it propagates to the parent ScrollArea
        event.ignore()

class NoScrollSlider(QSlider):
    def wheelEvent(self, event):
        # Ignore the wheel event so it propagates to the parent ScrollArea
        event.ignore()

class HotkeyButton(QPushButton):
    """
    A custom button that captures key presses and formats them as strings
    compatible with the 'keyboard' library (e.g., 'ctrl+alt+e').
    """
    key_set = pyqtSignal(str)

    def __init__(self, default_text=""):
        super().__init__(default_text)
        self.setCheckable(True)
        self.current_key_string = default_text
        self.setText(default_text if default_text else "Click to set...")
        
        self.normal_style = """
            QPushButton {
                background-color: #232834;
                color: #E0E6ED;
                border: 1px solid #3E4451;
                padding: 4px;
                text-align: left;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #4B5363; }
        """
        self.recording_style = """
            QPushButton {
                background-color: #722f37; 
                color: #ffffff;
                border: 1px solid #ff4444;
                padding: 4px;
                text-align: center;
                border-radius: 4px;
                font-size: 12px;
            }
        """
        self.setStyleSheet(self.normal_style)
        self.clicked.connect(self._on_click)

    def _on_click(self):
        self.setText("Press keys... (Esc to cancel)")
        self.setStyleSheet(self.recording_style)

    def keyPressEvent(self, event):
        if not self.isChecked():
            super().keyPressEvent(event)
            return

        key = event.key()
        
        if key == Qt.Key.Key_Escape:
            self.setChecked(False)
            self.setText(self.current_key_string if self.current_key_string else "Click to set...")
            self.setStyleSheet(self.normal_style)
            return

        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.current_key_string = ""
            self.setText("None")
            self.setChecked(False)
            self.setStyleSheet(self.normal_style)
            return

        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        parts = []
        modifiers = event.modifiers()
        
        if modifiers & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:     parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:   parts.append("shift")

        key_text = QKeySequence(key).toString().lower()
        parts.append(key_text)

        final_string = "+".join(parts)
        
        self.current_key_string = final_string
        self.setText(final_string)
        self.setChecked(False) 
        self.setStyleSheet(self.normal_style)
        self.key_set.emit(final_string)

    def focusOutEvent(self, event):
        if self.isChecked():
            self.setChecked(False)
            self.setText(self.current_key_string if self.current_key_string else "Click to set...")
            self.setStyleSheet(self.normal_style)
        super().focusOutEvent(event)
    
    def set_hotkey(self, text):
        self.current_key_string = text
        self.setText(text if text else "Click to set...")


class SettingsWindow(QWidget):
    start_download = pyqtSignal(list)
    start_language_download = pyqtSignal(str)

    SECTIONS = {
        'price': ('Price', 'show_price'),
        'trader': ('Trader Info', 'show_trader_info'),
        'notes': ('User Notes', 'show_notes'),
        'crafting': ('Crafting Info', 'show_crafting_info'),
        'hideout': ('Hideout Reqs', 'show_hideout_reqs'),
        'project': ('Project Reqs', 'show_project_reqs'),
        'recycle': ('Recycles Into', 'show_recycles_into'),
        'salvage': ('Salvages Into', 'show_salvages_into')
    }
    
    DEFAULT_ORDER = ['price', 'trader', 'notes', 'crafting', 'hideout', 'project', 'recycle', 'salvage']

    def __init__(self, on_save_callback=None):
        super().__init__()
        self.on_save_callback = on_save_callback
        
        # Apply Global Theme + Specific Overrides
        compact_style = Constants.DARK_THEME_QSS + """
            QWidget { font-size: 13px; }
            QLabel[objectName="Header"] {
                font-size: 15px; margin-top: 5px; padding-bottom: 2px;
            }
            QCheckBox { spacing: 4px; }
            QCheckBox::indicator:checked, QListView::indicator:checked {
                background-color: #98C379; border: 1px solid #98C379; border-radius: 2px; image: url(none); 
            }
            QCheckBox::indicator:unchecked, QListView::indicator:unchecked {
                background-color: #2C313C; border: 1px solid #3E4451; border-radius: 2px;
            }
        """
        self.setStyleSheet(compact_style)
        
        self.config = configparser.ConfigParser()
        
        self.start_hotkey_price = ""
        self.start_hotkey_quest = ""
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scroll_content")
        
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(6) 
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        # --- General Settings ---
        self.add_header("General Settings")
        # Use NoScrollComboBox to prevent accidental scrolling changes
        self.lang_combo = NoScrollComboBox()
        self.lang_combo.addItems(sorted(list(Constants.LANGUAGES.keys())))
        self.add_labeled_widget("Game Language:", self.lang_combo)

        # --- Update Section (MOVED HERE) ---
        self.add_header("Data Updates")
        update_layout = QHBoxLayout()
        self.update_status_label = QLabel("Ready to check for updates.")
        self.check_update_button = QPushButton("Check for Updates")
        self.check_update_button.setFixedHeight(28) 
        self.check_update_button.clicked.connect(self._on_check_button_clicked)
        update_layout.addWidget(self.update_status_label, 1)
        update_layout.addWidget(self.check_update_button)
        self.scroll_layout.addLayout(update_layout)

        # --- Hotkeys ---
        self.add_header("Hotkeys")
        self.hotkey_btn = self.add_hotkey_selector("Item Info Hotkey:")
        self.quest_hotkey_btn = self.add_hotkey_selector("Quest Log Hotkey:")

        # --- Item Overlay ---
        self.add_header("Item Overlay Settings")
        self.item_font_size = self.add_slider("Font Size:", 8, 24, 12, "pt")
        self.item_duration = self.add_slider("Duration:", 1, 10, 3, "s", float_scale=True)
        
        lbl_hint = QLabel("Drag items to reorder. Uncheck to hide.")
        lbl_hint.setStyleSheet("color: #ABB2BF; font-style: italic; font-size: 11px;")
        self.scroll_layout.addWidget(lbl_hint)

        self.overlay_order_list = QListWidget()
        self.overlay_order_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.overlay_order_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.overlay_order_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.overlay_order_list.setStyleSheet("""
            QListWidget { background-color: #232834; border: 1px solid #3E4451; border-radius: 4px; padding: 5px; }
            QListWidget::item { padding: 5px; background-color: #2C313C; border-bottom: 1px solid #3E4451; color: #E0E6ED; }
            QListWidget::item:selected { background-color: #3E4451; }
            QListWidget::item:hover { background-color: #323842; }
        """)
        self.overlay_order_list.setFixedHeight(260) 
        self.scroll_layout.addWidget(self.overlay_order_list)

        self.chk_future_hideout = self.add_checkbox("Show Future Hideout Reqs (Modifier)")
        self.chk_future_project = self.add_checkbox("Show Future Project Reqs (Modifier)")

        # --- Quest Overlay ---
        self.add_header("Quest Overlay Settings")
        self.quest_font_size = self.add_slider("Font Size:", 8, 24, 12, "pt")
        self.quest_width = self.add_slider("Width:", 200, 600, 350, "px")
        self.quest_opacity = self.add_slider("Opacity:", 30, 100, 95, "%")
        self.quest_duration = self.add_slider("Duration:", 1, 20, 5, "s", float_scale=True)

        self.scroll_layout.addStretch()

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedHeight(30)
        save_btn.setObjectName("action_button_green")
        save_btn.clicked.connect(self.save_settings)
        
        # Changed "Cancel" to "Revert" since it's a tab now
        revert_btn = QPushButton("Revert")
        revert_btn.setFixedHeight(30)
        revert_btn.setObjectName("action_button_red") 
        revert_btn.clicked.connect(self.load_settings)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(revert_btn)
        layout.addLayout(btn_layout)

        self.load_settings()
        self._setup_updater_thread()

    def _setup_updater_thread(self):
        self.update_thread = QThread()
        self.update_worker = UpdateChecker()
        self.update_worker.moveToThread(self.update_thread)

        self.start_download.connect(self.update_worker.download_updates)
        self.start_language_download.connect(self.update_worker.download_language)

        self.update_worker.checking_for_updates.connect(self._on_checking_updates)
        self.update_worker.update_check_finished.connect(self._on_check_finished)
        self.update_worker.download_progress.connect(self._on_download_progress)
        self.update_worker.update_complete.connect(self._on_update_complete)

        self.update_thread.finished.connect(self.update_worker.deleteLater)
        self.update_thread.start()

    def _on_check_button_clicked(self):
        self.update_worker.run_check()

    def _on_checking_updates(self):
        self.update_status_label.setText("Checking for updates...")
        self.check_update_button.setEnabled(False)

    def _on_check_finished(self, files_to_download, message):
        self.update_status_label.setText(message)
        self.check_update_button.setEnabled(True)

        if files_to_download:
            msg = QMessageBox()
            msg.setWindowTitle("Update Available")
            msg.setText(f"{message}\n\nDo you want to download and apply the updates?\n(Your progress will not be affected.)")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                self.check_update_button.setEnabled(False)
                self.start_download.emit(files_to_download)

    def _on_download_progress(self, current, total, filename):
        self.update_status_label.setText(f"Downloading {filename} ({current}/{total})...")

    def _on_update_complete(self, success, message):
        self.update_status_label.setText(message)
        self.check_update_button.setEnabled(True)
        
        icon = QMessageBox.Icon.Information if success else QMessageBox.Icon.Warning
        msg = QMessageBox()
        msg.setWindowTitle("Update Complete" if success else "Update Error")
        msg.setText(message)
        msg.setIcon(icon)
        msg.exec()

    def cleanup(self):
        if self.update_thread.isRunning():
            self.update_thread.quit()
            self.update_thread.wait()

    def add_header(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("Header") 
        self.scroll_layout.addWidget(lbl)
    
    def add_labeled_widget(self, label_text, widget):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #E0E6ED;")
        row.addWidget(lbl)
        row.addWidget(widget)
        self.scroll_layout.addLayout(row)

    def add_hotkey_selector(self, label_text):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #E0E6ED;")
        row.addWidget(lbl)
        btn = HotkeyButton()
        row.addWidget(btn)
        self.scroll_layout.addLayout(row)
        return btn

    def add_checkbox(self, text):
        chk = QCheckBox(text)
        self.scroll_layout.addWidget(chk)
        return chk

    def add_slider(self, label, min_v, max_v, default, suffix, float_scale=False):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #E0E6ED;")
        row.addWidget(lbl)
        
        val_lbl = QLabel(f"{default}{suffix}")
        val_lbl.setFixedWidth(50)
        val_lbl.setStyleSheet("color: #E0E6ED;")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Use NoScrollSlider to prevent accidental scrolling changes
        slider = NoScrollSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v if not float_scale else int(min_v*10), max_v if not float_scale else int(max_v*10))
        slider.setValue(default if not float_scale else int(default*10))
        
        def update_lbl(v):
            display_val = v/10.0 if float_scale else v
            val_lbl.setText(f"{display_val:.1f}{suffix}" if float_scale else f"{display_val}{suffix}")
            
        slider.valueChanged.connect(update_lbl)
        update_lbl(slider.value())
        
        row.addWidget(slider)
        row.addWidget(val_lbl)
        self.scroll_layout.addLayout(row)
        return slider

    def load_settings(self):
        self.config.read(Constants.CONFIG_FILE)
        
        hk_price = self.config.get('Hotkeys', 'price_check', fallback="ctrl+f")
        hk_quest = self.config.get('Hotkeys', 'quest_log', fallback="ctrl+e")
        
        self.hotkey_btn.set_hotkey(hk_price)
        self.quest_hotkey_btn.set_hotkey(hk_quest)
        
        lang_code = self.config.get('General', 'language', fallback='eng')
        found = False
        for name, (json_code, tess_code) in Constants.LANGUAGES.items():
            if tess_code == lang_code or json_code == lang_code:
                self.lang_combo.setCurrentText(name)
                found = True
                break
        if not found: self.lang_combo.setCurrentText("English")

        saved_order_str = self.config.get('ItemOverlay', 'section_order', fallback="")
        if saved_order_str:
            saved_order = [x.strip() for x in saved_order_str.split(',') if x.strip() in self.SECTIONS]
            for key in self.DEFAULT_ORDER:
                if key not in saved_order: saved_order.append(key)
        else:
            saved_order = self.DEFAULT_ORDER

        self.overlay_order_list.clear()
        for key in saved_order:
            display_name, config_key = self.SECTIONS[key]
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            is_checked = self.config.getboolean('ItemOverlay', config_key, fallback=True)
            item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            self.overlay_order_list.addItem(item)

        self.chk_future_hideout.setChecked(self.config.getboolean('ItemOverlay', 'show_all_future_reqs', fallback=False))
        self.chk_future_project.setChecked(self.config.getboolean('ItemOverlay', 'show_all_future_project_reqs', fallback=False))
        
        if not self.config.has_section('QuestOverlay'): self.config.add_section('QuestOverlay')
        self.quest_font_size.setValue(self.config.getint('QuestOverlay', 'font_size', fallback=12))
        self.quest_width.setValue(self.config.getint('QuestOverlay', 'width', fallback=350))
        self.quest_opacity.setValue(self.config.getint('QuestOverlay', 'opacity', fallback=95))
        self.quest_duration.setValue(int(self.config.getfloat('QuestOverlay', 'duration_seconds', fallback=5.0) * 10))
        self.item_font_size.setValue(self.config.getint('ItemOverlay', 'font_size', fallback=12))
        self.item_duration.setValue(int(self.config.getfloat('ItemOverlay', 'duration_seconds', fallback=3.0) * 10))

    def save_settings(self):
        if not self.config.has_section('Hotkeys'): self.config.add_section('Hotkeys')
        
        new_price_hk = self.hotkey_btn.current_key_string
        new_quest_hk = self.quest_hotkey_btn.current_key_string
        
        self.config.set('Hotkeys', 'price_check', new_price_hk)
        self.config.set('Hotkeys', 'quest_log', new_quest_hk)
        
        if not self.config.has_section('General'): self.config.add_section('General')
        display_name = self.lang_combo.currentText()
        if display_name in Constants.LANGUAGES:
            lang_code = Constants.LANGUAGES[display_name][1]
            self.config.set('General', 'language', lang_code)
            
            if lang_code != 'eng': 
                 target = os.path.join(Constants.TESSDATA_DIR, f"{lang_code}.traineddata")
                 if not os.path.exists(target):
                     QMessageBox.information(self, "Downloading Language", f"Downloading language data for {display_name}...\nThis may take a few seconds.")
                     self.start_language_download.emit(lang_code)

        if not self.config.has_section('ItemOverlay'): self.config.add_section('ItemOverlay')
        self.config.set('ItemOverlay', 'font_size', str(self.item_font_size.value()))
        self.config.set('ItemOverlay', 'duration_seconds', str(self.item_duration.value()/10.0))
        
        new_order = []
        for i in range(self.overlay_order_list.count()):
            item = self.overlay_order_list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            new_order.append(key)
            _, config_key = self.SECTIONS[key]
            is_checked = (item.checkState() == Qt.CheckState.Checked)
            self.config.set('ItemOverlay', config_key, str(is_checked))
            
        self.config.set('ItemOverlay', 'section_order', ",".join(new_order))

        self.config.set('ItemOverlay', 'show_all_future_reqs', str(self.chk_future_hideout.isChecked()))
        self.config.set('ItemOverlay', 'show_all_future_project_reqs', str(self.chk_future_project.isChecked()))
        
        if not self.config.has_section('QuestOverlay'): self.config.add_section('QuestOverlay')
        self.config.set('QuestOverlay', 'font_size', str(self.quest_font_size.value()))
        self.config.set('QuestOverlay', 'width', str(self.quest_width.value()))
        self.config.set('QuestOverlay', 'opacity', str(self.quest_opacity.value()))
        self.config.set('QuestOverlay', 'duration_seconds', str(self.quest_duration.value()/10.0))
        
        with open(Constants.CONFIG_FILE, 'w') as f:
            self.config.write(f)
            
        if new_price_hk != self.start_hotkey_price or new_quest_hk != self.start_hotkey_quest:
            QMessageBox.information(self, "Restart Required", "You have modified keybindings.\nPlease restart the application for the new hotkeys to take effect.")

        if self.on_save_callback:
            self.on_save_callback()
        
        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")