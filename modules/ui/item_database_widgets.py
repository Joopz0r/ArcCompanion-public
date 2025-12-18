from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QSizePolicy,
    QGraphicsOpacityEffect, QTextEdit, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PyQt6.QtGui import QPixmap, QColor
import os
import requests
from modules.core.constants import Constants
from .ui_components import StashProgressBar

# =============================================================================
# IMAGE LOADER (Unchanged)
# =============================================================================
class ImageDownloadWorker(QThread):
    download_complete = pyqtSignal(bool, str) 
    def __init__(self, url, save_path, parent=None):
        super().__init__(parent); self.url = url; self.save_path = save_path
    def run(self):
        try:
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            response = requests.get(self.url, timeout=10, stream=True)
            if response.status_code == 200:
                with open(self.save_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        if self.isInterruptionRequested(): f.close(); return
                        f.write(chunk)
                self.download_complete.emit(True, self.save_path)
            else: self.download_complete.emit(False, self.save_path)
        except Exception: self.download_complete.emit(False, self.save_path)

class ItemImageLoader(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_cache = {}
        self.active_downloads = {}
        self.pending_labels = {} 
    def load_image(self, item, label, size=64):
        item_id = item.get('id'); img_url = item.get('imageFilename')
        filename = img_url.split('/')[-1] if img_url else f"{item_id}.png"
        path = os.path.join(Constants.DATA_DIR, "images", "items", filename)
        if path in self.image_cache: self._set_pixmap(label, self.image_cache[path], size)
        elif os.path.exists(path):
            pix = QPixmap(path); self.image_cache[path] = pix; self._set_pixmap(label, pix, size)
        elif img_url and img_url.startswith("http"):
            label.setText("..."); self._start_download(img_url, path, label, size)
        else: label.setText("?")
    def _set_pixmap(self, label, pixmap, size):
        label.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    def _start_download(self, url, path, label, size):
        if path not in self.pending_labels: self.pending_labels[path] = []
        self.pending_labels[path].append((label, size))
        if path in self.active_downloads: return
        worker = ImageDownloadWorker(url, path, self)
        worker.download_complete.connect(self._on_download_complete)
        self.active_downloads[path] = worker; worker.start()
    def _on_download_complete(self, success, path):
        if path in self.active_downloads: del self.active_downloads[path]
        waiting = self.pending_labels.pop(path, [])
        if success and os.path.exists(path):
            pix = QPixmap(path); self.image_cache[path] = pix
            for label, size in waiting:
                try: self._set_pixmap(label, pix, size)
                except RuntimeError: pass 
        else:
            for label, _ in waiting:
                try: label.setText("x")
                except RuntimeError: pass
    def cleanup(self):
        for w in self.active_downloads.values(): w.requestInterruption(); w.quit(); w.wait(50)
        self.active_downloads.clear()


# =============================================================================
# NOTES DIALOG
# =============================================================================
class NotesDialog(QDialog):
    """Dialog for editing item notes."""
    notes_saved = pyqtSignal(str, str)  # item_id, notes
    
    def __init__(self, item_id, item_name, current_notes="", parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.setWindowTitle(f"Notes - {item_name}")
        self.setMinimumSize(400, 250)
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1F2B;
            }
            QLabel {
                color: #E0E6ED;
                font-size: 14px;
            }
            QTextEdit {
                background-color: #232834;
                color: #E0E6ED;
                border: 1px solid #3E4451;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border-color: #4476ED;
            }
            QPushButton {
                background-color: #3E4451;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4B5363;
            }
            QPushButton#save_btn {
                background-color: #22C55E;
            }
            QPushButton#save_btn:hover {
                background-color: #16A34A;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Text area
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Add your notes here...")
        self.text_edit.setText(current_notes)
        layout.addWidget(self.text_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Notes")
        save_btn.setObjectName("save_btn")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _save(self):
        self.notes_saved.emit(self.item_id, self.text_edit.toPlainText())
        self.accept()


# =============================================================================
# COMPACT LIST ROW
# =============================================================================
class ItemListRow(QFrame):
    """Compact row for the item list - 75px height, click to expand."""
    clicked = pyqtSignal(dict)

    def __init__(self, item, localized_name, image_loader, stash_count=0, stack_size=1, 
                 is_collected=False, req_details=None, is_tracked=False, is_expanded=False):
        super().__init__()
        self.item = item
        self.is_expanded = is_expanded
        self.is_tracked = is_tracked
        self.stash_count = stash_count
        self.stack_size = max(1, stack_size)
        self.req_details = req_details or {}
        
        self.setFixedHeight(75)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.rarity = item.get('rarity', 'Common')
        self.rarity_color = Constants.RARITY_COLORS.get(self.rarity, "#777")
        self.is_bp = (item.get('type') == "Blueprint") or ("Blueprint" in item.get('name', ''))
        
        self._init_ui(localized_name, image_loader, is_collected)
        self._update_style()

    def _init_ui(self, localized_name, image_loader, is_collected):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        
        # 1. Icon (52x52)
        self.img_lbl = QLabel()
        self.img_lbl.setFixedSize(52, 52)
        self.img_lbl.setStyleSheet(f"""
            border: 2px solid {self.rarity_color}; 
            border-radius: 8px; 
            background-color: #0D1117;
        """)
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_loader.load_image(self.item, self.img_lbl, size=48)
        layout.addWidget(self.img_lbl)
        
        # 2. Name & Type Section
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        
        # Name with tracked indicator
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        
        self.name_lbl = QLabel(localized_name)
        self.name_lbl.setStyleSheet(f"""
            color: {self.rarity_color}; 
            font-size: 16px; 
            font-weight: bold;
        """)
        name_row.addWidget(self.name_lbl)
        
        if self.is_tracked:
            track_icon = QLabel("★")
            track_icon.setStyleSheet("color: #FFD700; font-size: 16px;")
            name_row.addWidget(track_icon)
        
        name_row.addStretch()
        info_layout.addLayout(name_row)
        
        # Type and rarity
        type_txt = f"{self.item.get('type', 'Item')} • {self.rarity}"
        self.type_lbl = QLabel(type_txt)
        self.type_lbl.setStyleSheet("color: #6B7280; font-size: 13px;")
        info_layout.addWidget(self.type_lbl)
        
        layout.addWidget(info_widget, 3)  # Stretch 3
        
        # 3. Requirement Badges (Minimal - just colored dots/icons)
        badges_widget = QWidget()
        badges_layout = QHBoxLayout(badges_widget)
        badges_layout.setContentsMargins(0, 0, 0, 0)
        badges_layout.setSpacing(10)
        badges_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        badge_configs = [
            ('quest', '🎯', '#22C55E', 'Quest'),
            ('hideout', '🏠', '#3B82F6', 'Hideout'),
            ('project', '📋', '#F59E0B', 'Project')
        ]
        
        for key, icon, color, tooltip in badge_configs:
            items = self.req_details.get(key, [])
            if items:
                badge = QLabel(icon)
                badge.setToolTip(f"{tooltip}: {', '.join(items[:3])}{'...' if len(items) > 3 else ''}")
                badge.setStyleSheet(f"color: {color}; font-size: 16px;")
                badges_layout.addWidget(badge)
        
        layout.addWidget(badges_widget, 1)  # Stretch 1
        
        # 4. Stash Status
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(12)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        if not self.is_bp:
            # Progress bar
            self.progress_bar = StashProgressBar(font_size=1)
            self.progress_bar.setFixedSize(80, 10)
            self.progress_bar.update_status(self.stash_count, self.stack_size)
            status_layout.addWidget(self.progress_bar)
            
            # Count
            self.count_lbl = QLabel(f"{self.stash_count}/{self.stack_size}")
            self.count_lbl.setStyleSheet("color: #9CA3AF; font-size: 14px; font-weight: bold;")
            status_layout.addWidget(self.count_lbl)
        else:
            # Blueprint status
            if is_collected:
                status_lbl = QLabel("✓")
                status_lbl.setToolTip("Learned")
                status_lbl.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 18px;")
            else:
                status_lbl = QLabel("○")
                status_lbl.setToolTip("Not Learned")
                status_lbl.setStyleSheet("color: #4B5563; font-size: 18px;")
            status_layout.addWidget(status_lbl)
        
        layout.addWidget(status_widget, 1)  # Stretch 1
        
        # 5. Expand Indicator
        self.expand_indicator = QLabel("▶")
        self.expand_indicator.setStyleSheet("color: #4B5563; font-size: 14px;")
        layout.addWidget(self.expand_indicator)

    def set_expanded(self, expanded):
        self.is_expanded = expanded
        self.expand_indicator.setText("▼" if expanded else "▶")
        self._update_style()

    def update_stash_display(self, new_count):
        self.stash_count = new_count
        if hasattr(self, 'progress_bar'):
            self.progress_bar.update_status(new_count, self.stack_size)
        if hasattr(self, 'count_lbl'):
            self.count_lbl.setText(f"{new_count}/{self.stack_size}")

    def _update_style(self):
        if self.is_expanded:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #1F2937;
                    border: 1px solid {self.rarity_color}66;
                    border-bottom: none;
                    border-top-left-radius: 10px;
                    border-top-right-radius: 10px;
                    border-bottom-left-radius: 0px;
                    border-bottom-right-radius: 0px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1B1F27;
                    border: 1px solid #2D333B;
                    border-radius: 10px;
                }
                QFrame:hover {
                    background-color: #222730;
                    border-color: #3E4451;
                }
                QLabel {
                    border: none;
                    background: transparent;
                }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)


# =============================================================================
# DETAIL PANEL (Expandable Section)
# =============================================================================
class ItemDetailPanel(QFrame):
    """Expanded detail panel with stash controls and requirements."""
    stash_changed = pyqtSignal(str, int)  # item_id, new_count
    track_toggled = pyqtSignal(str)  # item_id
    notes_requested = pyqtSignal(str)  # item_id

    def __init__(self, item, stash_count, stack_size, req_details, is_tracked=False, is_bp=False, is_collected=False, has_notes=False):
        super().__init__()
        self.item = item
        self.item_id = item.get('id')
        self.stash_count = stash_count
        self.stack_size = max(1, stack_size)
        self.is_tracked = is_tracked
        self.is_bp = is_bp
        self.has_notes = has_notes
        self.req_details = req_details or {}
        
        self.rarity_color = Constants.RARITY_COLORS.get(item.get('rarity', 'Common'), "#777")
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #161A21;
                border: 1px solid {self.rarity_color}66;
                border-top: none;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        
        self._init_ui(is_collected)

    def _init_ui(self, is_collected):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)
        
        # === Row 1: Stash Controls (left) + Action Buttons (right, stacked) ===
        controls_row = QHBoxLayout()
        controls_row.setSpacing(12)
        
        if not self.is_bp:
            # Stash controls
            stash_label = QLabel("STASH")
            stash_label.setStyleSheet("color: #6B7280; font-size: 12px; font-weight: bold;")
            controls_row.addWidget(stash_label)
            
            controls_row.addSpacing(15)
            
            # -10 button
            self.btn_m10 = self._create_control_btn("-10", width=50)
            self.btn_m10.clicked.connect(lambda: self._change_stash(-10))
            controls_row.addWidget(self.btn_m10)
            
            controls_row.addSpacing(8)
            
            # -1 button
            self.btn_m1 = self._create_control_btn("-1", width=44)
            self.btn_m1.clicked.connect(lambda: self._change_stash(-1))
            controls_row.addWidget(self.btn_m1)
            
            controls_row.addSpacing(12)
            
            # Progress bar
            self.stash_bar = StashProgressBar(font_size=11)
            self.stash_bar.setFixedSize(140, 30)
            self.stash_bar.update_status(self.stash_count, self.stack_size)
            controls_row.addWidget(self.stash_bar)
            
            controls_row.addSpacing(12)
            
            # +1 button
            self.btn_p1 = self._create_control_btn("+1", width=44)
            self.btn_p1.clicked.connect(lambda: self._change_stash(1))
            controls_row.addWidget(self.btn_p1)
            
            controls_row.addSpacing(8)
            
            # +10 button
            self.btn_p10 = self._create_control_btn("+10", width=50)
            self.btn_p10.clicked.connect(lambda: self._change_stash(10))
            controls_row.addWidget(self.btn_p10)
        else:
            # Blueprint status
            bp_status = QLabel("✓ LEARNED" if is_collected else "○ NOT LEARNED")
            color = "#22C55E" if is_collected else "#6B7280"
            bp_status.setStyleSheet(f"""
                color: {color}; 
                font-weight: bold; 
                font-size: 14px;
                padding: 8px 16px;
                border: 1px solid {color} !important;
                border-radius: 6px;
                background-color: {color}15;
            """)
            controls_row.addWidget(bp_status)
        
        controls_row.addStretch()
        
        # Action buttons (stacked vertically on right)
        actions_widget = QWidget()
        actions_layout = QVBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        
        # Track button (top)
        self.track_btn = QPushButton("★ TRACKED" if self.is_tracked else "☆ TRACK")
        self.track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.track_btn.setFixedSize(110, 32)
        self._update_track_btn_style()
        self.track_btn.clicked.connect(self._toggle_track)
        actions_layout.addWidget(self.track_btn)
        
        # Notes button (bottom)
        self.notes_btn = QPushButton("📝 Notes" if not self.has_notes else "📝 Notes ●")
        self.notes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notes_btn.setFixedSize(110, 32)
        self.notes_btn.setStyleSheet("""
            QPushButton {
                background-color: #232834;
                color: #9CA3AF;
                border: 1px solid #3E4451;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #E0E6ED;
                border-color: #4476ED;
            }
        """)
        self.notes_btn.clicked.connect(lambda: self.notes_requested.emit(self.item_id))
        actions_layout.addWidget(self.notes_btn)
        
        controls_row.addWidget(actions_widget)
        
        layout.addLayout(controls_row)
        
        # === Row 2: Item Stats ===
        stats_row = QHBoxLayout()
        stats_row.setSpacing(30)
        
        # Value
        value = self.item.get('value', 0)
        value_widget = self._create_stat_widget("💰", f"{value:,}", "#E5C07B")
        stats_row.addWidget(value_widget)
        
        # Weight
        weight = self.item.get('weightKg', 0)
        weight_widget = self._create_stat_widget("⚖", f"{weight}kg", "#9CA3AF")
        stats_row.addWidget(weight_widget)
        
        # Stack size
        stack_widget = self._create_stat_widget("📦", str(self.stack_size), "#9CA3AF")
        stats_row.addWidget(stack_widget)
        
        # Item ID (subtle)
        id_lbl = QLabel(f"ID: {self.item_id}")
        id_lbl.setStyleSheet("color: #374151; font-size: 12px;")
        stats_row.addWidget(id_lbl)
        
        stats_row.addStretch()
        layout.addLayout(stats_row)
        
        # === Row 3: Requirements ===
        has_reqs = any(self.req_details.get(k) for k in ['quest', 'hideout', 'project'])
        
        if has_reqs:
            # Divider
            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setStyleSheet("background-color: #2D333B; border: none;")
            divider.setFixedHeight(1)
            layout.addWidget(divider)
            
            req_header = QLabel("NEEDED FOR")
            req_header.setStyleSheet("color: #6B7280; font-size: 12px; font-weight: bold;")
            layout.addWidget(req_header)
            
            req_layout = QVBoxLayout()
            req_layout.setSpacing(8)
            
            req_configs = [
                ('quest', '🎯 Quests:', '#22C55E'),
                ('hideout', '🏠 Hideout:', '#3B82F6'),
                ('project', '📋 Projects:', '#F59E0B')
            ]
            
            for key, label, color in req_configs:
                items = self.req_details.get(key, [])
                if items:
                    row = QHBoxLayout()
                    row.setSpacing(12)
                    
                    type_lbl = QLabel(label)
                    type_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
                    type_lbl.setFixedWidth(100)
                    row.addWidget(type_lbl)
                    
                    items_text = ", ".join(items[:4])
                    if len(items) > 4:
                        items_text += f" +{len(items) - 4} more"
                    
                    items_lbl = QLabel(items_text)
                    items_lbl.setStyleSheet("color: #9CA3AF; font-size: 13px;")
                    items_lbl.setWordWrap(True)
                    row.addWidget(items_lbl, 1)
                    
                    req_layout.addLayout(row)
            
            layout.addLayout(req_layout)

    def _create_control_btn(self, text, width=44):
        btn = QPushButton(text)
        btn.setFixedSize(width, 34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #232834;
                color: #E0E6ED;
                border: 1px solid #3E4451;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4476ED;
                border-color: #4476ED;
            }
            QPushButton:pressed {
                background-color: #3B65C9;
            }
        """)
        return btn

    def _create_stat_widget(self, icon, value, color):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 15px;")
        layout.addWidget(icon_lbl)
        
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
        layout.addWidget(value_lbl)
        
        return widget

    def _change_stash(self, delta):
        new_count = max(0, self.stash_count + delta)
        if new_count != self.stash_count:
            self.stash_count = new_count
            self.stash_bar.update_status(new_count, self.stack_size)
            self.stash_changed.emit(self.item_id, new_count)

    def _toggle_track(self):
        self.is_tracked = not self.is_tracked
        self.track_btn.setText("★ TRACKED" if self.is_tracked else "☆ TRACK")
        self._update_track_btn_style()
        self.track_toggled.emit(self.item_id)

    def _update_track_btn_style(self):
        if self.is_tracked:
            self.track_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 215, 0, 0.15);
                    color: #FFD700;
                    border: 1px solid #FFD700;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 215, 0, 0.25);
                }
            """)
        else:
            self.track_btn.setStyleSheet("""
                QPushButton {
                    background-color: #232834;
                    color: #6B7280;
                    border: 1px solid #3E4451;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    color: #FFD700;
                    border-color: #FFD700;
                }
            """)

    def update_stash(self, new_count):
        self.stash_count = new_count
        if hasattr(self, 'stash_bar'):
            self.stash_bar.update_status(new_count, self.stack_size)

    def update_notes_indicator(self, has_notes):
        self.has_notes = has_notes
        self.notes_btn.setText("📝 Notes ●" if has_notes else "📝 Notes")


# =============================================================================
# EXPANDABLE ITEM ROW (Container)
# =============================================================================
class ExpandableItemRow(QFrame):
    """Container that holds ItemListRow + ItemDetailPanel with expand/collapse."""
    item_clicked = pyqtSignal(dict)  # Emitted when row header is clicked
    stash_changed = pyqtSignal(str, int)  # item_id, new_count
    track_toggled = pyqtSignal(str)  # item_id
    notes_requested = pyqtSignal(str)  # item_id

    def __init__(self, item, localized_name, image_loader, stash_count=0, stack_size=1, 
                 is_collected=False, req_details=None, is_tracked=False, has_notes=False):
        super().__init__()
        self.item = item
        self.is_expanded = False
        self.localized_name = localized_name
        self.image_loader = image_loader
        self.stash_count = stash_count
        self.stack_size = max(1, stack_size)
        self.is_collected = is_collected
        self.req_details = req_details or {}
        self.is_tracked = is_tracked
        self.has_notes = has_notes
        self.is_bp = (item.get('type') == "Blueprint") or ("Blueprint" in item.get('name', ''))
        
        self.setStyleSheet("background: transparent; border: none;")
        
        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(0)
        
        # Header row (always visible)
        self.header_row = ItemListRow(
            self.item, self.localized_name, self.image_loader,
            stash_count=self.stash_count, stack_size=self.stack_size,
            is_collected=self.is_collected, req_details=self.req_details,
            is_tracked=self.is_tracked, is_expanded=False
        )
        self.header_row.clicked.connect(self._on_header_clicked)
        self.main_layout.addWidget(self.header_row)
        
        # Detail panel (initially hidden)
        self.detail_panel = ItemDetailPanel(
            self.item, self.stash_count, self.stack_size,
            self.req_details, is_tracked=self.is_tracked,
            is_bp=self.is_bp, is_collected=self.is_collected,
            has_notes=self.has_notes
        )
        self.detail_panel.stash_changed.connect(self._on_stash_changed)
        self.detail_panel.track_toggled.connect(self._on_track_toggled)
        self.detail_panel.notes_requested.connect(self._on_notes_requested)
        self.detail_panel.hide()
        self.main_layout.addWidget(self.detail_panel)

    def _on_header_clicked(self, item):
        self.item_clicked.emit(item)

    def _on_stash_changed(self, item_id, new_count):
        self.stash_count = new_count
        self.header_row.update_stash_display(new_count)
        self.stash_changed.emit(item_id, new_count)

    def _on_track_toggled(self, item_id):
        self.is_tracked = not self.is_tracked
        self.track_toggled.emit(item_id)

    def _on_notes_requested(self, item_id):
        self.notes_requested.emit(item_id)

    def set_expanded(self, expanded):
        if self.is_expanded == expanded:
            return
            
        self.is_expanded = expanded
        self.header_row.set_expanded(expanded)
        
        if expanded:
            self.detail_panel.show()
        else:
            self.detail_panel.hide()

    def update_stash(self, new_count):
        self.stash_count = new_count
        self.header_row.update_stash_display(new_count)
        self.detail_panel.update_stash(new_count)

    def update_notes_indicator(self, has_notes):
        self.has_notes = has_notes
        self.detail_panel.update_notes_indicator(has_notes)
