from PyQt6.QtWidgets import (QLabel, QPushButton, QFrame, QCheckBox, QMessageBox, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox)
from PyQt6.QtCore import Qt
from modules.core.constants import Constants
from .base_page import BasePage

class QuestManagerWindow(BasePage):
    def __init__(self, data_manager, user_progress, lang_code="en"):
        super().__init__("Quest Manager")
        
        self.data_manager = data_manager
        # self.user_progress is now accessed directly via self.data_manager.user_progress
        self.lang_code = lang_code 

        if 'quests' not in self.data_manager.user_progress:
            self.data_manager.user_progress['quests'] = {}
        
        self.quest_widgets = {} 
        self.all_quests_data = self.data_manager.get_filtered_quests(lang_code=self.lang_code) 
        self.quest_data_map = {q.get('id'): q for q in self.all_quests_data}
        
        all_quest_ids = [q.get('id') for q in self.all_quests_data]
        self.quest_order = self.data_manager.user_progress.get('quest_order', all_quest_ids)
        for q_id in all_quest_ids:
            if q_id not in self.quest_order: self.quest_order.append(q_id)
        
        # Header Controls
        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Quests...")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self.rebuild_and_refresh_ui)
        self.header.add_widget(self.search_input)

        # Map Filter
        self.map_filter = QComboBox()
        self.map_filter.addItems(["ALL", "Dam Battlegrounds", "Buried City", "Spaceport", "Blue Gate", "Stella Montis"])
        self.map_filter.currentIndexChanged.connect(self.rebuild_and_refresh_ui)
        self.header.add_widget(self.map_filter)

        self.chk_show_completed = QCheckBox("Show Completed")
        self.chk_show_completed.stateChanged.connect(self.rebuild_and_refresh_ui)
        self.header.add_widget(self.chk_show_completed)

        self.build_all_widgets()
        self.content_layout.addStretch()
        self.rebuild_and_refresh_ui()

    def build_all_widgets(self):
        for quest in self.all_quests_data:
            q_id = quest.get('id')
            if not q_id: continue
            
            current_prog = self.data_manager.user_progress['quests'].get(q_id, {})
            is_tracked_saved = current_prog.get('is_tracked', False)
            completed_objs_saved = current_prog.get('objectives_completed', [])

            frame = QFrame()
            frame.setObjectName("QuestFrame") 
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(8, 8, 8, 8)
            h_layout = QHBoxLayout()
            
            reorder_layout = QVBoxLayout()
            btn_up = QPushButton("▲"); btn_up.setObjectName("inv_button"); btn_up.setFixedSize(28, 28)
            btn_up.clicked.connect(lambda _, qid=q_id: self.move_quest(qid, -1))
            btn_down = QPushButton("▼"); btn_down.setObjectName("inv_button"); btn_down.setFixedSize(28, 28)
            btn_down.clicked.connect(lambda _, qid=q_id: self.move_quest(qid, 1))
            reorder_layout.addWidget(btn_up); reorder_layout.addWidget(btn_down)
            h_layout.addLayout(reorder_layout)
            
            title_vbox = QVBoxLayout(); title_vbox.setSpacing(2)
            title = QLabel(quest.get('name', '')); 
            title.setStyleSheet("font-weight: bold; font-size: 16px; border: none; color: #E5C07B;")
            title_vbox.addWidget(title)
            
            map_names = self.data_manager.get_quest_map_names(quest, lang_code=self.lang_code)
            if map_names:
                map_str = ", ".join(map_names)
                map_lbl = QLabel(f"Map: {map_str}")
                map_lbl.setStyleSheet("color: #61AFEF; font-size: 12px; font-style: italic; border: none;")
                title_vbox.addWidget(map_lbl)
            
            h_layout.addLayout(title_vbox); h_layout.addStretch()
            
            track_chk = QCheckBox("Track")
            track_chk.setChecked(is_tracked_saved) 
            track_chk.stateChanged.connect(self.rebuild_and_refresh_ui)
            track_chk.stateChanged.connect(self.start_save_timer)
            
            done_btn = QPushButton("Done"); done_btn.setFixedWidth(80)
            h_layout.addWidget(track_chk); h_layout.addWidget(done_btn)
            layout.addLayout(h_layout)
            
            obj_widgets = []
            for obj_text in quest.get('objectives', []):
                obj_layout = QHBoxLayout(); obj_layout.setContentsMargins(20, 0, 0, 0)
                check_box = QCheckBox("")
                if obj_text in completed_objs_saved: check_box.setChecked(True)
                check_box.stateChanged.connect(self.start_save_timer)
                text_label = QLabel(obj_text); text_label.setWordWrap(True)
                # Ensure immediate visual update
                check_box.stateChanged.connect(lambda _, cb=check_box, lbl=text_label: lbl.setStyleSheet("color: #5C6370; text-decoration: line-through;" if cb.isChecked() else "color: #E0E6ED;"))
                obj_layout.addWidget(check_box); obj_layout.addWidget(text_label, 1)
                layout.addLayout(obj_layout)
                obj_widgets.append({'text': obj_text, 'checkbox': check_box, 'label': text_label})
                
            self.quest_widgets[q_id] = { 'frame': frame, 'title': title, 'track_chk': track_chk, 'done_btn': done_btn, 'objs': obj_widgets, 'btn_up': btn_up, 'btn_down': btn_down }
            done_btn.clicked.connect(lambda _, qid=q_id: self.toggle_done(qid))

    def rebuild_and_refresh_ui(self, _=None):
        for qid, widgets in self.quest_widgets.items():
            prog = self.data_manager.user_progress['quests'].setdefault(qid, {})
            prog['is_tracked'] = widgets['track_chk'].isChecked()
            prog['objectives_completed'] = [obj['text'] for obj in widgets['objs'] if obj['checkbox'].isChecked()]
            
        def sort_key(q_id):
            prog = self.data_manager.user_progress['quests'].get(q_id, {})
            is_tracked = prog.get('is_tracked', False)
            is_completed = prog.get('quest_completed', False)
            order_index = self.quest_order.index(q_id) if q_id in self.quest_order else 999
            return (not is_tracked, order_index, is_completed)
            
        sorted_quest_ids = sorted(self.quest_widgets.keys(), key=sort_key)
        show_completed = self.chk_show_completed.isChecked()
        
        search_text = self.search_input.text().lower()
        selected_map = self.map_filter.currentText()
        
        map_filter_map = {
            "Dam Battlegrounds": ["dam_battlegrounds"],
            "Buried City": ["buried_city"],
            "Spaceport": ["the_spaceport"],
            "Blue Gate": ["the_blue_gate"],
            "Stella Montis": ["stella_montis_upper", "stella_montis_lower", "stella_montis"]
        }
        
        visible_tracked_ids = []
        
        for i, q_id in enumerate(sorted_quest_ids):
            widgets = self.quest_widgets[q_id]
            prog = self.data_manager.user_progress['quests'].get(q_id, {})
            is_complete = prog.get('quest_completed', False)
            is_tracked = prog.get('is_tracked', False)
            
            # Filter Check
            quest_data = self.quest_data_map.get(q_id)
            quest_name = quest_data.get('name', '').lower() if quest_data else ''
            quest_maps = quest_data.get('map', []) if quest_data else []
            if isinstance(quest_maps, str): quest_maps = [quest_maps]
            
            matches_search = search_text in quest_name
            matches_map = True
            if selected_map != "ALL":
                target_maps = map_filter_map.get(selected_map, [])
                matches_map = any(m in target_maps for m in quest_maps)
            
            should_show = (not is_complete or show_completed) and matches_search and matches_map
            
            self.content_layout.insertWidget(i, widgets['frame'])
            widgets['frame'].setVisible(should_show)
            
            if should_show and is_tracked:
                visible_tracked_ids.append(q_id)
                
            widgets['btn_up'].setVisible(is_tracked)
            widgets['btn_down'].setVisible(is_tracked)
                
            done_btn = widgets['done_btn']
            if is_complete:
                widgets['title'].setStyleSheet("color: #5C6370; font-weight: bold; font-size: 16px; border: none; text-decoration: line-through;")
                done_btn.setText("Re-Open"); done_btn.setObjectName("action_button_red")
                widgets['track_chk'].setVisible(False)
            else:
                widgets['title'].setStyleSheet("color: #E5C07B; font-weight: bold; font-size: 16px; border: none;")
                done_btn.setText("Done"); done_btn.setObjectName("action_button_green")
                widgets['track_chk'].setVisible(True)
            done_btn.style().polish(done_btn)
            
            completed_objs = prog.get('objectives_completed', [])
            for obj_widget in widgets['objs']:
                is_obj_complete = obj_widget['text'] in completed_objs
                if obj_widget['checkbox'].isChecked() != is_obj_complete: obj_widget['checkbox'].setChecked(is_obj_complete)
                obj_widget['label'].setStyleSheet("color: #5C6370; text-decoration: line-through;" if is_obj_complete else "color: #E0E6ED;")

        for q_id in visible_tracked_ids:
            widgets = self.quest_widgets[q_id]
            widgets['btn_up'].setEnabled(not (q_id == visible_tracked_ids[0]))
            widgets['btn_down'].setEnabled(not (q_id == visible_tracked_ids[-1]))

    def move_quest(self, quest_id, direction):
        tracked_quests = [q for q in self.quest_order if self.data_manager.user_progress['quests'].get(q, {}).get('is_tracked', False)]
        if quest_id not in tracked_quests: return
        try: current_tracked_index = tracked_quests.index(quest_id)
        except ValueError: return
        new_tracked_index = current_tracked_index + direction
        if 0 <= new_tracked_index < len(tracked_quests):
            target_quest_id = tracked_quests[new_tracked_index]
            idx1 = self.quest_order.index(quest_id); idx2 = self.quest_order.index(target_quest_id)
            self.quest_order[idx1], self.quest_order[idx2] = self.quest_order[idx2], self.quest_order[idx1]
            self.rebuild_and_refresh_ui(); self.start_save_timer()

    def toggle_done(self, q_id):
        prog = self.data_manager.user_progress['quests'].setdefault(q_id, {})
        current_status = prog.get('quest_completed', False)
        prog['quest_completed'] = not current_status
        if prog['quest_completed']:
             prog['is_tracked'] = False
             self.quest_widgets[q_id]['track_chk'].setChecked(False)
        self.start_save_timer(); self.rebuild_and_refresh_ui()

    def confirm_reset(self):
        msg = QMessageBox(self); msg.setWindowTitle("Confirm Reset")
        msg.setText("Are you sure you want to completely reset ALL Quest progress?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes: self.reset_state()

    # --- BASE PAGE OVERRIDES ---
    def reset_state(self):
        self.data_manager.user_progress['quests'] = {}
        self.quest_order = [q.get('id') for q in self.all_quests_data]
        self.data_manager.user_progress['quest_order'] = self.quest_order
        for qid, widgets in self.quest_widgets.items():
            widgets['track_chk'].setChecked(False)
            for obj in widgets['objs']: obj['checkbox'].setChecked(False)
        self.start_save_timer(); self.rebuild_and_refresh_ui()

    def save_state(self):
        self.data_manager.user_progress['quest_order'] = self.quest_order
        for q_id, widgets in self.quest_widgets.items():
            prog = self.data_manager.user_progress['quests'].setdefault(q_id, {})
            prog['is_tracked'] = widgets['track_chk'].isChecked()
            prog['objectives_completed'] = [obj['text'] for obj in widgets['objs'] if obj['checkbox'].isChecked()]
        
        # Use DataManager's save method to preserve all progress data (including item_notes)
        self.data_manager.save_user_progress()

    def reload_data(self):
        """Reloads UI state from the current data_manager.user_progress."""
        self.quest_order = self.data_manager.user_progress.get('quest_order', [])
        # Fallback if empty or missing ids
        all_ids = [q.get('id') for q in self.all_quests_data]
        if not self.quest_order: 
            self.quest_order = all_ids
        for q_id in all_ids:
            if q_id not in self.quest_order: self.quest_order.append(q_id)
            
        # Update widgets WITHOUT triggering the write-back in rebuild_and_refresh_ui
        # We update the widgets to match the data, then call rebuild which will sync them back (no-op effectively)
        for q_id, widgets in self.quest_widgets.items():
            prog = self.data_manager.user_progress['quests'].get(q_id, {})
            
            # Update Track Checkbox (block signals to prevent auto-save triggering)
            widgets['track_chk'].blockSignals(True)
            widgets['track_chk'].setChecked(prog.get('is_tracked', False))
            widgets['track_chk'].blockSignals(False)
            
            # Update Objectives
            comp_objs = prog.get('objectives_completed', [])
            for obj in widgets['objs']:
                obj['checkbox'].blockSignals(True)
                obj['checkbox'].setChecked(obj['text'] in comp_objs)
                obj['checkbox'].blockSignals(False)
                
                # Manually trigger style update
                is_checked = obj['checkbox'].isChecked()
                obj['label'].setStyleSheet("color: #5C6370; text-decoration: line-through;" if is_checked else "color: #E0E6ED;")

        self.rebuild_and_refresh_ui()