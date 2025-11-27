from PyQt6.QtWidgets import (QLabel, QPushButton, QFrame, QCheckBox, QMessageBox, QVBoxLayout, QHBoxLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
import json
import os
from .constants import Constants
from .base_manager_window import BaseManagerWindow

class QuestManagerWindow(BaseManagerWindow):
    def __init__(self, data_manager, user_progress):
        super().__init__()
        self.data_manager = data_manager
        self.user_progress = user_progress

        if 'quests' not in self.user_progress:
            self.user_progress['quests'] = {}
        
        self.quest_widgets = {} 
        self.all_quests_data = self.data_manager.get_filtered_quests() 
        
        all_quest_ids = [q.get('id') for q in self.all_quests_data]
        self.quest_order = self.user_progress.get('quest_order', all_quest_ids)
        for q_id in all_quest_ids:
            if q_id not in self.quest_order:
                self.quest_order.append(q_id)
        
        self.chk_show_completed = QCheckBox("Show Completed")
        self.chk_show_completed.stateChanged.connect(self.rebuild_and_refresh_ui)
        self.top_bar_layout.addWidget(self.chk_show_completed)

        self.build_all_widgets()
        self.rebuild_and_refresh_ui()

    def build_all_widgets(self):
        for quest in self.all_quests_data:
            q_id = quest.get('id')
            if not q_id: continue
            
            current_prog = self.user_progress['quests'].get(q_id, {})
            is_tracked_saved = current_prog.get('is_tracked', False)
            completed_objs_saved = current_prog.get('objectives_completed', [])

            frame = QFrame()
            # Applies the Card Style + Green Top Border from constants.py
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
            
            title = QLabel(quest.get('name', '')); 
            title.setStyleSheet("font-weight: bold; font-size: 16px; border: none; color: #E5C07B;")
            h_layout.addWidget(title); h_layout.addStretch()
            
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
                if obj_text in completed_objs_saved:
                    check_box.setChecked(True)
                check_box.stateChanged.connect(self.start_save_timer)
                
                text_label = QLabel(obj_text); text_label.setWordWrap(True)
                obj_layout.addWidget(check_box); obj_layout.addWidget(text_label, 1)
                layout.addLayout(obj_layout)
                obj_widgets.append({'text': obj_text, 'checkbox': check_box, 'label': text_label})
                
            self.quest_widgets[q_id] = {
                'frame': frame, 
                'title': title, 
                'track_chk': track_chk, 
                'done_btn': done_btn, 
                'objs': obj_widgets, 
                'btn_up': btn_up, 
                'btn_down': btn_down
            }
            done_btn.clicked.connect(lambda _, qid=q_id: self.toggle_done(qid))

    def rebuild_and_refresh_ui(self, _=None):
        for qid, widgets in self.quest_widgets.items():
            prog = self.user_progress['quests'].setdefault(qid, {})
            prog['is_tracked'] = widgets['track_chk'].isChecked()
            
        def sort_key(q_id):
            prog = self.user_progress['quests'].get(q_id, {})
            is_tracked = prog.get('is_tracked', False)
            is_completed = prog.get('quest_completed', False)
            order_index = self.quest_order.index(q_id) if q_id in self.quest_order else 999
            return (not is_tracked, order_index, is_completed)
            
        sorted_quest_ids = sorted(self.quest_widgets.keys(), key=sort_key)
        
        show_completed = self.chk_show_completed.isChecked()
        visible_tracked_ids = [qid for qid in sorted_quest_ids if self.user_progress['quests'].get(qid, {}).get('is_tracked', False) and (not self.user_progress['quests'].get(qid, {}).get('quest_completed', False) or show_completed)]
        
        for i, q_id in enumerate(sorted_quest_ids):
            widgets = self.quest_widgets[q_id]
            prog = self.user_progress['quests'].get(q_id, {})
            is_complete = prog.get('quest_completed', False)
            is_tracked = prog.get('is_tracked', False)
            
            self.content_layout.insertWidget(i, widgets['frame'])
            
            should_show = not is_complete or show_completed
            widgets['frame'].setVisible(should_show)

            widgets['btn_up'].setVisible(is_tracked)
            widgets['btn_down'].setVisible(is_tracked)
            
            if is_tracked and visible_tracked_ids:
                widgets['btn_up'].setEnabled(not (q_id == visible_tracked_ids[0]))
                widgets['btn_down'].setEnabled(not (q_id == visible_tracked_ids[-1]))
                
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
                if obj_widget['checkbox'].isChecked() != is_obj_complete:
                     obj_widget['checkbox'].setChecked(is_obj_complete)
                
                obj_widget['label'].setStyleSheet("color: #5C6370; text-decoration: line-through;" if is_obj_complete else "color: #E0E6ED;")

    def move_quest(self, quest_id, direction):
        tracked_quests = [q for q in self.quest_order if self.user_progress['quests'].get(q, {}).get('is_tracked', False)]
        
        if quest_id not in tracked_quests:
            return

        try:
            current_tracked_index = tracked_quests.index(quest_id)
        except ValueError:
            return

        new_tracked_index = current_tracked_index + direction
        
        if 0 <= new_tracked_index < len(tracked_quests):
            target_quest_id = tracked_quests[new_tracked_index]
            idx1 = self.quest_order.index(quest_id)
            idx2 = self.quest_order.index(target_quest_id)
            self.quest_order[idx1], self.quest_order[idx2] = self.quest_order[idx2], self.quest_order[idx1]
            self.rebuild_and_refresh_ui()
            self.start_save_timer()

    def toggle_done(self, q_id):
        prog = self.user_progress['quests'].setdefault(q_id, {})
        current_status = prog.get('quest_completed', False)
        prog['quest_completed'] = not current_status
        if prog['quest_completed']:
             prog['is_tracked'] = False
             self.quest_widgets[q_id]['track_chk'].setChecked(False)
        self.start_save_timer()
        self.rebuild_and_refresh_ui()

    def reset_quest_progress_confirmation(self):
        msg = QMessageBox(); msg.setWindowTitle("Confirm Reset")
        msg.setText("Are you sure you want to completely reset ALL Quest progress?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes: self.reset_quest_progress()

    def reset_quest_progress(self):
        self.user_progress['quests'] = {}
        self.quest_order = [q.get('id') for q in self.all_quests_data]
        self.user_progress['quest_order'] = self.quest_order
        for qid, widgets in self.quest_widgets.items():
            widgets['track_chk'].setChecked(False)
            for obj in widgets['objs']: obj['checkbox'].setChecked(False)
        self.start_save_timer()
        self.rebuild_and_refresh_ui()

    def save_progress(self):
        self.user_progress['quest_order'] = self.quest_order
        for q_id, widgets in self.quest_widgets.items():
            prog = self.user_progress['quests'].setdefault(q_id, {})
            prog['is_tracked'] = widgets['track_chk'].isChecked()
            prog['objectives_completed'] = [obj['text'] for obj in widgets['objs'] if obj['checkbox'].isChecked()]
        try:
            with open(Constants.PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_progress, f, indent=2)
        except Exception as e: print(f"Error saving quest progress: {e}")