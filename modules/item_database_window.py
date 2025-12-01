from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QScrollArea, QGridLayout, QLabel, QComboBox, QFrame, QSizePolicy,
    QToolTip, QGraphicsDropShadowEffect, QDialog, QTextEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QObject, QEvent, QPoint, QThread, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QColor, QCursor, QFont
import os
import requests
from .constants import Constants

# --- FUZZY SEARCH IMPORTS ---
try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    # Fallback if library is missing
    import difflib
    _HAS_RAPIDFUZZ = False

class InstantTooltipFilter(QObject):
    """
    Event filter to bypass the default Qt tooltip delay and show it immediately
    upon hovering.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            text = obj.toolTip()
            if text:
                QToolTip.showText(QCursor.pos(), text, obj)
        elif event.type() == QEvent.Type.Leave:
            QToolTip.hideText()
        elif event.type() == QEvent.Type.MouseButtonPress:
            QToolTip.hideText()
            
        return super().eventFilter(obj, event)

class NoteEditorDialog(QDialog):
    """Custom dialog for editing item notes with more space."""
    def __init__(self, item_name, current_note, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Notes: {item_name}")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        
        self.setStyleSheet("""
            QDialog { background-color: #1A1F2B; color: #E0E6ED; }
            QLabel { color: #E0E6ED; font-size: 14px; font-weight: bold; }
            QTextEdit { 
                background-color: #232834; 
                color: white; 
                border: 1px solid #3E4451; 
                border-radius: 4px;
                padding: 8px;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            QTextEdit:focus { border: 1px solid #FFEB3B; }
            QPushButton { 
                background-color: #3E4451; 
                color: white; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #4B5363; }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Edit Note for {item_name}:"))
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Enter your notes here (e.g., 'Keep for Gunsmith part 3')...")
        self.text_edit.setPlainText(current_note)
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white;") 
        
        layout.addWidget(buttons)

    def get_note(self):
        return self.text_edit.toPlainText()

class ImageDownloadWorker(QThread):
    download_complete = pyqtSignal(bool, str) 

    def __init__(self, url, save_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            response = requests.get(self.url, timeout=10, stream=True)
            if response.status_code == 200:
                with open(self.save_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        if self.isInterruptionRequested():
                            f.close()
                            if os.path.exists(self.save_path):
                                try: os.remove(self.save_path)
                                except: pass
                            return
                        f.write(chunk)
                self.download_complete.emit(True, self.save_path)
            else:
                self.download_complete.emit(False, self.save_path)
        except Exception as e:
            self.download_complete.emit(False, self.save_path)

class ItemDatabaseWindow(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        # Use the ID Map to ensure we only get unique items
        if self.data_manager.id_to_item_map:
            self.unique_items = list(self.data_manager.id_to_item_map.values())
        else:
            # Fallback deduplication just in case
            seen_ids = set()
            self.unique_items = []
            for item in self.data_manager.items.values():
                if item.get('id') and item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    self.unique_items.append(item)

        self.filtered_items = []
        self.current_display_limit = 50 # Start with 50 items to prevent lag
        
        self.active_downloads = {} 
        self.pending_labels = {}
        self.image_cache = {}
        
        # --- NEW: Requirement Cache (Performance Optimization) ---
        self.req_cache = {} 
        self._build_requirements_cache()
        # ---------------------------------------------------------
        
        self.setMinimumWidth(720) 
        self.tooltip_filter = InstantTooltipFilter(self)
        
        self.all_types = sorted(list(set(item.get('type', 'Unknown') for item in self.unique_items)))
        self.all_rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(400) 
        self.search_timer.timeout.connect(self.filter_items)

        self.init_ui()
        self.filter_items() 

    def _build_requirements_cache(self):
        """
        Pre-calculates where every item is needed (Quests, Hideout, Projects)
        to avoid expensive loops during filtering and rendering.
        """
        self.req_cache = {}
        
        # 1. Process Quests
        for quest in self.data_manager.quest_data:
            name_field = quest.get('name', {})
            quest_name = name_field.get('en', 'Unknown Quest') if isinstance(name_field, dict) else str(name_field)
            
            for req in quest.get('requiredItemIds', []):
                item_id = req.get('itemId')
                if not item_id: continue
                
                qty = req.get('quantity', 1)
                if item_id not in self.req_cache: 
                    self.req_cache[item_id] = {'types': set(), 'details': {'quest': [], 'hideout': [], 'project': []}}
                
                self.req_cache[item_id]['types'].add('quest')
                self.req_cache[item_id]['details']['quest'].append(f"{quest_name} ({qty}x)")

        # 2. Process Hideout
        for station in self.data_manager.hideout_data:
            name_field = station.get('name', {})
            station_name = name_field.get('en', 'Station') if isinstance(name_field, dict) else str(name_field)
            
            for level in station.get('levels', []):
                for req in level.get('requirementItemIds', []):
                    item_id = req.get('itemId')
                    if not item_id: continue
                    
                    qty = req.get('quantity', 1)
                    level_num = level.get('level', '?')
                    
                    if item_id not in self.req_cache: 
                        self.req_cache[item_id] = {'types': set(), 'details': {'quest': [], 'hideout': [], 'project': []}}
                    
                    self.req_cache[item_id]['types'].add('hideout')
                    self.req_cache[item_id]['details']['hideout'].append(f"{station_name} Lv.{level_num} ({qty}x)")

        # 3. Process Projects
        for proj in self.data_manager.project_data:
            name_field = proj.get('name', 'Project')
            p_name = name_field.get('en', 'Project') if isinstance(name_field, dict) else str(name_field)
            clean_name = p_name.replace("Project", "").strip() or p_name
            
            for phase in proj.get('phases', []):
                for req in phase.get('requirementItemIds', []):
                    item_id = req.get('itemId')
                    if not item_id: continue
                    
                    qty = req.get('quantity', 1)
                    
                    if item_id not in self.req_cache: 
                        self.req_cache[item_id] = {'types': set(), 'details': {'quest': [], 'hideout': [], 'project': []}}
                    
                    self.req_cache[item_id]['types'].add('project')
                    self.req_cache[item_id]['details']['project'].append(f"{clean_name} ({qty}x)")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Search & Filter Bar ---
        filter_layout = QHBoxLayout()
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search items...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #1A1F2B;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #4476ED; }
        """)
        self.search_bar.textChanged.connect(self.search_timer.start)
        filter_layout.addWidget(self.search_bar)

        self.view_filter = self._create_combo_box("All Items", ["Tracked Only", "With Notes"])
        self.view_filter.currentTextChanged.connect(self.filter_items)
        filter_layout.addWidget(self.view_filter)

        self.needed_filter = self._create_combo_box("Needed For", ["Quests", "Hideout", "Projects"])
        self.needed_filter.currentTextChanged.connect(self.filter_items)
        filter_layout.addWidget(self.needed_filter)

        self.type_filter = self._create_combo_box("All Types", self.all_types)
        self.type_filter.currentTextChanged.connect(self.filter_items)
        filter_layout.addWidget(self.type_filter)

        self.rarity_filter = self._create_combo_box("All Rarities", self.all_rarities)
        self.rarity_filter.currentTextChanged.connect(self.filter_items)
        filter_layout.addWidget(self.rarity_filter)

        main_layout.addLayout(filter_layout)
        
        # --- Legend Bar ---
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(20)
        legend_layout.setContentsMargins(0, 0, 0, 10)
        
        legend_label = QLabel("<b>Border Legend:</b>")
        legend_label.setStyleSheet("color: #888; font-size: 12px;")
        legend_layout.addWidget(legend_label)
        
        # Quest legend
        quest_box = QLabel()
        quest_box.setFixedSize(30, 20)
        quest_box.setStyleSheet("background-color: #1A1F2B; border: 2px solid #4CAF50; border-radius: 3px;")
        quest_text = QLabel("Quests")
        quest_text.setStyleSheet("color: #4CAF50; font-size: 11px;")
        legend_layout.addWidget(quest_box)
        legend_layout.addWidget(quest_text)
        
        # Hideout legend
        hideout_box = QLabel()
        hideout_box.setFixedSize(30, 20)
        hideout_box.setStyleSheet("background-color: #1A1F2B; border: 2px solid #2196F3; border-radius: 3px;")
        hideout_text = QLabel("Hideout")
        hideout_text.setStyleSheet("color: #2196F3; font-size: 11px;")
        legend_layout.addWidget(hideout_box)
        legend_layout.addWidget(hideout_text)
        
        # Project legend
        project_box = QLabel()
        project_box.setFixedSize(30, 20)
        project_box.setStyleSheet("background-color: #1A1F2B; border: 2px solid #FF9800; border-radius: 3px;")
        project_text = QLabel("Projects")
        project_text.setStyleSheet("color: #FF9800; font-size: 11px;")
        legend_layout.addWidget(project_box)
        legend_layout.addWidget(project_text)
        
        legend_layout.addStretch()
        main_layout.addLayout(legend_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QWidget { background-color: transparent; }
        """)
        
        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

    def _create_combo_box(self, default_text, items):
        combo = QComboBox()
        combo.addItem(default_text)
        combo.addItems(items)
        combo.setStyleSheet("""
            QComboBox {
                background-color: #1A1F2B;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px 10px;
                color: #ddd;
                min-width: 120px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #1A1F2B;
                selection-background-color: #4476ED;
                color: #ddd;
            }
        """)
        return combo

    def filter_items(self):
        # Always reset limit when filters change to prevent confusion
        self.current_display_limit = 50
        
        search_text = self.search_bar.text().lower().strip()
        selected_view = self.view_filter.currentText()
        selected_needed = self.needed_filter.currentText()
        selected_type = self.type_filter.currentText()
        selected_rarity = self.rarity_filter.currentText()

        tracked_items = self.data_manager.user_progress.get('tracked_items', [])
        noted_items = self.data_manager.user_progress.get('item_notes', {}).keys()

        self.filtered_items = []
        
        # Iterate over UNIQUE items only
        for item in self.unique_items:
            name = item.get('name', '').lower()
            item_type = item.get('type', 'Unknown')
            rarity = item.get('rarity', 'Common')
            item_id = item.get('id')

            # --- SEARCH LOGIC ---
            if search_text:
                match_found = False
                
                # 1. Search Main Name
                if search_text in name:
                    match_found = True
                
                # 2. Search Localized Names (so you can search in Spanish/French etc)
                if not match_found and 'names' in item and isinstance(item['names'], dict):
                    for localized_name in item['names'].values():
                        if localized_name and search_text in localized_name.lower():
                            match_found = True
                            break
                            
                # 3. Fuzzy Match (If simple match failed)
                if not match_found and _HAS_RAPIDFUZZ:
                    # Check main name
                    score = fuzz.partial_ratio(search_text, name)
                    if score >= 75: 
                        match_found = True
                    # Check localized names if needed
                    elif 'names' in item:
                         for localized_name in item['names'].values():
                             if localized_name and fuzz.partial_ratio(search_text, localized_name.lower()) >= 75:
                                 match_found = True
                                 break
                elif not match_found and not _HAS_RAPIDFUZZ:
                    # Fallback Difflib
                    s = difflib.SequenceMatcher(None, search_text, name)
                    if s.find_longest_match(0, len(search_text), 0, len(name)).size >= len(search_text) * 0.7:
                        match_found = True

                if not match_found:
                    continue

            if selected_view == "Tracked Only" and item_id not in tracked_items: continue
            if selected_view == "With Notes" and item_id not in noted_items: continue
            
            # Filter by "Needed For" - USES CACHE O(1)
            if selected_needed != "Needed For":
                # Safe lookup using cache
                cached_data = self.req_cache.get(item_id, {'types': set()})
                needed_types = cached_data['types']
                
                if selected_needed == "Quests" and 'quest' not in needed_types: continue
                if selected_needed == "Hideout" and 'hideout' not in needed_types: continue
                if selected_needed == "Projects" and 'project' not in needed_types: continue
            
            if selected_type != "All Types" and item_type != selected_type: continue
            if selected_rarity != "All Rarities" and rarity != selected_rarity: continue
            
            self.filtered_items.append(item)

        # Sort: Put exact matches first, then sort by name
        if search_text:
            # Custom sort: exact substring matches float to top
            self.filtered_items.sort(key=lambda x: (search_text not in x.get('name', '').lower(), x.get('name', '')))
        else:
            self.filtered_items.sort(key=lambda x: x.get('name', ''))
            
        self.update_display()

    def update_display(self):
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget: widget.setParent(None)

        row, col = 0, 0
        max_cols = 4 
        
        # Always apply limit to ensure performance, even during search/filtering
        limit = self.current_display_limit

        count = 0
        for item in self.filtered_items:
            if count >= limit: 
                # Create "Show More" Button
                remaining = len(self.filtered_items) - count
                show_more_btn = QPushButton(f"Show More items... ({remaining} remaining)")
                show_more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                show_more_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3E4451;
                        color: #E0E6ED;
                        border: 1px solid #5C6370;
                        border-radius: 4px;
                        padding: 10px;
                        font-weight: bold;
                        margin-top: 10px;
                    }
                    QPushButton:hover { background-color: #4B5363; border-color: #4476ED; }
                """)
                show_more_btn.clicked.connect(self.show_more_items)
                # Span the button across all columns
                self.grid_layout.addWidget(show_more_btn, row + 1, 0, 1, max_cols)
                break
            
            item_widget = self.create_item_widget(item)
            self.grid_layout.addWidget(item_widget, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
            count += 1
            
    def show_more_items(self):
        # Increase the limit by 50 and refresh
        self.current_display_limit += 50
        self.update_display()

    def create_item_widget(self, item):
        card = QFrame()
        card.setFixedSize(150, 190) 
        card.setObjectName("card")
        
        neon_rarity = {
            "Common": "#777777", "Uncommon": "#4CAF50", 
            "Rare": "#2979FF", "Epic": "#E040FB", "Legendary": "#FFAB00" 
        }
        rarity = item.get('rarity', 'Common')
        rarity_color = neon_rarity.get(rarity, "#777777")

        card.setStyleSheet(f"""
            QFrame#card {{
                background-color: #131519; 
                border: 1px solid #2A2E39;
                border-top: 4px solid {rarity_color};
                border-radius: 10px;
            }}
            QFrame#card:hover {{
                border: 1px solid {rarity_color};
                border-top: 4px solid {rarity_color};
                background-color: #1A1D24;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(8, 12, 8, 5)
        content_layout.setSpacing(5)

        # Image Label
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setFixedSize(64, 64)
        
        item_id = item.get('id')
        img_url = item.get('imageFilename')
        
        if img_url and isinstance(img_url, str):
            filename = img_url.split('/')[-1]
        else:
            filename = f"{item_id}.png"
            
        image_path = os.path.join(Constants.DATA_DIR, "images", "items", filename)
        
        # --- CACHED IMAGE LOGIC ---
        if image_path in self.image_cache:
            image_label.setPixmap(self.image_cache[image_path])
        elif os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_cache[image_path] = scaled_pixmap
            image_label.setPixmap(scaled_pixmap)
        else:
            if img_url and isinstance(img_url, str) and img_url.startswith("http"):
                image_label.setText("...") 
                image_label.setStyleSheet(f"color: #888; font-size: 12px;")
                self.start_image_download(img_url, image_path, image_label)
            else:
                image_label.setText("?")
                image_label.setStyleSheet(f"color: {rarity_color}; font-size: 24px; font-weight: bold; border: 1px dashed #444; border-radius: 4px;")
        
        content_layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Name
        name_label = QLabel(item.get('name', 'Unknown'))
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setFixedHeight(40) 
        name_label.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 12px; border: none;")
        content_layout.addWidget(name_label)
        card_layout.addWidget(content_frame)

        # Footer
        footer_frame = QFrame()
        footer_frame.setFixedHeight(35)
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: #0B0C0F;
                border-bottom-left-radius: 9px;
                border-bottom-right-radius: 9px;
                border-top: 1px solid #2A2E39;
            }
        """)
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(5, 0, 5, 0)
        footer_layout.setSpacing(5)
        footer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Track Button
        track_btn = QPushButton()
        track_btn.setCheckable(True)
        track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        track_btn.setFixedHeight(24)
        
        is_tracked = self.is_item_tracked(item_id)
        track_btn.setChecked(is_tracked)
        
        # Check where item is needed (Uses Cache now)
        needed_in = self.check_item_needed_for(item_id)
        self.update_track_button_style(track_btn, is_tracked, needed_in)
        track_btn.clicked.connect(lambda checked, i=item_id, b=track_btn: self.toggle_track_item(i, b))
        
        # Note Button
        note_btn = QPushButton("NOTES")
        note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        note_btn.setFixedHeight(24)
        
        self.update_note_button_style(note_btn, item_id)
        note_btn.clicked.connect(lambda checked, i=item_id, b=note_btn, c=card: self.edit_item_note(i, b, c, item, rarity_color))
        
        footer_layout.addWidget(track_btn)
        footer_layout.addWidget(note_btn)
        
        card_layout.addWidget(footer_frame)

        self._setup_tooltip(card, item, rarity_color)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        return card

    def start_image_download(self, url, path, label):
        if path not in self.pending_labels:
            self.pending_labels[path] = []
        self.pending_labels[path].append(label)

        if path in self.active_downloads:
            return 

        worker = ImageDownloadWorker(url, path, parent=self)
        worker.download_complete.connect(self.on_download_complete)
        worker.finished.connect(self.on_worker_finished)
        
        self.active_downloads[path] = worker
        worker.start()

    def on_download_complete(self, success, path):
        labels = self.pending_labels.pop(path, [])
        
        cached_pixmap = None
        if success and os.path.exists(path):
            try:
                pixmap = QPixmap(path)
                cached_pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_cache[path] = cached_pixmap
            except Exception:
                pass

        for label in labels:
            try:
                if cached_pixmap:
                    label.setPixmap(cached_pixmap)
                    label.setStyleSheet("") 
                elif success:
                     label.setText("err")
                else:
                    label.setText("x") 
            except RuntimeError:
                pass

    def on_worker_finished(self):
        worker = self.sender()
        if isinstance(worker, ImageDownloadWorker):
            path = worker.save_path
            if path in self.active_downloads:
                del self.active_downloads[path]
            worker.deleteLater()

    def _setup_tooltip(self, widget, item, color_hex):
        tooltip_lines = [f"<b style='font-size:14px; color:{color_hex}'>{item.get('name', 'Unknown')}</b>"]
        if (val := item.get('value')) is not None: tooltip_lines.append(f"Price: £{val}")
        if (w := item.get('weightKg')) is not None: tooltip_lines.append(f"Weight: {w}kg")
        if (s := item.get('stackSize')) is not None: tooltip_lines.append(f"Stack: {s}")
        
        item_id = item.get('id')
        if item_id:
            user_note = self.data_manager.get_item_note(item_id)
            if user_note:
                 safe_note = user_note.replace("<", "&lt;").replace(">", "&gt;")
                 if len(safe_note) > 100: safe_note = safe_note[:97] + "..."
                 tooltip_lines.append(f"<br><b>Note:</b> <span style='color:#FFEB3B'><i>{safe_note}</i></span>")

        trades = self.data_manager.find_trades_for_item(item.get('name', ''))
        if trades:
            traders = sorted(list(set(t.get('trader', 'Unknown').title() for t in trades)))
            tooltip_lines.append(f"<br><b>Sold by:</b> <span style='color:#ADD8E6'>{', '.join(traders)}</span>")
            
        # --- NEW: Use Cache for Tooltips (Faster) ---
        if item_id:
            cached = self.req_cache.get(item_id, {'details': {}})
            details = cached.get('details', {})
            
            quest_details = details.get('quest', [])
            hideout_details = details.get('hideout', [])
            project_details = details.get('project', [])

            if quest_details:
                tooltip_lines.append(f"<b>Quests:</b> <span style='color:#4CAF50'>{', '.join(quest_details[:3])}</span>")
                if len(quest_details) > 3:
                    tooltip_lines.append(f"<span style='color:#888'>...and {len(quest_details) - 3} more</span>")
            
            if hideout_details:
                tooltip_lines.append(f"<b>Hideout:</b> <span style='color:#2196F3'>{', '.join(hideout_details[:3])}</span>")
                if len(hideout_details) > 3:
                    tooltip_lines.append(f"<span style='color:#888'>...and {len(hideout_details) - 3} more</span>")
            
            if project_details:
                tooltip_lines.append(f"<b>Projects:</b> <span style='color:#FF9800'>{', '.join(project_details[:3])}</span>")
                if len(project_details) > 3:
                    tooltip_lines.append(f"<span style='color:#888'>...and {len(project_details) - 3} more</span>")
        # --------------------------------------------
            
        if (cb := item.get('craftBench')):
            bench = cb if isinstance(cb, str) else ", ".join(cb)
            tooltip_lines.append(f"<b>Craft:</b> {bench.replace('_', ' ').title()}")

        inner_html = "<br>".join(tooltip_lines)
        full_tooltip = f"<div style='color:#eee; padding:4px;'>{inner_html}</div>"
        widget.setToolTip(full_tooltip)
        widget.installEventFilter(self.tooltip_filter)

    def is_item_tracked(self, item_id):
        return item_id in self.data_manager.user_progress.get('tracked_items', [])

    def check_item_needed_for(self, item_id):
        """Check where item is needed: quests, hideout, or projects (Uses Cache)"""
        # Return list of types from cache (e.g., ['quest', 'hideout'])
        if item_id in self.req_cache:
            return list(self.req_cache[item_id]['types'])
        return []

    def toggle_track_item(self, item_id, button):
        tracked_items = self.data_manager.user_progress.get('tracked_items', [])
        needed_in = self.check_item_needed_for(item_id)
        
        if item_id in tracked_items:
            tracked_items.remove(item_id)
            self.update_track_button_style(button, False, needed_in)
        else:
            tracked_items.append(item_id)
            self.update_track_button_style(button, True, needed_in)
        self.data_manager.user_progress['tracked_items'] = tracked_items
        self.data_manager.save_user_progress()
        self.filter_items()

    def update_track_button_style(self, button, is_tracked, needed_in=None):
        if needed_in is None:
            needed_in = []
        
        # Define border colors based on where item is needed
        colors = []
        if 'quest' in needed_in:
            colors.append('#4CAF50')  # Green
        if 'hideout' in needed_in:
            colors.append('#2196F3')  # Blue
        if 'project' in needed_in:
            colors.append('#FF9800')  # Orange
        
        # Divide border among colors
        if len(colors) == 3:
            # All 3: top + left = green, right = blue, bottom = orange
            border_style = f"border-top: 2px solid {colors[0]}; border-left: 2px solid {colors[0]}; border-right: 2px solid {colors[1]}; border-bottom: 2px solid {colors[2]};"
        elif len(colors) == 2:
            # 2 colors: top + left = first, right + bottom = second
            border_style = f"border-top: 2px solid {colors[0]}; border-left: 2px solid {colors[0]}; border-right: 2px solid {colors[1]}; border-bottom: 2px solid {colors[1]};"
        elif len(colors) == 1:
            # Single color
            border_style = f"border: 2px solid {colors[0]};"
        else:
            # No special requirements
            border_style = "border: 1px solid #444;"
        
        # FIX: Include border_style in hover state so colors don't vanish on hover
        if is_tracked:
            button.setText("TRACKED")
            button.setStyleSheet(f"""
                QPushButton {{ background-color: rgba(76, 175, 80, 0.2); color: #4CAF50;
                    {border_style} border-radius: 4px; font-weight: bold; font-size: 10px; }}
                QPushButton:hover {{ {border_style} background-color: rgba(76, 175, 80, 0.4); }}
            """)
        else:
            button.setText("TRACK")
            button.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: #666;
                    {border_style} border-radius: 4px; font-weight: bold; font-size: 10px; }}
                QPushButton:hover {{ {border_style} color: #aaa; }}
            """)

    def edit_item_note(self, item_id, button, card_widget, item, color_hex):
        current_note = self.data_manager.get_item_note(item_id)
        dialog = NoteEditorDialog(item.get('name', 'Item'), current_note, self)
        
        if dialog.exec():
            new_note = dialog.get_note()
            self.data_manager.set_item_note(item_id, new_note)
            self.update_note_button_style(button, item_id)
            self._setup_tooltip(card_widget, item, color_hex)

    def update_note_button_style(self, button, item_id):
        has_note = bool(self.data_manager.get_item_note(item_id))
        if has_note:
            button.setStyleSheet("""
                QPushButton { background-color: rgba(255, 235, 59, 0.15); color: #FFEB3B;
                    border: 1px solid #FFEB3B; border-radius: 4px; font-weight: bold; font-size: 10px; }
                QPushButton:hover { background-color: rgba(255, 235, 59, 0.3); }
            """)
            button.setToolTip("Edit Note")
        else:
            button.setStyleSheet("""
                QPushButton { background-color: transparent; color: #666;
                    border: 1px solid #444; border-radius: 4px; font-weight: bold; font-size: 10px; }
                QPushButton:hover { border: 1px solid #888; color: #aaa; }
            """)
            button.setToolTip("Add Note")

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def cleanup(self):
        for worker in list(self.active_downloads.values()):
            if worker.isRunning():
                worker.requestInterruption()
                worker.quit()
                worker.wait(100) 
        self.active_downloads.clear()
        self.pending_labels.clear()

    def _perform_save(self):
        pass