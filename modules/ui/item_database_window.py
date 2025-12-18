from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QScrollArea, QComboBox, QMessageBox, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QTimer
import os
from modules.core.constants import Constants
from .base_page import BasePage
from .item_database_widgets import ExpandableItemRow, ItemImageLoader, NotesDialog

class ItemDatabaseWindow(BasePage):
    def __init__(self, data_manager, lang_code="en"):
        super().__init__("Item Database") 
        self.data_manager = data_manager
        self.lang_code = lang_code
        self.image_loader = ItemImageLoader(self)
        
        if self.data_manager.id_to_item_map:
            self.unique_items = list(self.data_manager.id_to_item_map.values())
        else:
            seen = set()
            self.unique_items = []
            for i in self.data_manager.items.values():
                if i.get('id') and i['id'] not in seen:
                    seen.add(i['id'])
                    self.unique_items.append(i)
        
        self.expanded_item_id = None  # Track currently expanded item (accordion)
        self.item_rows = {}  # Map item_id -> ExpandableItemRow widget
        
        self._enforce_blueprint_defaults()
        self.filtered_items = []
        self.current_display_limit = 50
        self.req_cache = {}
        self._build_requirements_cache()
        self.all_types = sorted(list(set(item.get('type', 'Unknown') for item in self.unique_items)))
        self.all_rarities = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.filter_items)
        
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(200)
        self.resize_timer.timeout.connect(self.update_display)
        
        self.init_ui()
        self.filter_items()
        self.update_blueprint_stats()

    def init_ui(self):
        # === Filter Bar ===
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search items...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #1A1F2B;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 10px 12px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #4476ED;
            }
        """)
        self.search_bar.textChanged.connect(self.search_timer.start)
        filter_layout.addWidget(self.search_bar, 1)
        
        # Reset button
        self.reset_btn = QPushButton("✖")
        self.reset_btn.setFixedSize(38, 38)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Reset Search and Filters")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(211, 47, 47, 0.2);
                color: #ef5350;
                border: 1px solid #ef5350;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(211, 47, 47, 0.4);
            }
        """)
        self.reset_btn.clicked.connect(self.reset_filters)
        filter_layout.addWidget(self.reset_btn)
        
        # Dropdowns
        self.view_filter = self._create_combo("All Items", ["Tracked Only", "Stash", "Quests", "Hideout", "Projects"])
        self.type_filter = self._create_combo("All Types", self.all_types)
        self.rarity_filter = self._create_combo("All Rarities", self.all_rarities)
        
        for w in [self.view_filter, self.type_filter, self.rarity_filter]:
            filter_layout.addWidget(w)
        
        self.content_layout.addLayout(filter_layout)
        
        # === Quick Action Buttons ===
        quick_layout = QHBoxLayout()
        quick_layout.setContentsMargins(0, 10, 0, 10)
        quick_layout.setSpacing(12)
        
        self.bp_filter_btn = QPushButton("📘 Blueprints (0/0)")
        self.bp_filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bp_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E3A5F;
                color: #FFF;
                border: 1px solid #4476ED;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2b4c75;
            }
        """)
        self.bp_filter_btn.clicked.connect(self._filter_to_blueprints)
        
        self.storage_filter_btn = QPushButton("📦 In Stash")
        self.storage_filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.storage_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E5C32;
                color: #FFF;
                border: 1px solid #4CAF50;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3d7a42;
            }
        """)
        self.storage_filter_btn.clicked.connect(self._filter_to_storage)
        
        quick_layout.addWidget(self.bp_filter_btn)
        quick_layout.addWidget(self.storage_filter_btn)
        quick_layout.addStretch()
        
        # Item count label
        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet("color: #6B7280; font-size: 13px;")
        quick_layout.addWidget(self.count_label)
        
        self.content_layout.addLayout(quick_layout)
        
        # === Divider ===
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #282C36;")
        divider.setFixedHeight(1)
        self.content_layout.addWidget(divider)
        
        # === Item List (Scrollable) ===
        self.scroll_content = QWidget()
        self.list_layout = QVBoxLayout(self.scroll_content)
        self.list_layout.setContentsMargins(0, 12, 0, 12)
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.inner_scroll = QScrollArea()
        self.inner_scroll.setWidgetResizable(True)
        self.inner_scroll.setWidget(self.scroll_content)
        self.inner_scroll.setStyleSheet("background: transparent; border: none;")
        
        self.content_layout.addWidget(self.inner_scroll)

    # ==========================================================================
    # DATA & FILTER LOGIC
    # ==========================================================================
    
    def _enforce_blueprint_defaults(self):
        tracked = self.data_manager.user_progress.get('tracked_items', [])
        stash = self.data_manager.user_progress.get('stash_inventory', {})
        changed = False
        
        for item in self.unique_items:
            if (item.get('type') == "Blueprint") or ("Blueprint" in item.get('name', '')):
                iid = item.get('id')
                if stash.get(iid, 0) == 0 and iid not in tracked:
                    tracked.append(iid)
                    changed = True
        
        if changed:
            self.data_manager.user_progress['tracked_items'] = tracked
            self.data_manager.save_user_progress()

    def _build_requirements_cache(self):
        self.req_cache = {}
        
        def get_name(obj, fallback):
            n = obj.get('name', {})
            return n.get(self.lang_code, n.get('en', fallback)) if isinstance(n, dict) else n
        
        for quest in self.data_manager.quest_data:
            q_name = get_name(quest, 'Quest')
            for req in quest.get('requiredItemIds', []):
                self._add_to_cache(req.get('itemId'), 'quest', f"{q_name} ({req.get('quantity', 1)}x)")
        
        for station in self.data_manager.hideout_data:
            s_name = get_name(station, 'Station')
            for level in station.get('levels', []):
                for req in level.get('requirementItemIds', []):
                    self._add_to_cache(req.get('itemId'), 'hideout', f"{s_name} Lv.{level.get('level')} ({req.get('quantity', 1)}x)")
        
        for proj in self.data_manager.project_data:
            p_name = get_name(proj, 'Project').replace("Project", "").strip()
            for phase in proj.get('phases', []):
                for req in phase.get('requirementItemIds', []):
                    self._add_to_cache(req.get('itemId'), 'project', f"{p_name} ({req.get('quantity', 1)}x)")

    def _add_to_cache(self, item_id, type_key, text):
        if not item_id:
            return
        if item_id not in self.req_cache:
            self.req_cache[item_id] = {'types': set(), 'details': {'quest': [], 'hideout': [], 'project': []}}
        self.req_cache[item_id]['types'].add(type_key)
        self.req_cache[item_id]['details'][type_key].append(text)

    def _create_combo(self, default, items):
        c = QComboBox()
        c.addItem(default)
        c.addItems(items)
        c.setStyleSheet("""
            QComboBox {
                background-color: #1A1F2B;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px 12px;
                color: #E0E6ED;
                min-width: 100px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1A1F2B;
                selection-background-color: #4476ED;
                color: #E0E6ED;
                border: 1px solid #333;
            }
        """)
        c.currentTextChanged.connect(self.filter_items)
        return c

    def _filter_to_blueprints(self):
        self.view_filter.setCurrentText("All Items")
        self.type_filter.setCurrentText("Blueprint")
        self.filter_items()

    def _filter_to_storage(self):
        self.view_filter.setCurrentText("Stash")
        self.filter_items()

    def reset_filters(self):
        self.search_bar.blockSignals(True)
        self.view_filter.blockSignals(True)
        self.type_filter.blockSignals(True)
        self.rarity_filter.blockSignals(True)
        
        self.search_bar.clear()
        self.view_filter.setCurrentIndex(0)
        self.type_filter.setCurrentIndex(0)
        self.rarity_filter.setCurrentIndex(0)
        
        self.search_bar.blockSignals(False)
        self.view_filter.blockSignals(False)
        self.type_filter.blockSignals(False)
        self.rarity_filter.blockSignals(False)
        
        self.filter_items()

    def update_blueprint_stats(self):
        total = 0
        collected = 0
        stash = self.data_manager.user_progress.get('stash_inventory', {})
        
        for item in self.unique_items:
            if (item.get('type') == "Blueprint") or ("Blueprint" in item.get('name', '')):
                total += 1
                if stash.get(item.get('id'), 0) > 0:
                    collected += 1
        
        self.bp_filter_btn.setText(f"📘 Blueprints ({collected}/{total})")

    def filter_items(self):
        self.current_display_limit = 50
        self.expanded_item_id = None  # Collapse any expanded item when filtering
        
        search = self.search_bar.text().lower().strip()
        view = self.view_filter.currentText()
        f_type = self.type_filter.currentText()
        f_rarity = self.rarity_filter.currentText()
        
        tracked = self.data_manager.user_progress.get('tracked_items', [])
        stash = self.data_manager.user_progress.get('stash_inventory', {})
        
        self.filtered_items = []
        
        for item in self.unique_items:
            name = item.get('name', '').lower()
            iid = item.get('id')
            
            if search:
                found = search in name
                if not found and 'names' in item:
                    for val in item['names'].values():
                        if val and search in val.lower():
                            found = True
                            break
                if not found:
                    continue
            
            if view == "Tracked Only" and iid not in tracked:
                continue
            if view == "Stash" and stash.get(iid, 0) <= 0:
                continue
            
            reqs = self.req_cache.get(iid, {'types': set()})['types']
            if view == "Quests" and 'quest' not in reqs:
                continue
            if view == "Hideout" and 'hideout' not in reqs:
                continue
            if view == "Projects" and 'project' not in reqs:
                continue
            
            if f_type != "All Types" and item.get('type') != f_type:
                continue
            if f_rarity != "All Rarities" and item.get('rarity') != f_rarity:
                continue
            
            self.filtered_items.append(item)
        
        # Sort
        if search:
            self.filtered_items.sort(key=lambda x: (search not in x.get('name', '').lower(), x.get('name', '')))
        else:
            self.filtered_items.sort(key=lambda x: x.get('name', ''))
        
        self.update_display()

    def resizeEvent(self, event):
        self.resize_timer.start()
        super().resizeEvent(event)

    # ==========================================================================
    # DISPLAY & UI UPDATE
    # ==========================================================================
    
    def update_display(self):
        # Clear existing items
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.item_rows.clear()
        
        count = 0
        limit = self.current_display_limit
        stash = self.data_manager.user_progress.get('stash_inventory', {})
        tracked_items = self.data_manager.user_progress.get('tracked_items', [])
        item_notes = self.data_manager.user_progress.get('item_notes', {})

        for item in self.filtered_items:
            if count >= limit:
                # Show More button
                btn = QPushButton(f"📋 Show More ({len(self.filtered_items) - count} remaining)")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #232834;
                        color: #E0E6ED;
                        border: 1px solid #3E4451;
                        border-radius: 8px;
                        padding: 14px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #2C323C;
                        border-color: #4476ED;
                    }
                """)
                btn.clicked.connect(lambda: self._show_more())
                self.list_layout.addWidget(btn)
                break
            
            loc_name = self.data_manager.get_localized_name(item, self.lang_code)
            is_bp = (item.get('type') == "Blueprint") or ("Blueprint" in item.get('name', ''))
            is_collected = stash.get(item.get('id'), 0) > 0 if is_bp else False
            
            try:
                stack_size = int(item.get('stackSize', 1))
            except:
                stack_size = 1
            if stack_size < 1:
                stack_size = 1
            
            stash_count = stash.get(item.get('id'), 0)
            req_details = self.req_cache.get(item.get('id'), {'details': {}})['details']
            is_tracked = item.get('id') in tracked_items
            has_notes = bool(item_notes.get(item.get('id'), '').strip())

            row = ExpandableItemRow(
                item, loc_name, self.image_loader,
                stash_count=stash_count, stack_size=stack_size,
                is_collected=is_collected, req_details=req_details,
                is_tracked=is_tracked, has_notes=has_notes
            )
            
            row.item_clicked.connect(self.on_item_clicked)
            row.stash_changed.connect(self.on_stash_changed)
            row.track_toggled.connect(self.on_track_toggled)
            row.notes_requested.connect(self.on_notes_requested)
            
            self.item_rows[item.get('id')] = row
            self.list_layout.addWidget(row)
            count += 1
        
        self.list_layout.addStretch()
        
        # Update count label
        self.count_label.setText(f"{len(self.filtered_items)} items")

    def _show_more(self):
        self.current_display_limit += 50
        self.update_display()

    def on_item_clicked(self, item):
        """Handle accordion behavior - collapse previous, expand new."""
        item_id = item.get('id')
        
        # Collapse previously expanded item
        if self.expanded_item_id and self.expanded_item_id != item_id:
            if self.expanded_item_id in self.item_rows:
                self.item_rows[self.expanded_item_id].set_expanded(False)
        
        # Toggle current item
        if item_id in self.item_rows:
            row = self.item_rows[item_id]
            is_now_expanded = not row.is_expanded
            row.set_expanded(is_now_expanded)
            self.expanded_item_id = item_id if is_now_expanded else None

    def on_stash_changed(self, item_id, new_count):
        """Handle stash count changes from detail panel."""
        stash = self.data_manager.user_progress.get('stash_inventory', {})
        stash[item_id] = new_count
        self.data_manager.user_progress['stash_inventory'] = stash
        self.data_manager.save_user_progress()
        self.start_save_timer()
        self.update_blueprint_stats()

    def on_track_toggled(self, item_id):
        """Handle track toggle from detail panel."""
        tracked = self.data_manager.user_progress.get('tracked_items', [])
        
        if item_id in tracked:
            tracked.remove(item_id)
        else:
            tracked.append(item_id)
        
        self.data_manager.user_progress['tracked_items'] = tracked
        self.data_manager.save_user_progress()
        self.start_save_timer()

    def on_notes_requested(self, item_id):
        """Open notes dialog for the item."""
        # Find item name
        item_name = item_id
        for item in self.unique_items:
            if item.get('id') == item_id:
                item_name = self.data_manager.get_localized_name(item, self.lang_code)
                break
        
        # Get current notes
        item_notes = self.data_manager.user_progress.get('item_notes', {})
        current_notes = item_notes.get(item_id, '')
        
        # Show dialog
        dialog = NotesDialog(item_id, item_name, current_notes, self)
        dialog.notes_saved.connect(self._save_notes)
        dialog.exec()

    def _save_notes(self, item_id, notes):
        """Save notes for an item."""
        item_notes = self.data_manager.user_progress.get('item_notes', {})
        
        if notes.strip():
            item_notes[item_id] = notes
        else:
            item_notes.pop(item_id, None)  # Remove if empty
        
        self.data_manager.user_progress['item_notes'] = item_notes
        self.data_manager.save_user_progress()
        self.start_save_timer()
        
        # Update indicator on the row
        if item_id in self.item_rows:
            self.item_rows[item_id].update_notes_indicator(bool(notes.strip()))

    # ==========================================================================
    # RESET & CLEANUP
    # ==========================================================================
    
    def confirm_reset(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Reset")
        msg.setText("Are you sure you want to completely reset ALL Stash, Blueprints, and Tracked Items?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            msg_notes = QMessageBox(self)
            msg_notes.setWindowTitle("Clear Notes?")
            msg_notes.setText("Do you also want to clear all Item Notes?")
            msg_notes.setInformativeText("Select 'No' to keep your personal notes.")
            msg_notes.setIcon(QMessageBox.Icon.Question)
            msg_notes.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_notes.setDefaultButton(QMessageBox.StandardButton.No)
            
            clear_notes = (msg_notes.exec() == QMessageBox.StandardButton.Yes)
            self.reset_state(clear_notes=clear_notes)

    def reset_state(self, clear_notes=False):
        self.data_manager.user_progress['stash_inventory'] = {}
        self.data_manager.user_progress['tracked_items'] = []
        if clear_notes:
            self.data_manager.user_progress['item_notes'] = {}
            
        self.data_manager.save_user_progress()
        self.reset_filters()
        self._enforce_blueprint_defaults()
        self.filter_items()
        self.update_blueprint_stats()

    def cleanup(self):
        if hasattr(self, 'image_loader'):
            self.image_loader.cleanup()

    def closeEvent(self, event): 
        self.cleanup()
        super().closeEvent(event)