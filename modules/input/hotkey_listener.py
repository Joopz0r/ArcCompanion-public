from PyQt6.QtCore import QObject, pyqtSignal
from pynput import keyboard as pynput_keyboard

class HotkeyListener(QObject):
    item_check_triggered = pyqtSignal()
    quest_log_triggered = pyqtSignal()
    hub_triggered = pyqtSignal()
    
    def __init__(self, item_hotkey, quest_hotkey, hub_hotkey):
        super().__init__()
        self.item_hotkey_str = self._convert_to_pynput_format(item_hotkey)
        self.quest_hotkey_str = self._convert_to_pynput_format(quest_hotkey)
        self.hub_hotkey_str = self._convert_to_pynput_format(hub_hotkey)
        self.listener = None

    def _convert_to_pynput_format(self, hotkey_str):
        parts = hotkey_str.lower().replace(" ", "").split('+')
        formatted_parts = []
        modifiers = {'ctrl', 'shift', 'alt', 'cmd', 'enter', 'tab', 'esc', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'insert', 'delete', 'home', 'end', 'pageup', 'pagedown'}
        for part in parts:
            if part in modifiers: formatted_parts.append(f"<{part}>")
            else: formatted_parts.append(part)
        return '+'.join(formatted_parts)

    def run(self):
        print(f"Hotkey listener started. Mapping: Item='{self.item_hotkey_str}', Quest='{self.quest_hotkey_str}', Hub='{self.hub_hotkey_str}'")
        hotkeys = { 
            self.item_hotkey_str: self._on_item_check, 
            self.quest_hotkey_str: self._on_quest_log,
            self.hub_hotkey_str: self._on_hub
        }
        try:
            with pynput_keyboard.GlobalHotKeys(hotkeys) as self.listener: self.listener.join()
        except Exception as e: print(f"Error in Hotkey Listener: {e}")

    def stop(self):
        if self.listener: self.listener.stop()

    def _on_item_check(self): self.item_check_triggered.emit()
    def _on_quest_log(self): self.quest_log_triggered.emit()
    def _on_hub(self): self.hub_triggered.emit()
