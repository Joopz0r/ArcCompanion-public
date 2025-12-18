from PyQt6.QtCore import QObject, pyqtSignal
import traceback
from modules.ocr.scanner import ItemScanner

class ScanWorker(QObject):
    """
    Runs the screen scanning and OCR process in a separate thread.
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, scanner: ItemScanner, from_tray: bool):
        super().__init__()
        self.scanner = scanner
        self.from_tray = from_tray

    def run(self):
        try:
            # This calls the new OpenCV+MSS scanner
            result = self.scanner.scan_screen(full_screen=self.from_tray)
            self.finished.emit(result)
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))
            self.finished.emit(None)
