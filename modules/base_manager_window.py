from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea
from PyQt6.QtCore import QTimer, pyqtSignal

class BaseManagerWindow(QWidget):
    progress_saved = pyqtSignal()

    def __init__(self):
        super().__init__()

        # --- Auto-Save Timer ---
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(2000) 
        self.save_timer.timeout.connect(self._perform_save)

        # --- Main Layout Structure ---
        self.main_layout = QVBoxLayout(self)

        # Top Bar (Checkboxes, etc)
        self.top_bar_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_bar_layout)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        self.content_widget = QWidget()
        # FIX: Set ID so CSS can make it transparent
        self.content_widget.setObjectName("scroll_content") 
        
        self.content_layout = QVBoxLayout(self.content_widget)
        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll)

        # Bottom Buttons
        self.button_layout = QHBoxLayout()
        self.main_layout.addLayout(self.button_layout)
        self.button_layout.addStretch() 

    def start_save_timer(self):
        self.save_timer.start()

    def _perform_save(self):
        print("Auto-saving progress...")
        self.save_progress()
        self.progress_saved.emit() 

    def save_progress(self):
        raise NotImplementedError("Child classes must implement 'save_progress'.")

    def closeEvent(self, event):
        if self.save_timer.isActive():
            self.save_timer.stop()
            self._perform_save()
        super().closeEvent(event)

    def hideEvent(self, event):
        if self.save_timer.isActive():
            self.save_timer.stop()
            self._perform_save()
        super().hideEvent(event)