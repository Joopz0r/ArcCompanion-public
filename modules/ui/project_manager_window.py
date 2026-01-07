from PyQt6.QtWidgets import (QLabel, QPushButton, QFrame, QCheckBox, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy, QTabWidget, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from modules.core.constants import Constants
from .ui_components import InventoryControl, TextProgressBar
from .base_page import BasePage

class CategoryProgressBar(TextProgressBar):
    """
    A specialized progress bar that formats numbers with commas (e.g. 10,000 / 50,000)
    but maintains the exact look of the standard Item ProgressBar.
    """
    def paintEvent(self, event):
        # Standard QProgressBar paint
        super(TextProgressBar, self).paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setBackgroundMode(Qt.BGMode.TransparentMode)
        
        # Match font from ui_components
        font = QFont("Segoe UI")
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        
        # Formatting with commas
        text = f"{self.value():,} / {self.maximum():,}"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

class CategoryValueControl(QWidget):

    value_changed = pyqtSignal()
    
    def __init__(self, current_value=0, required_value=0):
        super().__init__()
        self.current_value = current_value
        self.required_value = required_value
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 1. -10k Button (Matches -10 size/style)
        self.btn_minus_10k = QPushButton("-10k")
        self.btn_minus_10k.setFixedSize(45, 30)
        self.btn_minus_10k.setObjectName("inv_button")
        self.btn_minus_10k.setStyleSheet("font-size: 11px; padding: 0px;")
        self.btn_minus_10k.clicked.connect(lambda: self.increment_value(-10000))
        layout.addWidget(self.btn_minus_10k)
        
        # 2. Minus Button (Matches - size/style)
        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedSize(30, 30)
        self.btn_minus.setObjectName("inv_button")
        self.btn_minus.clicked.connect(lambda: self.increment_value(-1))
        layout.addWidget(self.btn_minus)

        # 3. Progress Bar
        self.pbar = CategoryProgressBar()
        self.pbar.setRange(0, self.required_value)
        self.pbar.setValue(self.current_value)
        self._update_style()
        layout.addWidget(self.pbar)
        
        # 4. +1 Button (Matches + size/style)
        self.btn_plus_1 = QPushButton("+1")
        self.btn_plus_1.setFixedSize(30, 30)
        self.btn_plus_1.setObjectName("inv_button")
        self.btn_plus_1.clicked.connect(lambda: self.increment_value(1))
        layout.addWidget(self.btn_plus_1)
        
        # 5. +10k Button (Matches +10 size/style)
        self.btn_plus_10k = QPushButton("+10k")
        self.btn_plus_10k.setFixedSize(45, 30)
        self.btn_plus_10k.setObjectName("inv_button")
        self.btn_plus_10k.setStyleSheet("font-size: 11px; padding: 0px;")
        self.btn_plus_10k.clicked.connect(lambda: self.increment_value(10000))
        layout.addWidget(self.btn_plus_10k)
    
    def increment_value(self, amount):
        """Increment the current value by the specified amount."""
        self.current_value = max(0, self.current_value + amount)
        self.pbar.setValue(self.current_value)
        self._update_style()
        self.value_changed.emit()
    
    def _update_style(self):
        # Turns the bar green if complete, just like InventoryControl
        is_complete = (self.current_value >= self.required_value)
        self.pbar.setProperty("complete", is_complete)
        self.pbar.style().polish(self.pbar)
    
    def get_value(self):
        """Get the current value."""
        return self.current_value
    
    def set_value(self, value):
        """Set the current value."""
        self.current_value = value
        self.pbar.setValue(self.current_value)
        self._update_style()
        self.value_changed.emit()


class ProjectManagerWindow(BasePage):
    def __init__(self, project_data, user_progress, data_manager, rarity_colors, lang_code="en"):
        super().__init__("Projects Manager")
        self.data_manager = data_manager
        self.rarity_colors = rarity_colors
        self.project_data = project_data
        self.lang_code = lang_code 

        # self.user_progress is now accessed directly via self.data_manager.user_progress
        
        if 'projects' not in self.data_manager.user_progress:
            self.data_manager.user_progress['projects'] = {}
        
        self.inventory_widgets = {} 
        self.category_widgets = {}  # For category value tracking
        self.phase_frames = {} 
        
        self.chk_show_completed = QCheckBox("Show Completed")
        self.chk_show_completed.stateChanged.connect(self.refresh_visibility)
        self.header.add_widget(self.chk_show_completed)
        
        # Replace BasePage scroll with Tabs
        self.main_layout.removeWidget(self.scroll)
        self.scroll.setParent(None)
        
        self.tabs = QTabWidget()
        # Restore the gold/orange top border to the tab content area, matching previous Project styling
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #333;
                border-top: 3px solid #ED9A44;
                border-radius: 4px;
                background-color: #1A1F2B;
            }
        """)
        self.main_layout.insertWidget(1, self.tabs) # Insert after header

        self.build_ui()

    def build_ui(self):
        for project in self.project_data:
            p_id = project.get('id')
            if not p_id: continue
            
            p_name = self.data_manager.get_localized_name(project, self.lang_code)
            
            # Create a tab for this project
            tab_widget = QWidget()
            tab_widget.setStyleSheet("background-color: transparent;")
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            
            # Scroll Area for the tab
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            tab_layout.addWidget(scroll)
            
            content_widget = QWidget()
            content_widget.setObjectName("scroll_content")
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(20, 20, 20, 20)
            content_layout.setSpacing(15)
            scroll.setWidget(content_widget)
            
            self.tabs.addTab(tab_widget, p_name)
            
            # Add Project Title inside the tab as well
            content_layout.addWidget(QLabel(p_name, objectName="Header"))
            
            for phase_info in sorted(project.get('phases', []), key=lambda x: x.get('phase', 0)):
                phase_num = phase_info.get('phase', 0)
                item_reqs = phase_info.get('requirementItemIds', [])
                category_reqs = phase_info.get('requirementCategories', [])
                
                # Skip phases with no requirements at all
                if not item_reqs and not category_reqs:
                    continue
                
                wrapper = QWidget()
                w_layout = QVBoxLayout(wrapper)
                w_layout.setContentsMargins(0, 10, 0, 10)
                w_layout.setSpacing(5)
                content_layout.addWidget(wrapper)
                self.phase_frames[(p_id, phase_num)] = wrapper
                
                phase_name = phase_info.get('name')
                if isinstance(phase_name, dict):
                    phase_name = phase_name.get(self.lang_code, phase_name.get('en', ''))
                elif not isinstance(phase_name, str):
                    phase_name = ""
                    
                h_row = QHBoxLayout()
                title_text = f"Phase {phase_num}: {phase_name}"
                title = QLabel(title_text)
                title.setStyleSheet("font-weight: bold; border: none; font-size: 15px; color: #9DA5B4;")
                
                btn_complete = QPushButton("Complete")
                btn_complete.setFixedWidth(120)
                btn_complete.clicked.connect(lambda _, pid=p_id, pn=phase_num: self.toggle_phase_completion(pid, pn))
                
                h_row.addWidget(title)
                h_row.addStretch()
                h_row.addWidget(btn_complete)
                w_layout.addLayout(h_row)
                
                # Add description if it exists (for Phase 5)
                description = phase_info.get('description')
                if description:
                    if isinstance(description, dict):
                        desc_text = description.get(self.lang_code, description.get('en', ''))
                    else:
                        desc_text = description
                    if desc_text:
                        desc_label = QLabel(desc_text)
                        desc_label.setWordWrap(True)
                        desc_label.setStyleSheet("color: #ABB2BF; border: none; font-size: 12px; margin-top: 5px; margin-bottom: 10px;")
                        w_layout.addWidget(desc_label)
                
                # Handle item-based requirements
                if item_reqs:
                    for req in item_reqs:
                        item_id, qty = req.get('itemId'), req.get('quantity', 0)
                        item_name = self.data_manager.get_localized_name(item_id, self.lang_code)
                        saved = self.data_manager.user_progress.get('projects', {}).get(p_id, {}).get('inventory', {}).get(str(phase_num), {}).get(item_id, 0)
                        
                        row = QHBoxLayout()
                        item_obj = self.data_manager.id_to_item_map.get(item_id)
                        rarity = item_obj.get('rarity', 'Common') if item_obj else 'Common'
                        color = self.rarity_colors.get(rarity, "#E0E0E0")
                        
                        lbl = QLabel(item_name)
                        lbl.setStyleSheet(f"color: {color}; border: none;")
                        ctrl = InventoryControl(saved, qty, show_extra_buttons=True)
                        # Connect to sync method that updates user_progress immediately
                        ctrl.value_changed.connect(lambda pid=p_id, pn=phase_num, iid=item_id: self._on_inventory_changed(pid, pn, iid))
                        self.inventory_widgets[(p_id, phase_num, item_id)] = ctrl
                        
                        row.addWidget(lbl)
                        row.addStretch(1)
                        row.addWidget(ctrl)
                        w_layout.addLayout(row)
                
                # Handle category-based requirements (Phase 5)
                if category_reqs:
                    for cat_req in category_reqs:
                        category_name = cat_req.get('category', '')
                        value_required = cat_req.get('valueRequired', 0)
                        saved_value = self.data_manager.user_progress.get('projects', {}).get(p_id, {}).get('categories', {}).get(str(phase_num), {}).get(category_name, 0)
                        
                        row = QHBoxLayout()
                        
                        # Category label - styled like item names but Gold color
                        lbl = QLabel(category_name)
                        lbl.setStyleSheet("color: #E5C07B; border: none;")
                        row.addWidget(lbl)
                        
                        row.addStretch(1)
                        
                        # Category value control - now consistent with InventoryControl
                        ctrl = CategoryValueControl(saved_value, value_required)
                        # Connect to sync method that updates user_progress immediately
                        ctrl.value_changed.connect(lambda pid=p_id, pn=phase_num, cn=category_name: self._on_category_changed(pid, pn, cn))
                        self.category_widgets[(p_id, phase_num, category_name)] = ctrl
                        
                        row.addWidget(ctrl)
                        w_layout.addLayout(row)
                
                wrapper.setProperty("btn_complete", btn_complete)
            
            # Add a vertical stretch to each project's content_layout.
            # This ensures that if some phases are hidden, the remaining content
            # is pushed to the top instead of stretching to fill the whole box.
            content_layout.addStretch()
        
        self.refresh_visibility()

    def _on_inventory_changed(self, p_id, phase_num, item_id):
        """Called when an inventory control value changes - syncs to user_progress immediately."""
        widget = self.inventory_widgets.get((p_id, phase_num, item_id))
        if widget:
            val = widget.get_value()
            # Update user_progress immediately so overlay shows current values
            inv_dict = self.data_manager.user_progress.setdefault('projects', {}).setdefault(p_id, {}).setdefault('inventory', {})
            phase_dict = inv_dict.setdefault(str(phase_num), {})
            if val > 0:
                phase_dict[item_id] = val
            elif item_id in phase_dict:
                del phase_dict[item_id]
        # Start save timer to persist to disk
        self.start_save_timer()

    def _on_category_changed(self, p_id, phase_num, category_name):
        """Called when a category control value changes - syncs to user_progress immediately."""
        widget = self.category_widgets.get((p_id, phase_num, category_name))
        if widget:
            val = widget.get_value()
            # Update user_progress immediately so overlay shows current values
            cat_dict = self.data_manager.user_progress.setdefault('projects', {}).setdefault(p_id, {}).setdefault('categories', {})
            phase_dict = cat_dict.setdefault(str(phase_num), {})
            if val > 0:
                phase_dict[category_name] = val
            elif category_name in phase_dict:
                del phase_dict[category_name]
        # Start save timer to persist to disk
        self.start_save_timer()

    def refresh_visibility(self):
        show_completed = self.chk_show_completed.isChecked()
        for (p_id, p_num), wrapper in self.phase_frames.items():
            progress = self.data_manager.user_progress.get('projects', {}).get(p_id, {'completed_phase': 0})
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
        progress = self.data_manager.user_progress['projects'].setdefault(p_id, {'completed_phase': 0, 'inventory': {}, 'categories': {}})
        curr = progress.get('completed_phase', 0)
        if p_num <= curr:
            progress['completed_phase'] = p_num - 1
        elif p_num == curr + 1:
            progress['completed_phase'] = p_num
        self.start_save_timer()
        self.refresh_visibility()

    def confirm_reset(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Reset")
        msg.setText("Are you sure you want to completely reset ALL Expedition progress?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.reset_state()

    # --- BASE PAGE OVERRIDES ---
    def reset_state(self):
        self.data_manager.user_progress['projects'] = {}
        for ctrl in self.inventory_widgets.values():
            ctrl.set_value(0) 
        for ctrl in self.category_widgets.values():
            ctrl.set_value(0)
        self.start_save_timer()
        self.refresh_visibility()

    def save_state(self):
        # Sync all current widget values to user_progress (in case any were missed)
        for (p_id, p_num, item_id), widget in self.inventory_widgets.items():
             inv_dict = self.data_manager.user_progress.setdefault('projects', {}).setdefault(p_id, {}).setdefault('inventory', {})
             phase_dict = inv_dict.setdefault(str(p_num), {})
             val = widget.get_value()
             if val > 0:
                 phase_dict[item_id] = val
             elif item_id in phase_dict:
                 del phase_dict[item_id]
        
        # Save category values
        for (p_id, p_num, category_name), widget in self.category_widgets.items():
            cat_dict = self.data_manager.user_progress.setdefault('projects', {}).setdefault(p_id, {}).setdefault('categories', {})
            phase_dict = cat_dict.setdefault(str(p_num), {})
            val = widget.get_value()
            if val > 0:
                phase_dict[category_name] = val
            elif category_name in phase_dict:
                del phase_dict[category_name]
        
        # Use DataManager's save method to preserve all progress data (including item_notes)
        self.data_manager.save_user_progress()

    def reload_data(self):
        """Reloads UI state from the current data_manager.user_progress."""
        # 1. Update Inventory Widgets
        for (p_id, p_num, item_id), widget in self.inventory_widgets.items():
            val = self.data_manager.user_progress.get('projects', {}).get(p_id, {}).get('inventory', {}).get(str(p_num), {}).get(item_id, 0)
            widget.set_value(val)
            
        # 2. Update Category Widgets
        for (p_id, p_num, category_name), widget in self.category_widgets.items():
            val = self.data_manager.user_progress.get('projects', {}).get(p_id, {}).get('categories', {}).get(str(p_num), {}).get(category_name, 0)
            widget.set_value(val)
            
        # 3. Refresh Phases visibility (which checks completed_phase)
        self.refresh_visibility()