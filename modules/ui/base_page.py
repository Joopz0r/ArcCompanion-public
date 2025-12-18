from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QHBoxLayout
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from .ui_components import PageHeader

class BasePage(QWidget):
    """
    Standard page structure: 
    - Top: PageHeader (Uniform size and styling)
    - Middle: Scrollable Content
    - Bottom: Optional Footer (Buttons)
    - Auto-Save capabilities built-in.
    """
    progress_saved = pyqtSignal()

    def __init__(self, title_text, parent=None):
        super().__init__(parent)

        # Auto-Save Timer
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(2000) 
        self.save_timer.timeout.connect(self._perform_save)

        # Main Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Header (Standardized)
        self.header = PageHeader(title_text)
        self.main_layout.addWidget(self.header)

        # 2. Scroll Area (Flexible content)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        # Remove border from scroll area to blend in
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("scroll_content") 
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20) # Standard padding for content
        self.content_layout.setSpacing(15)
        
        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll)

        # 3. Footer (Optional)
        self.footer_layout = QHBoxLayout()
        self.footer_layout.setContentsMargins(20, 10, 20, 10)
        self.main_layout.addLayout(self.footer_layout)

    def start_save_timer(self):
        """Call this whenever data changes to trigger a delayed save."""
        self.save_timer.start()

    def _perform_save(self):
        """Internal method called by timer."""
        self.save_state()
        self.progress_saved.emit() 

    def save_state(self):
        """Override this to save data to disk."""
        pass

    def reset_state(self):
        """Override this to reset data to defaults."""
        pass

    # Lifecycle Hooks
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