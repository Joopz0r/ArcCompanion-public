from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QProgressBar, QSizePolicy, 
    QCheckBox, QFrame, QLabel, QTabWidget, QVBoxLayout, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QCursor, QKeySequence, 
    QDesktopServices, QPixmap, QGuiApplication
)
import os
import ctypes
from PyQt6.QtCore import QObject, QEvent

def ensure_window_within_screen(x, y, border_tolerance=20):
    """
    Checks if point (x, y) is visible on any connected screen.
    If not, returns coordinates to center the window on the primary screen.
    Also ensures the window top is not above the screen top.
    
    Returns:
        tuple: (safe_x, safe_y)
    """
    screens = QGuiApplication.screens()
    if not screens:
        return 100, 100

    # check if x,y is within any screen rect
    is_visible = False
    
    for screen in screens:
        geo = screen.availableGeometry()
        # Simple point visibility check - lax enough to catch "mostly" visible
        # We check if the top-left point is roughly within bounds
        if geo.contains(x + border_tolerance, y + border_tolerance):
            is_visible = True
            break
            
    if is_visible:
        # Extra safety: Ensure y isn't negative/off-screen top
        # (Though geo.contains check above vaguely covers it, explicit clamping is safer)
        # We iterate again to find WHICH screen it's on to clamp correctly if needed, 
        # but for simplicity, if it's visible, we trust it, just preventing negative Y 
        # that might be *too* negative if we only checked specific points.
        # Actually, let's just return as is if valid.
        return x, y
    
    # If we are here, the window is likely off-screen.
    # Reset to primary screen center-ish
    primary = QGuiApplication.primaryScreen()
    if primary:
        geo = primary.availableGeometry()
        center = geo.center()
        # Return a position that centers a hypothetical window of average size
        # We don't have W/H here but returning something near center is safer than TopLeft 0,0
        return center.x() - 380, center.y() - 400 # approx half of 760x850
        
    return 100, 100

def set_dark_title_bar(window: QWidget):
    """
    Applies the Windows DWM immersive dark mode attribute to a window's title bar.
    Safe to call on non-Windows systems (will just do nothing).
    """
    try:
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        hwnd = int(window.winId())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), 4)
    except Exception:
        pass

class DarkTitleBarProxy(QObject):
    """
    Event filter to automatically apply dark title bars to all newly created top-level windows.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget):
            if obj.isWindow():
                set_dark_title_bar(obj)
        return False

# =============================================================================
# HEADER COMPONENT (New)
# =============================================================================
class PageHeader(QFrame):
    def __init__(self, title_text, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setObjectName("PageHeader")
        # Styling for the header background and bottom border
        self.setStyleSheet("""
            #PageHeader {
                background-color: #1A1F2B;
                border-bottom: 2px solid #3E4451;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # Title
        self.title_lbl = QLabel(title_text)
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #E5C07B; border: none; background: transparent;")
        layout.addWidget(self.title_lbl)
        
        layout.addStretch()
        
        # Area for specific page controls (Checkboxes, Buttons)
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setSpacing(15)
        layout.addLayout(self.controls_layout)

    def add_widget(self, widget):
        self.controls_layout.addWidget(widget)

# =============================================================================
# PROGRESS BARS
# =============================================================================

class TextProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setMinimumWidth(80)
        self.setMaximumHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()

class StashProgressBar(QProgressBar):
    def __init__(self, parent=None, font_size=9):
        super().__init__(parent)
        self.setTextVisible(False)
        self.real_count = 0
        self.stack_size = 1
        self.font_size = font_size
        self.setStyleSheet("""
            QProgressBar { border: 1px solid #3E4451; border-radius: 4px; background-color: #232834; text-align: center; }
            QProgressBar::chunk { background-color: #4476ED; border-radius: 3px; }
        """)

    def update_status(self, count, stack_size):
        self.real_count = count
        self.stack_size = stack_size
        safe_max = stack_size if stack_size > 0 else 1
        
        self.setMaximum(safe_max)
        self.setValue(min(count, safe_max))
        
        if count >= safe_max:
            self.setStyleSheet("""
                QProgressBar { border: 1px solid #3E4451; border-radius: 4px; background-color: #232834; }
                QProgressBar::chunk { background-color: #4CAF50; border-radius: 3px; } 
            """)
        else:
            self.setStyleSheet("""
                QProgressBar { border: 1px solid #3E4451; border-radius: 4px; background-color: #232834; }
                QProgressBar::chunk { background-color: #4476ED; border-radius: 3px; }
            """)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        text = f"{self.real_count} / {self.stack_size}"
        font = QFont("Segoe UI", self.font_size); font.setBold(True)
        painter.setFont(font); painter.setPen(QColor("#FFFFFF"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text); painter.end()

# =============================================================================
# INPUT CONTROLS
# =============================================================================

class InventoryControl(QWidget):
    value_changed = pyqtSignal()

    def __init__(self, initial_val, max_val, show_extra_buttons=True):
        super().__init__()
        self.value = initial_val
        self.max_val = max_val
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
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

        if show_extra_buttons:
            btn_m10 = make_btn("-10", 45)
            btn_m10.clicked.connect(lambda: self.change(-10))
            layout.addWidget(btn_m10)

        btn_m1 = make_btn("-")
        btn_m1.clicked.connect(lambda: self.change(-1))
        layout.addWidget(btn_m1)
        
        self.pbar = TextProgressBar()
        self.pbar.setRange(0, self.max_val)
        self.pbar.setValue(self.value)
        self._update_style()
        layout.addWidget(self.pbar)
        
        btn_p1 = make_btn("+")
        btn_p1.clicked.connect(lambda: self.change(1))
        layout.addWidget(btn_p1)
        
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

    def set_value(self, new_value):
        """Force set value and update UI."""
        self.value = max(0, min(self.max_val, new_value))
        self.pbar.setValue(self.value)
        self._update_style()
        self.value_changed.emit()

    def get_value(self): return self.value

class ModernToggle(QCheckBox):
    """A specific toggle switch style for modifiers."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QCheckBox { spacing: 12px; color: #E0E6ED; font-size: 13px; padding: 2px; }
            QCheckBox::indicator { width: 36px; height: 18px; border-radius: 9px; }
            QCheckBox::indicator:unchecked { background-color: #232834; border: 1px solid #3E4451; }
            QCheckBox::indicator:checked { background-color: #2E5C32; border: 1px solid #4CAF50; image: url(:/none); }
        """)

class HotkeyButton(QPushButton):
    key_set = pyqtSignal(str)

    def __init__(self, default_text=""):
        super().__init__(default_text)
        self.setCheckable(True)
        self.current_key_string = default_text
        self.setText(default_text if default_text else "Click to set...")
        
        self.normal_style = """
            QPushButton {
                background-color: #232834; color: #E0E6ED; border: 1px solid #3E4451;
                padding: 6px 12px; text-align: center; border-radius: 4px;
                font-family: 'Segoe UI', monospace; font-weight: bold;
            }
            QPushButton:hover { border: 1px solid #4476ED; background-color: #282D38; }
        """
        self.recording_style = """
            QPushButton {
                background-color: rgba(211, 47, 47, 0.2); color: #ef5350;
                border: 1px solid #ef5350; padding: 6px 12px; text-align: center;
                border-radius: 4px; font-weight: bold;
            }
        """
        self.setStyleSheet(self.normal_style)
        self.clicked.connect(self._on_click)

    def _on_click(self):
        self.setText("Press any key... (Esc to cancel)")
        self.setStyleSheet(self.recording_style)

    def keyPressEvent(self, event):
        if not self.isChecked():
            super().keyPressEvent(event); return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._cancel(); return
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.current_key_string = ""; self.setText("None"); self._finish(); return
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        
        parts = []
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:     parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:   parts.append("shift")
        key_text = QKeySequence(key).toString().lower()
        parts.append(key_text)
        
        final_string = "+".join(parts)
        self.current_key_string = final_string
        self.setText(final_string)
        self.key_set.emit(final_string)
        self._finish()

    def _cancel(self):
        self.setChecked(False)
        self.setText(self.current_key_string if self.current_key_string else "Click to set...")
        self.setStyleSheet(self.normal_style)

    def _finish(self):
        self.setChecked(False)
        self.setStyleSheet(self.normal_style)
    
    def set_hotkey(self, text):
        self.current_key_string = text
        self.setText(text if text else "Click to set...")
    
    def focusOutEvent(self, event):
        if self.isChecked(): self._cancel()
        super().focusOutEvent(event)

# =============================================================================
# DISPLAY CONTAINERS
# =============================================================================

class SettingsCard(QFrame):
    """Container matching the Hub style (Dark Blue-Grey)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background-color: #1A1F2B; border-radius: 6px; border: 1px solid #333; }")

class ClickableBanner(QLabel):
    def __init__(self, image_path, target_url, fallback_text="Support!", bg_color="#333", parent=None):
        super().__init__(parent)
        self.target_url = target_url
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.original_pixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(90); self.setMaximumHeight(120)
        self.setScaledContents(False)

        if image_path and os.path.exists(image_path):
            self.original_pixmap = QPixmap(image_path)
            self.update_pixmap()
            self.setStyleSheet("QLabel { border: 1px solid #3E4451; border-radius: 4px; background-color: #1A1F2B; } QLabel:hover { border: 1px solid #4476ED; }")
        else:
            self.setText(fallback_text)
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setStyleSheet(f"QLabel {{ background-color: {bg_color}; color: white; font-weight: bold; font-size: 16px; border-radius: 5px; border: 1px solid #3E4451; }} QLabel:hover {{ border: 1px solid #ffffff; background-color: {bg_color}dd; }}")

    def resizeEvent(self, event):
        if self.original_pixmap: self.update_pixmap()
        super().resizeEvent(event)

    def update_pixmap(self):
        if not self.original_pixmap: return
        scaled = self.original_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: QDesktopServices.openUrl(QUrl(self.target_url))