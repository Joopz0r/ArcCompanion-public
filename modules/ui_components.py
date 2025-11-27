from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QProgressBar, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont

class TextProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        
        # --- FIXED: Removed setFixedSize(100, 30) to prevent clipping/rendering issues ---
        self.setMinimumWidth(80)
        self.setMaximumHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # --- END FIX ---

    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setBackgroundMode(Qt.BGMode.TransparentMode)
        
        font = QFont("Segoe UI")
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        
        text = f"{self.value()} / {self.maximum()}"
        
        # Since the size policy is now Expanding, the width is managed by the parent layout.
        # AlignCenter is still the correct way to center the text.
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()

class InventoryControl(QWidget):
    value_changed = pyqtSignal()

    def __init__(self, initial_val, max_val, show_extra_buttons=True):
        super().__init__()
        self.value = initial_val
        self.max_val = max_val
        
        # Prevent the parent layout from stretching/shrinking this whole control
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # Dimensions
        BTN_SIZE = 30
        BTN_FONT = "font-size: 16px; font-weight: bold; padding: 0px;"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        def make_btn(text, width=None):
            b = QPushButton(text)
            b.setFixedSize(width if width else BTN_SIZE, BTN_SIZE)
            b.setObjectName("inv_button")
            b.setStyleSheet(BTN_FONT)
            return b

        # -10 Button
        if show_extra_buttons:
            btn_m10 = make_btn("-10", 45)
            btn_m10.clicked.connect(lambda: self.change(-10))
            layout.addWidget(btn_m10)

        # -1 Button
        btn_m1 = make_btn("-")
        btn_m1.clicked.connect(lambda: self.change(-1))
        layout.addWidget(btn_m1)
        
        # --- Progress Bar ---
        self.pbar = TextProgressBar()
        self.pbar.setRange(0, self.max_val)
        self.pbar.setValue(self.value)
        self._update_style()
        layout.addWidget(self.pbar) # This widget now expands horizontally within the control
        
        # +1 Button
        btn_p1 = make_btn("+")
        btn_p1.clicked.connect(lambda: self.change(1))
        layout.addWidget(btn_p1)
        
        # +10 Button
        if show_extra_buttons:
            btn_p10 = make_btn("+10", 45)
            btn_p10.clicked.connect(lambda: self.change(10))
            layout.addWidget(btn_p10)

    def _update_style(self):
        is_complete = (self.value >= self.max_val)
        self.pbar.setProperty("complete", is_complete)
        self.pbar.style().polish(self.pbar)

    def change(self, amount):
        old_value = self.value
        self.value = max(0, min(self.max_val, self.value + amount))
        
        if self.value != old_value:
            self.pbar.setValue(self.value)
            self._update_style()
            self.value_changed.emit()

    def get_value(self): return self.value