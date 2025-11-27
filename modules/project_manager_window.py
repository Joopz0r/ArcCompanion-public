from PyQt6.QtWidgets import (QLabel, QPushButton, QFrame, QCheckBox, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
import json
import os
from .constants import Constants
from .ui_components import InventoryControl
from .base_manager_window import BaseManagerWindow

class ProjectManagerWindow(BaseManagerWindow):
    def __init__(self, project_data, user_progress, item_finder, rarity_colors):
        super().__init__()
        self.item_finder = item_finder
        self.rarity_colors = rarity_colors
        self.project_data = project_data
        self.user_progress = user_progress

        if 'projects' not in self.user_progress:
            self.user_progress['projects'] = {}
        
        self.inventory_widgets = {} 
        self.phase_frames = {} 
        
        self.chk_show_completed = QCheckBox("Show Completed")
        self.chk_show_completed.stateChanged.connect(self.refresh_visibility)
        self.top_bar_layout.addWidget(self.chk_show_completed)
        
        self.build_ui()

    def build_ui(self):
        for project in self.project_data:
            p_id = project.get('id')
            if not p_id: continue
            
            p_frame = QFrame()
            # Applies the Card Style + Orange Top Border from constants.py
            p_frame.setObjectName("ProjectFrame") 
            
            p_layout = QVBoxLayout(p_frame)
            p_layout.setContentsMargins(8, 8, 8, 8) 
            
            self.content_layout.addWidget(p_frame)
            
            # Project Header
            p_layout.addWidget(QLabel(project.get('name', ''), objectName="Header"))
            
            for phase_info in sorted(project.get('phases', []), key=lambda x: x.get('phase', 0)):
                phase_num = phase_info.get('phase', 0)
                reqs = phase_info.get('requirementItemIds', [])
                if not reqs: continue
                
                wrapper = QWidget()
                w_layout = QVBoxLayout(wrapper)
                w_layout.setContentsMargins(0, 10, 0, 10)
                w_layout.setSpacing(5)
                
                p_layout.addWidget(wrapper)
                self.phase_frames[(p_id, phase_num)] = wrapper
                
                # Phase Header Row
                h_row = QHBoxLayout()
                title_text = f"Phase {phase_num}: {phase_info.get('name', '')}"
                title = QLabel(title_text)
                title.setStyleSheet("font-weight: bold; border: none; font-size: 15px; color: #9DA5B4;")
                
                btn_complete = QPushButton("Complete")
                btn_complete.setFixedWidth(120)
                btn_complete.clicked.connect(lambda _, pid=p_id, pn=phase_num: self.toggle_phase_completion(pid, pn))
                
                h_row.addWidget(title)
                h_row.addStretch()
                h_row.addWidget(btn_complete)
                w_layout.addLayout(h_row)
                
                # Requirement Rows
                for req in reqs:
                    item_id, qty = req.get('itemId'), req.get('quantity', 0)
                    item_name = self.item_finder.id_to_name_map.get(item_id, "Unknown")
                    saved = self.user_progress.get('projects', {}).get(p_id, {}).get('inventory', {}).get(str(phase_num), {}).get(item_id, 0)
                    
                    row = QHBoxLayout()
                    item_obj = self.item_finder.get_item_by_name(item_name)
                    rarity = item_obj.get('rarity', 'Common') if item_obj else 'Common'
                    color = self.rarity_colors.get(rarity, "#E0E0E0")
                    
                    lbl = QLabel(item_name)
                    lbl.setStyleSheet(f"color: {color}; border: none;")
                    
                    ctrl = InventoryControl(saved, qty, show_extra_buttons=True)
                    ctrl.value_changed.connect(self.start_save_timer)
                    self.inventory_widgets[(p_id, phase_num, item_id)] = ctrl
                    
                    row.addWidget(lbl)
                    row.addStretch(1)
                    row.addWidget(ctrl)
                    w_layout.addLayout(row)
                
                wrapper.setProperty("btn_complete", btn_complete)
        
        self.refresh_visibility()

    def refresh_visibility(self):
        show_completed = self.chk_show_completed.isChecked()
        for (p_id, p_num), wrapper in self.phase_frames.items():
            progress = self.user_progress.get('projects', {}).get(p_id, {'completed_phase': 0})
            completed_phase = progress.get('completed_phase', 0)
            
            is_completed = p_num <= completed_phase
            is_next = p_num == completed_phase + 1
            
            btn = wrapper.property("btn_complete")
            btn.setStyleSheet("font-size: 11px;")
            
            if is_completed:
                wrapper.setVisible(show_completed)
                btn.setText("Re-Open")
                btn.setEnabled(True)
                btn.setObjectName("action_button_red") 
            else:
                wrapper.setVisible(True)
                btn.setText("Complete Phase")
                btn.setEnabled(is_next)
                
                if is_next:
                    btn.setObjectName("action_button_green")
                else:
                    btn.setObjectName("") 
            
            btn.style().polish(btn)

    def toggle_phase_completion(self, p_id, p_num):
        progress = self.user_progress['projects'].setdefault(p_id, {'completed_phase': 0, 'inventory': {}})
        curr = progress.get('completed_phase', 0)
        
        if p_num <= curr: 
            progress['completed_phase'] = p_num - 1
        elif p_num == curr + 1: 
            progress['completed_phase'] = p_num
            
        self.start_save_timer()
        self.refresh_visibility()

    def reset_project_progress_confirmation(self):
        msg = QMessageBox(); msg.setWindowTitle("Confirm Reset")
        msg.setText("Are you sure you want to completely reset ALL Expedition progress?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes: self.reset_project_progress()

    def reset_project_progress(self):
        self.user_progress['projects'] = {}
        for ctrl in self.inventory_widgets.values():
            ctrl.value = 0 
            ctrl.change(0) 
        self.start_save_timer()
        self.refresh_visibility()

    def save_progress(self):
        for (p_id, p_num, item_id), widget in self.inventory_widgets.items():
             inv_dict = self.user_progress.setdefault('projects', {}).setdefault(p_id, {}).setdefault('inventory', {})
             phase_dict = inv_dict.setdefault(str(p_num), {})
             val = widget.get_value()
             if val > 0:
                phase_dict[item_id] = val
             elif item_id in phase_dict:
                del phase_dict[item_id]
                
        try:
            with open(Constants.PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_progress, f, indent=2)
        except Exception as e: print(f"Error saving project progress: {e}")