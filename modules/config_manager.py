import configparser
import os
from .constants import Constants


class ConfigManager:
    DEFAULT_HOTKEY_PRICE = "ctrl+f"
    DEFAULT_HOTKEY_QUEST = "ctrl+e"
    DEFAULT_HOTKEY_HUB = "ctrl+h"

    # OCR Defaults
    DEFAULT_OCR_COLOR = "249, 238, 223"
    DEFAULT_FULL_SCREEN = False
    DEFAULT_DEBUG_SAVE = False

    # General Defaults
    DEFAULT_LANG = "eng"

    # Item Overlay Defaults
    DEFAULT_ITEM_FONT = 12
    DEFAULT_ITEM_DURATION = 3.0
    DEFAULT_SHOW_FUTURE_HIDEOUT = True
    DEFAULT_SHOW_FUTURE_PROJECT = True
    DEFAULT_ITEM_OFFSET_X = 0
    DEFAULT_ITEM_OFFSET_Y = 0
    DEFAULT_ANCHOR_MODE = "Mouse"
    DEFAULT_ITEM_OPACITY = 98
    DEFAULT_SECTION_ORDER = "price,storage,trader,notes,crafting,hideout,project,recycle,salvage,recommendation"

    # Quest Overlay Defaults
    DEFAULT_QUEST_FONT = 12
    DEFAULT_QUEST_WIDTH = 350
    DEFAULT_QUEST_OPACITY = 95
    DEFAULT_QUEST_DURATION = 5.0

    # Window Defaults
    DEFAULT_WIN_W = 760
    DEFAULT_WIN_H = 850
    DEFAULT_WIN_X = -1
    DEFAULT_WIN_Y = -1
    DEFAULT_BANNER_VISIBLE = True

    # Remote Database Defaults
    DEFAULT_REMOTE_DATABASE_ENABLED = False
    DEFAULT_REMOTE_DATABASE_URL = "https://arcstashers.com/assets/home-Cnqc1Zqz.js"
    DEFAULT_SHOW_RECOMMENDATIONS = False
    DEFAULT_RECOMMENDATION_FORMAT = "original"  # Options: "original", "uppercase", "title", "lowercase"

    def __init__(self):
        self.path = Constants.CONFIG_FILE
        self.parser = configparser.ConfigParser()
        self.load()

    def load(self):
        """Reads the config file from disk."""
        self.parser.read(self.path)

    def save(self):
        """Writes the current state to disk."""
        try:
            with open(self.path, 'w') as f:
                self.parser.write(f)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_str(self, section, key, fallback=""):
        return self.parser.get(section, key, fallback=fallback)

    def get_int(self, section, key, fallback=0):
        return self.parser.getint(section, key, fallback=fallback)

    def get_float(self, section, key, fallback=0.0):
        return self.parser.getfloat(section, key, fallback=fallback)

    def get_bool(self, section, key, fallback=False):
        return self.parser.getboolean(section, key, fallback=fallback)

    def set(self, section, key, value):
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, key, str(value))

    def get_item_hotkey(self):
        return self.get_str('Hotkeys', 'price_check', self.DEFAULT_HOTKEY_PRICE)

    def get_quest_hotkey(self):
        return self.get_str('Hotkeys', 'quest_log', self.DEFAULT_HOTKEY_QUEST)

    def get_hub_hotkey(self):
        return self.get_str('Hotkeys', 'hub_hotkey', self.DEFAULT_HOTKEY_HUB)

    # --- OCR ---
    def get_ocr_color(self): return self.get_str('OCR', 'target_color', self.DEFAULT_OCR_COLOR)
    def set_ocr_color(self, val): self.set('OCR', 'target_color', val)

    def get_full_screen_scan(self): return self.get_bool('OCR', 'full_screen_scan', self.DEFAULT_FULL_SCREEN)
    def set_full_screen_scan(self, val): self.set('OCR', 'full_screen_scan', val)

    def get_save_debug_images(self): return self.get_bool('OCR', 'save_debug_images', self.DEFAULT_DEBUG_SAVE)
    def set_save_debug_images(self, val): self.set('OCR', 'save_debug_images', val)

    # --- GENERAL ---
    def get_language(self): return self.get_str('General', 'language', self.DEFAULT_LANG)
    def set_language(self, val): self.set('General', 'language', val)

    # --- ITEM OVERLAY ---
    def get_item_font_size(self): return self.get_int('ItemOverlay', 'font_size', self.DEFAULT_ITEM_FONT)
    def get_item_duration(self): return self.get_float('ItemOverlay', 'duration_seconds', self.DEFAULT_ITEM_DURATION)
    def get_show_future_hideout(self): return self.get_bool('ItemOverlay', 'show_all_future_reqs', self.DEFAULT_SHOW_FUTURE_HIDEOUT)
    def get_show_future_project(self): return self.get_bool('ItemOverlay', 'show_all_future_project_reqs', self.DEFAULT_SHOW_FUTURE_PROJECT)
    def get_show_future_project(self): return self.get_bool('ItemOverlay', 'show_all_future_project_reqs', self.DEFAULT_SHOW_FUTURE_PROJECT)
    def get_item_offset_x(self): return self.get_int('ItemOverlay', 'offset_x', self.DEFAULT_ITEM_OFFSET_X)
    def get_item_offset_y(self): return self.get_int('ItemOverlay', 'offset_y', self.DEFAULT_ITEM_OFFSET_Y)
    def get_item_anchor_mode(self): return self.get_str('ItemOverlay', 'anchor_mode', self.DEFAULT_ANCHOR_MODE)
    def get_item_opacity(self): return self.get_int('ItemOverlay', 'opacity', self.DEFAULT_ITEM_OPACITY)
    def get_overlay_section_order(self): return self.get_str('ItemOverlay', 'section_order', self.DEFAULT_SECTION_ORDER)

    def set_item_overlay_settings(self, font_size, duration, show_hideout, show_project,
                                  offset_x, offset_y, anchor_mode, opacity, order_str, section_states):
        self.set('ItemOverlay', 'font_size', font_size)
        self.set('ItemOverlay', 'duration_seconds', duration)
        self.set('ItemOverlay', 'show_all_future_reqs', show_hideout)
        self.set('ItemOverlay', 'show_all_future_project_reqs', show_project)
        self.set('ItemOverlay', 'offset_x', offset_x)
        self.set('ItemOverlay', 'offset_y', offset_y)
        self.set('ItemOverlay', 'anchor_mode', anchor_mode)
        self.set('ItemOverlay', 'opacity', opacity)
        self.set('ItemOverlay', 'section_order', order_str)
        for k, v in section_states.items(): self.set('ItemOverlay', k, v)

    # --- QUEST OVERLAY ---
    def get_quest_font_size(self): return self.get_int('QuestOverlay', 'font_size', self.DEFAULT_QUEST_FONT)
    def get_quest_width(self): return self.get_int('QuestOverlay', 'width', self.DEFAULT_QUEST_WIDTH)
    def get_quest_opacity(self): return self.get_int('QuestOverlay', 'opacity', self.DEFAULT_QUEST_OPACITY)
    def get_quest_duration(self): return self.get_float('QuestOverlay', 'duration_seconds', self.DEFAULT_QUEST_DURATION)

    def set_quest_overlay_settings(self, font_size, width, opacity, duration):
        self.set('QuestOverlay', 'font_size', font_size)
        self.set('QuestOverlay', 'width', width)
        self.set('QuestOverlay', 'opacity', opacity)
        self.set('QuestOverlay', 'duration_seconds', duration)

    # --- WINDOW STATE ---
    def get_window_geometry(self):
        return (
            self.get_int('Window', 'x', self.DEFAULT_WIN_X),
            self.get_int('Window', 'y', self.DEFAULT_WIN_Y),
            self.get_int('Window', 'width', self.DEFAULT_WIN_W),
            self.get_int('Window', 'height', self.DEFAULT_WIN_H)
        )

    def set_window_geometry(self, x, y, w, h):
        self.set('Window', 'x', x); self.set('Window', 'y', y)
        self.set('Window', 'width', w); self.set('Window', 'height', h)

    def get_banner_visible(self): return self.get_bool('Window', 'banner_visible', self.DEFAULT_BANNER_VISIBLE)
    def set_banner_visible(self, val): self.set('Window', 'banner_visible', val)

    # --- REMOTE DATABASE ---
    def get_remote_database_enabled(self): return self.get_bool('RemoteDatabase', 'enabled', self.DEFAULT_REMOTE_DATABASE_ENABLED)
    def set_remote_database_enabled(self, val): self.set('RemoteDatabase', 'enabled', val)

    def get_remote_database_url(self): return self.get_str('RemoteDatabase', 'database_url', self.DEFAULT_REMOTE_DATABASE_URL)
    def set_remote_database_url(self, val): self.set('RemoteDatabase', 'database_url', val)

    def get_show_recommendations(self): return self.get_bool('RemoteDatabase', 'show_recommendations', self.DEFAULT_SHOW_RECOMMENDATIONS)
    def set_show_recommendations(self, val): self.set('RemoteDatabase', 'show_recommendations', val)

    def get_recommendation_format(self): return self.get_str('ItemOverlay', 'recommendation_format', self.DEFAULT_RECOMMENDATION_FORMAT)
    def set_recommendation_format(self, val): self.set('ItemOverlay', 'recommendation_format', val)