from PyQt6.QtWidgets import (QLabel, QPushButton, QFrame, QMessageBox, QCheckBox, QVBoxLayout, QHBoxLayout, QWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
import json
import os
from .constants import Constants
from .ui_components import InventoryControl
from .base_manager_window import BaseManagerWindow

class HideoutManagerWindow(BaseManagerWindow):
    def __init__(self, hideout_data, user_progress, item_finder, rarity_colors):
        super().__init__()
        self.item_finder = item_finder
        self.rarity_colors = rarity_colors
        self.raw_hideout_data = hideout_data
        self.user_progress = user_progress
        
        if 'hideout_inventory' not in self.user_progress:
            self.user_progress['hideout_inventory'] = {}
        
        self.station_widgets = {} 
        self.inventory_widgets = {} 
        self.station_current_levels = {}

        self.station_order = self.user_progress.get('hideout_station_order', [s['id'] for s in self.raw_hideout_data])
        
        all_ids = [s['id'] for s in self.raw_hideout_data]
        for sid in all_ids:
            if sid not in self.station_order:
                self.station_order.append(sid)
        
        self.chk_show_all_reqs = QCheckBox("Show All Requirements")
        self.chk_show_all_reqs.stateChanged.connect(self.refresh_ui)
        self.top_bar_layout.addWidget(self.chk_show_all_reqs)
        self.top_bar_layout.addStretch()
        
        self.btn_toggle_all = QPushButton("Expand All")
        self.btn_toggle_all.clicked.connect(self.toggle_all)
        self.all_expanded = False
        
        self.button_layout.insertWidget(0, self.btn_toggle_all)
        
        self._create_all_station_widgets()
        self.refresh_ui()

    def _create_all_station_widgets(self):
        self.inventory_widgets = {} 
        self.station_widgets = {}

        for station in self.raw_hideout_data:
            station_id = station.get('id')
            if not station_id: continue
            
            station_frame = QFrame()
            # Assigning this ID applies the Card Style from constants.py
            station_frame.setObjectName("StationFrame") 
            
            s_layout = QVBoxLayout(station_frame)
            s_layout.setContentsMargins(4, 4, 4, 4)
            
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            
            btn_up = QPushButton("▲")
            btn_up.setObjectName("inv_button"); btn_up.setFixedSize(24, 24)
            btn_up.clicked.connect(lambda _, sid=station_id: self.move_station(sid, -1))
            
            btn_down = QPushButton("▼")
            btn_down.setObjectName("inv_button"); btn_down.setFixedSize(24, 24)
            btn_down.clicked.connect(lambda _, sid=station_id: self.move_station(sid, 1))
            
            header.addWidget(btn_up)
            header.addWidget(btn_down)
            
            name_lbl = QLabel(station.get('name', 'Unknown'), objectName="Header")
            # Override color slightly for Hideout Blue theme if desired, otherwise remove style
            name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #4476ED; border: none;")
            header.addWidget(name_lbl)
            header.addStretch()
            
            current_lvl = self.user_progress.get(station_id, 0)
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
            
            toggle_btn = QPushButton("▼") 
            toggle_btn.setCheckable(True)
            toggle_btn.setFixedSize(24, 24)
            toggle_btn.setObjectName("inv_button")
            toggle_btn.setChecked(self.all_expanded)
            header.addWidget(toggle_btn)

            s_layout.addLayout(header)

            levels_container = QWidget()
            levels_layout = QVBoxLayout(levels_container)
            levels_layout.setContentsMargins(4, 0, 0, 0) 
            levels_container.setVisible(self.all_expanded)
            
            toggle_btn.toggled.connect(levels_container.setVisible)
            toggle_btn.toggled.connect(lambda checked, b=toggle_btn: b.setText("▲" if checked else "▼"))
            
            s_layout.addWidget(levels_container)

            level_containers = {} 

            for level_info in sorted(station.get('levels', []), key=lambda x: x.get('level', 0)):
                lvl_num = level_info.get('level', 0)
                if lvl_num == 0: continue
                reqs = level_info.get('requirementItemIds', [])
                if not reqs: continue

                level_req_container = QWidget()
                level_req_layout = QVBoxLayout(level_req_container)
                level_req_layout.setContentsMargins(0, 5, 0, 5)
                levels_layout.addWidget(level_req_container)
                level_containers[lvl_num] = level_req_container

                lvl_header = QLabel(f"Level {lvl_num} Requirements:"); lvl_header.setStyleSheet("font-weight: bold; color: #9DA5B4; border: none;")
                level_req_layout.addWidget(lvl_header)
                
                for req in reqs:
                    item_id, qty_needed = req.get('itemId'), req.get('quantity', 0)
                    item_name = self.item_finder.id_to_name_map.get(item_id, "Unknown")
                    saved_qty = self.user_progress.get('hideout_inventory', {}).get(station_id, {}).get(str(lvl_num), {}).get(item_id, 0)
                    
                    row = QHBoxLayout()
                    item_obj = self.item_finder.get_item_by_name(item_name)
                    rarity = item_obj.get('rarity', 'Common') if item_obj else 'Common'
                    
                    lbl_name = QLabel(item_name)
                    lbl_name.setStyleSheet(f"color: {self.rarity_colors.get(rarity, '#E0E0E0')}; border: none;")
                    
                    row.addWidget(lbl_name); row.addStretch(1)
                    
                    ctrl = InventoryControl(saved_qty, qty_needed, show_extra_buttons=False) 
                    ctrl.value_changed.connect(self.start_save_timer)
                    self.inventory_widgets[(station_id, lvl_num, item_id)] = ctrl
                    
                    row.addWidget(ctrl)
                    level_req_layout.addLayout(row)

            self.station_widgets[station_id] = {
                'frame': station_frame,
                'btn_up': btn_up,
                'btn_down': btn_down,
                'lvl_lbl': lvl_lbl,
                'toggle_btn': toggle_btn,
                'level_containers': level_containers
            }

    def refresh_ui(self):
        sorted_ids = sorted(self.station_widgets.keys(), key=lambda sid: (
            sid != 'scrappy',
            self.station_order.index(sid) if sid in self.station_order else 999
        ))

        for i, sid in enumerate(sorted_ids):
            widgets = self.station_widgets[sid]
            self.content_layout.insertWidget(i, widgets['frame'])
            
            widgets['btn_up'].setEnabled(i > 0 and sid != 'scrappy') 
            widgets['btn_down'].setEnabled(i < len(sorted_ids) - 1)

            if widgets['lvl_lbl']:
                widgets['lvl_lbl'].setText(str(self.station_current_levels[sid]))

            show_all = self.chk_show_all_reqs.isChecked()
            curr_lvl = self.station_current_levels[sid]
            
            for lvl, container in widgets['level_containers'].items():
                is_visible = show_all or (lvl > curr_lvl)
                container.setVisible(is_visible)

    def move_station(self, station_id, direction):
        try: 
            current_index = self.station_order.index(station_id)
        except ValueError: return
        if station_id == 'scrappy': return 
        new_index = current_index + direction
        if 0 <= new_index < len(self.station_order):
            self.station_order.insert(new_index, self.station_order.pop(current_index))
            self.refresh_ui()
            self.start_save_timer()

    def change_station_level(self, station_id, delta, max_lvl):
        cur = self.station_current_levels[station_id]
        new_val = max(0, min(max_lvl, cur + delta))
        self.station_current_levels[station_id] = new_val
        self.refresh_ui() 
        self.start_save_timer()

    def toggle_all(self):
        self.all_expanded = not self.all_expanded
        self.btn_toggle_all.setText("Collapse All" if self.all_expanded else "Expand All")
        for widgets in self.station_widgets.values():
            widgets['toggle_btn'].setChecked(self.all_expanded)
            widgets['toggle_btn'].setText("▲" if self.all_expanded else "▼")

    def reset_hideout_progress_confirmation(self):
        msg = QMessageBox(); msg.setWindowTitle("Confirm Reset")
        msg.setText("Are you sure you want to completely reset ALL Hideout progress?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes: self.reset_hideout_progress()

    def reset_hideout_progress(self):
        self.user_progress['hideout_inventory'] = {}
        for sid in self.station_widgets.keys():
            self.station_current_levels[sid] = 0
            for key, widget in self.inventory_widgets.items():
                if key[0] == sid:
                    widget.value = 0
                    widget.change(0) 
        
        self.user_progress.pop('hideout_inventory', None)
        self.start_save_timer()
        self.refresh_ui()

    def save_progress(self):
        self.user_progress['hideout_station_order'] = self.station_order
        for s_id, val in self.station_current_levels.items(): 
            self.user_progress[s_id] = val
            
        for key, widget in self.inventory_widgets.items():
            s_id, lvl, i_id = key
            val = widget.get_value()
            if val > 0:
                self.user_progress.setdefault('hideout_inventory', {}).setdefault(s_id, {}).setdefault(str(lvl), {})[i_id] = val
                
        try:
            with open(Constants.PROGRESS_FILE, 'w', encoding='utf-8') as f: 
                json.dump(self.user_progress, f, indent=2)
        except Exception as e: print(f"Error saving hideout progress: {e}")