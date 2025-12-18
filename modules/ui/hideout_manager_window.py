from PyQt6.QtWidgets import (QLabel, QPushButton, QFrame, QMessageBox, QCheckBox, QVBoxLayout, QHBoxLayout, QWidget)
from PyQt6.QtCore import Qt
from modules.core.constants import Constants
from .ui_components import InventoryControl
from .base_page import BasePage

class HideoutManagerWindow(BasePage):
    def __init__(self, hideout_data, user_progress, data_manager, rarity_colors, lang_code="en"):
        super().__init__("Hideout Manager") # Title
        
        self.data_manager = data_manager
        self.rarity_colors = rarity_colors
        self.raw_hideout_data = hideout_data
        self.user_progress = user_progress
        self.lang_code = lang_code 
        
        # self.user_progress is now accessed directly via self.data_manager.user_progress
        # to ensure we always have the latest reference even if DataManager reloads it.
        
        if 'hideout_inventory' not in self.data_manager.user_progress:
            self.data_manager.user_progress['hideout_inventory'] = {}
        
        self.station_widgets = {} 
        self.inventory_widgets = {} 
        self.station_current_levels = {}

        self.station_order = self.data_manager.user_progress.get('hideout_station_order', [s['id'] for s in self.raw_hideout_data])
        
        all_ids = [s['id'] for s in self.raw_hideout_data]
        if not self.station_order: self.station_order = all_ids # Fallback

        for sid in all_ids:
            if sid not in self.station_order: self.station_order.append(sid)
        
        # Add Header Controls
        self.chk_show_all_reqs = QCheckBox("Show All Requirements")
        self.chk_show_all_reqs.stateChanged.connect(self.refresh_ui)
        self.header.add_widget(self.chk_show_all_reqs)
        
        self.btn_toggle_all = QPushButton("Expand All")
        self.btn_toggle_all.setFixedSize(100, 30)
        self.btn_toggle_all.clicked.connect(self.toggle_all)
        self.header.add_widget(self.btn_toggle_all)
        
        self.all_expanded = False
        
        self._create_all_station_widgets()
        self.refresh_ui()

    def _create_all_station_widgets(self):
        self.inventory_widgets = {} 
        self.station_widgets = {}

        for station in self.raw_hideout_data:
            station_id = station.get('id')
            if not station_id: continue
            
            station_frame = QFrame()
            station_frame.setObjectName("StationFrame") 
            s_layout = QVBoxLayout(station_frame)
            s_layout.setContentsMargins(4, 4, 4, 4)
            
            header = QHBoxLayout(); header.setContentsMargins(0, 0, 0, 0)
            
            btn_up = QPushButton("▲"); btn_up.setObjectName("inv_button"); btn_up.setFixedSize(24, 24)
            btn_up.clicked.connect(lambda _, sid=station_id: self.move_station(sid, -1))
            
            btn_down = QPushButton("▼"); btn_down.setObjectName("inv_button"); btn_down.setFixedSize(24, 24)
            btn_down.clicked.connect(lambda _, sid=station_id: self.move_station(sid, 1))
            
            header.addWidget(btn_up); header.addWidget(btn_down)
            
            display_name = self.data_manager.get_localized_name(station, self.lang_code)
            name_lbl = QLabel(display_name, objectName="Header")
            name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #4476ED; border: none;")
            header.addWidget(name_lbl); header.addStretch()
            
            current_lvl = self.data_manager.user_progress.get(station_id, 0)
            self.station_current_levels[station_id] = current_lvl
            
            lvl_lbl = None
            if station.get('maxLevel', 0) > 0:
                lvl_layout = QHBoxLayout()
                lvl_lbl = QLabel(str(current_lvl))
                lvl_lbl.setStyleSheet("border: none; font-weight: bold; font-size: 14px; padding: 0 5px;")
                
                btn_down_lvl = QPushButton("-"); btn_down_lvl.setFixedSize(24, 24); btn_down_lvl.setObjectName("inv_button")
                btn_down_lvl.clicked.connect(lambda _, s=station_id, m=station.get('maxLevel'): self.change_station_level(s, -1, m))
                
                btn_up_lvl = QPushButton("+"); btn_up_lvl.setFixedSize(24, 24); btn_up_lvl.setObjectName("inv_button")
                btn_up_lvl.clicked.connect(lambda _, s=station_id, m=station.get('maxLevel'): self.change_station_level(s, 1, m))
                
                lvl_layout.addWidget(btn_down_lvl); lvl_layout.addWidget(lvl_lbl); lvl_layout.addWidget(btn_up_lvl)
                header.addLayout(lvl_layout)
            
            toggle_btn = QPushButton("▼"); toggle_btn.setCheckable(True); toggle_btn.setFixedSize(24, 24); toggle_btn.setObjectName("inv_button")
            
            # Load saved expansion state (default to self.all_expanded if not found)
            saved_expanded = self.data_manager.user_progress.get('hideout_station_expanded', {}).get(station_id, self.all_expanded)
            toggle_btn.setChecked(saved_expanded)
            header.addWidget(toggle_btn)

            s_layout.addLayout(header)

            levels_container = QWidget()
            levels_layout = QVBoxLayout(levels_container); levels_layout.setContentsMargins(4, 0, 0, 0) 
            levels_container.setVisible(saved_expanded)
            
            toggle_btn.setText("▲" if saved_expanded else "▼")
            toggle_btn.toggled.connect(levels_container.setVisible)
            toggle_btn.toggled.connect(lambda checked, b=toggle_btn: b.setText("▲" if checked else "▼"))
            toggle_btn.toggled.connect(lambda checked, sid=station_id: self._on_station_toggled(checked, sid))
            s_layout.addWidget(levels_container)

            level_containers = {} 
            for level_info in sorted(station.get('levels', []), key=lambda x: x.get('level', 0)):
                lvl_num = level_info.get('level', 0)
                if lvl_num == 0: continue
                reqs = level_info.get('requirementItemIds', [])
                other_reqs = level_info.get('otherRequirements', [])
                if not reqs and not other_reqs: continue

                level_req_container = QWidget(); level_req_layout = QVBoxLayout(level_req_container); level_req_layout.setContentsMargins(0, 5, 0, 5)
                levels_layout.addWidget(level_req_container); level_containers[lvl_num] = level_req_container

                lvl_header = QLabel(f"Level {lvl_num} Requirements:"); lvl_header.setStyleSheet("font-weight: bold; color: #9DA5B4; border: none;")
                level_req_layout.addWidget(lvl_header)
                
                for req in reqs:
                    item_id, qty_needed = req.get('itemId'), req.get('quantity', 0)
                    item_name = self.data_manager.get_localized_name(item_id, self.lang_code)
                    saved_qty = self.data_manager.user_progress.get('hideout_inventory', {}).get(station_id, {}).get(str(lvl_num), {}).get(item_id, 0)
                    row = QHBoxLayout()
                    item_obj = self.data_manager.id_to_item_map.get(item_id)
                    rarity = item_obj.get('rarity', 'Common') if item_obj else 'Common'
                    lbl_name = QLabel(item_name); lbl_name.setStyleSheet(f"color: {self.rarity_colors.get(rarity, '#E0E0E0')}; border: none;")
                    row.addWidget(lbl_name); row.addStretch(1)
                    ctrl = InventoryControl(saved_qty, qty_needed, show_extra_buttons=False) 
                    # Connect to sync method that updates user_progress immediately
                    ctrl.value_changed.connect(lambda sid=station_id, ln=lvl_num, iid=item_id: self._on_inventory_changed(sid, ln, iid))
                    self.inventory_widgets[(station_id, lvl_num, item_id)] = ctrl
                    row.addWidget(ctrl); level_req_layout.addLayout(row)
                
                # Handle otherRequirements (e.g., Coins for Stash upgrades)
                for other_req in other_reqs:
                    row = QHBoxLayout()
                    # Parse requirement text (e.g., "5000 Coins")
                    lbl_name = QLabel("Coins"); lbl_name.setStyleSheet("color: #E5C07B; border: none;")
                    row.addWidget(lbl_name); row.addStretch(1)
                    lbl_amount = QLabel(other_req); lbl_amount.setStyleSheet("color: #E5C07B; border: none; font-weight: bold;")
                    row.addWidget(lbl_amount)
                    level_req_layout.addLayout(row)

            # Add "No available upgrades" label
            no_upgrades_lbl = QLabel("No available upgrades at this time")
            no_upgrades_lbl.setStyleSheet("color: #9DA5B4; font-style: italic; padding: 5px;")
            no_upgrades_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            levels_layout.addWidget(no_upgrades_lbl)
            no_upgrades_lbl.hide()

            self.station_widgets[station_id] = { 
                'frame': station_frame, 
                'btn_up': btn_up, 
                'btn_down': btn_down, 
                'lvl_lbl': lvl_lbl, 
                'toggle_btn': toggle_btn, 
                'level_containers': level_containers,
                'no_upgrades_lbl': no_upgrades_lbl
            }

    def _on_inventory_changed(self, station_id, lvl_num, item_id):
        """Called when an inventory control value changes - syncs to user_progress immediately."""
        widget = self.inventory_widgets.get((station_id, lvl_num, item_id))
        if widget:
            val = widget.get_value()
            # Ensure the nested dictionaries exist
            hideout_inv = self.data_manager.user_progress.setdefault('hideout_inventory', {})
            station_inv = hideout_inv.setdefault(station_id, {})
            level_inv = station_inv.setdefault(str(lvl_num), {})
            
            # Update user_progress immediately so overlay shows current values
            if val > 0:
                level_inv[item_id] = val
            elif item_id in level_inv:
                del level_inv[item_id]
        # Start save timer to persist to disk
        self.start_save_timer()

    def _on_station_toggled(self, checked, station_id):
        self.data_manager.user_progress.setdefault('hideout_station_expanded', {})[station_id] = checked
        self.start_save_timer()

    def refresh_ui(self):
        sorted_ids = sorted(self.station_widgets.keys(), key=lambda sid: self.station_order.index(sid) if sid in self.station_order else 999)
        for i, sid in enumerate(sorted_ids):
            widgets = self.station_widgets[sid]
            self.content_layout.insertWidget(i, widgets['frame'])
            widgets['btn_up'].setEnabled(i > 0)
            widgets['btn_down'].setEnabled(i < len(sorted_ids) - 1)
            if widgets['lvl_lbl']: widgets['lvl_lbl'].setText(str(self.station_current_levels[sid]))
            show_all = self.chk_show_all_reqs.isChecked()
            curr_lvl = self.station_current_levels[sid]
            any_visible = False
            for lvl, container in widgets['level_containers'].items():
                is_visible = show_all or (lvl > curr_lvl)
                container.setVisible(is_visible)
                if is_visible: any_visible = True
            
            if 'no_upgrades_lbl' in widgets:
                widgets['no_upgrades_lbl'].setVisible(not any_visible)

    def move_station(self, station_id, direction):
        try: current_index = self.station_order.index(station_id)
        except ValueError: return
        new_index = current_index + direction
        if 0 <= new_index < len(self.station_order):
            self.station_order.insert(new_index, self.station_order.pop(current_index))
            # Update user_progress immediately
            self.data_manager.user_progress['hideout_station_order'] = self.station_order
            self.refresh_ui()
            self.start_save_timer()

    def change_station_level(self, station_id, delta, max_lvl):
        cur = self.station_current_levels[station_id]
        new_val = max(0, min(max_lvl, cur + delta))
        self.station_current_levels[station_id] = new_val
        # Update user_progress immediately
        self.data_manager.user_progress[station_id] = new_val
        self.refresh_ui()
        self.start_save_timer()

    def toggle_all(self):
        self.all_expanded = not self.all_expanded
        self.btn_toggle_all.setText("Collapse All" if self.all_expanded else "Expand All")
        for sid, widgets in self.station_widgets.items():
            widgets['toggle_btn'].setChecked(self.all_expanded)
            widgets['toggle_btn'].setText("▲" if self.all_expanded else "▼")
            # Update individual state too so it persists
            self.data_manager.user_progress.setdefault('hideout_station_expanded', {})[sid] = self.all_expanded
        self.start_save_timer()

    def confirm_reset(self):
        msg = QMessageBox(self); msg.setWindowTitle("Confirm Reset")
        msg.setText("Are you sure you want to completely reset ALL Hideout progress?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes: self.reset_state()

    # --- BASE PAGE OVERRIDES ---
    def reset_state(self):
        self.data_manager.user_progress['hideout_inventory'] = {}
        self.data_manager.user_progress.pop('hideout_station_expanded', None)
        for sid in self.station_widgets.keys():
            self.station_current_levels[sid] = 0
            self.data_manager.user_progress[sid] = 0
            for key, widget in self.inventory_widgets.items():
                if key[0] == sid: widget.set_value(0) 
        self.start_save_timer()
        self.refresh_ui()

    def save_state(self):
        # Sync all current widget values to user_progress (in case any were missed)
        self.data_manager.user_progress['hideout_station_order'] = self.station_order
        for s_id, val in self.station_current_levels.items(): 
            self.data_manager.user_progress[s_id] = val
        for key, widget in self.inventory_widgets.items():
            s_id, lvl, i_id = key
            val = widget.get_value()
            if val > 0: self.data_manager.user_progress.setdefault('hideout_inventory', {}).setdefault(s_id, {}).setdefault(str(lvl), {})[i_id] = val
        
        # Use DataManager's save method to preserve all progress data (including item_notes)
        self.data_manager.save_user_progress()

    def reload_data(self):
        """Reloads UI state from the current data_manager.user_progress."""
        # 1. Update station order
        self.station_order = self.data_manager.user_progress.get('hideout_station_order', [s['id'] for s in self.raw_hideout_data])
        
        # 2. Update Levels
        for sid in self.station_widgets.keys():
            self.station_current_levels[sid] = self.data_manager.user_progress.get(sid, 0)
            
        # 3. Update Inventory Widgets
        for key, widget in self.inventory_widgets.items():
            s_id, lvl, i_id = key
            val = self.data_manager.user_progress.get('hideout_inventory', {}).get(s_id, {}).get(str(lvl), {}).get(i_id, 0)
            widget.set_value(val)
            
        # 4. Update Expanded States
        expanded_states = self.data_manager.user_progress.get('hideout_station_expanded', {})
        for sid, widgets in self.station_widgets.items():
            is_expanded = expanded_states.get(sid, self.all_expanded)
            widgets['toggle_btn'].setChecked(is_expanded)
            
        self.refresh_ui()