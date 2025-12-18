from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame, QGraphicsDropShadowEffect, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QCursor, QColor
import os
import math 
from modules.core.constants import Constants

class BaseOverlay(QWidget):
    def __init__(self, duration_ms, min_width=None, max_width=None, opacity=0.98, enable_distance_close=True, close_threshold=350):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(opacity)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame()
        self.container.setObjectName("OverlayFrame")
        
        self.container.setStyleSheet(f"""
            #OverlayFrame {{
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, 
                                                  stop:0 #2B303B, stop:1 #1A1F26);
                border: 1px solid #3E4451;
                border-top: 3px solid #555;
                border-radius: 5px;
            }}
            QLabel {{ color: #E0E6ED; }}
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.container.setGraphicsEffect(shadow)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(12, 10, 12, 10)
        self.container_layout.setSpacing(4) 
        
        self.main_layout.addWidget(self.container)

        if min_width: self.container.setMinimumWidth(min_width)
        if max_width: self.container.setMaximumWidth(max_width)
        
        self.duration_timer = QTimer(self)
        self.duration_timer.setSingleShot(True)
        self.duration_timer.timeout.connect(self.close_with_fade)
        self.duration_timer.start(int(duration_ms))

        if enable_distance_close:
            self.mouse_monitor_timer = QTimer(self)
            self.mouse_monitor_timer.timeout.connect(self.check_mouse_distance)
            self.mouse_monitor_timer.start(100) 
        
        self.close_threshold = close_threshold 

    def check_mouse_distance(self):
        mouse_pos = QCursor.pos()
        rect = self.frameGeometry()
        
        if mouse_pos.x() < rect.left(): dx = rect.left() - mouse_pos.x()
        elif mouse_pos.x() > rect.right(): dx = mouse_pos.x() - rect.right()
        else: dx = 0
            
        if mouse_pos.y() < rect.top(): dy = rect.top() - mouse_pos.y()
        elif mouse_pos.y() > rect.bottom(): dy = mouse_pos.y() - rect.bottom()
        else: dy = 0
            
        distance = math.sqrt(dx*dx + dy*dy)
        if distance > self.close_threshold: self.close_with_fade()

    def close_with_fade(self):
        """Closes the overlay with a smooth fade-out animation."""
        if hasattr(self, "_is_closing") and self._is_closing:
            return
        self._is_closing = True
        
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(300)
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_anim.finished.connect(self.close)
        self.fade_anim.start()

    def set_border_color(self, color_hex):
        self.container.setStyleSheet(f"""
            #OverlayFrame {{
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, 
                                                  stop:0 #2B303B, stop:1 #1A1F26);
                border: 1px solid #3E4451;
                border-top: 3px solid {color_hex};
                border-radius: 5px;
            }}
            QLabel {{ color: #E0E6ED; }}
        """)

    def add_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet("background-color: #3E4451; max-height: 1px;")
        self.container_layout.addWidget(line)

    def add_label(self, text, font_size=12, bold=False, color=None, indent=0):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        
        font = QFont("Segoe UI", font_size)
        if bold: font.setBold(True)
        lbl.setFont(font)
        
        style = f"margin-left: {indent}px; font-size: {font_size}pt;";
        if color: style += f" color: {color};"
        lbl.setStyleSheet(style)
        
        self.container_layout.addWidget(lbl)

    def show_smart(self, x=None, y=None, user_settings=None):
        """Improved show method that handles dual monitors and ensures visibility."""
        from PyQt6.QtGui import QGuiApplication
        
        cursor_pos = QCursor.pos()
        target_screen = QGuiApplication.screenAt(cursor_pos)
        if not target_screen:
            target_screen = QGuiApplication.primaryScreen()
            
        screen_geom = target_screen.geometry()
        overlay_height, overlay_width = self.sizeHint().height(), self.sizeHint().width()
        
        # Defaults if no settings provided
        offset_x, offset_y, anchor_mode = 0, 0, "Mouse"
        
        if user_settings:
            offset_x = user_settings.get_int('ItemOverlay', 'offset_x', fallback=0)
            offset_y = user_settings.get_int('ItemOverlay', 'offset_y', fallback=0)
            anchor_mode = user_settings.get_str('ItemOverlay', 'anchor_mode', fallback="Mouse")
        
        # Determine Base Position
        if anchor_mode == "Mouse":
             pos_x, pos_y = cursor_pos.x() + 20 + offset_x, cursor_pos.y() + 20 + offset_y
        else:
            sx, sy, sw, sh = screen_geom.x(), screen_geom.y(), screen_geom.width(), screen_geom.height()
            
            if "Top" in anchor_mode: base_y = sy + 20
            elif "Bottom" in anchor_mode: base_y = sy + sh - overlay_height - 20
            else: base_y = sy + (sh - overlay_height) // 2 
            
            if "Left" in anchor_mode: base_x = sx + 20
            elif "Right" in anchor_mode: base_x = sx + sw - overlay_width - 20
            else: base_x = sx + (sw - overlay_width) // 2 
            
            pos_x, pos_y = base_x + offset_x, base_y + offset_y

        # Keep on screen
        if pos_x + overlay_width > screen_geom.right(): pos_x = screen_geom.right() - overlay_width
        if pos_y + overlay_height > screen_geom.bottom(): pos_y = screen_geom.bottom() - overlay_height
        if pos_x < screen_geom.left(): pos_x = screen_geom.left()
        if pos_y < screen_geom.top(): pos_y = screen_geom.top()
        
        self.move(int(pos_x), int(pos_y))
        self.show()

class ItemOverlay(BaseOverlay):
    def __init__(self, item_data, user_settings, blueprint_required, hideout_reqs, project_reqs, trade_info, data_manager, user_note="", lang_code="en", stash_count=0, is_collected_blueprint=False, quest_reqs=None):
        # Initial config read for constructor args
        duration = user_settings.get_float('ItemOverlay', 'duration_seconds', fallback=3.0) * 1000
        font_size = user_settings.get_int('ItemOverlay', 'font_size', fallback=12)
        min_w = max(280, font_size * 25)
        max_w = max(400, font_size * 35)
        
        offset_x = user_settings.get_int('ItemOverlay', 'offset_x', fallback=0)
        offset_y = user_settings.get_int('ItemOverlay', 'offset_y', fallback=0)
        anchor_mode = user_settings.get_str('ItemOverlay', 'anchor_mode', fallback="Mouse")
        opacity_val = user_settings.get_int('ItemOverlay', 'opacity', fallback=98) / 100.0
        
        # Auto-disable leash if custom offsets are used OR if anchor is not Mouse
        enable_leash = (offset_x == 0 and offset_y == 0 and anchor_mode == "Mouse")
        
        super().__init__(duration, min_width=min_w, max_width=max_w, opacity=opacity_val, enable_distance_close=enable_leash)
        
        # storage
        self.item_data = item_data
        self.user_settings = user_settings
        self.blueprint_required = blueprint_required
        self.hideout_reqs = hideout_reqs
        self.project_reqs = project_reqs
        self.trade_info = trade_info
        self.data_manager = data_manager
        self.user_note = user_note
        self.lang_code = lang_code
        self.stash_count = stash_count
        self.is_collected_blueprint = is_collected_blueprint
        self.quest_reqs = quest_reqs or []
        
        self.refresh_ui()

    def refresh_ui(self):
        # 1. Clear existing layout
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # 2. Re-read settings
        font_size = self.user_settings.get_int('ItemOverlay', 'font_size', fallback=12)
        min_w = max(280, font_size * 25)
        max_w = max(400, font_size * 35)
        self.container.setMinimumWidth(min_w)
        self.container.setMaximumWidth(max_w)
        
        # 3. Apply Border Color
        rarity = self.item_data.get('rarity', 'Common')
        rarity_color = Constants.RARITY_COLORS.get(rarity, "#FFFFFF")
        self.set_border_color(rarity_color)
        
        # 4. Header (Name + Tracked + ticks)
        item_id = self.item_data.get('id')
        tracked_items = self.data_manager.user_progress.get('tracked_items', [])
        is_tracked = item_id and item_id in tracked_items
        show_indicator = self.user_settings.get_bool('ItemOverlay', 'show_tracked_indicator', fallback=True)
        
        display_name = self.data_manager.get_localized_name(self.item_data, self.lang_code)
        
        if is_tracked and show_indicator:
            display_name = f"★ {display_name}"
            
        if self.is_collected_blueprint:
            display_name += " <span style='color:#4CAF50'>✓</span>"
            
        self.add_label(display_name, font_size + 3, True, color=rarity_color)
        
        self.has_content = False

        # --- Renderers ---
        def render_trader():
            if self.user_settings.get_bool('ItemOverlay', 'show_trader_info', fallback=True) and self.trade_info:
                if self.has_content: self.add_separator()
                
                for trade in self.trade_info:
                    trader, cost = trade.get('trader'), trade.get('cost', {})
                    cost_qty, cost_item_id = cost.get('quantity'), cost.get('itemId')
                    
                    if cost_item_id == "coins": cost_name = "Coins"
                    else: cost_name = self.data_manager.get_localized_name(cost_item_id, self.lang_code).title()

                    overlay_text = f"{trader.title()}: {cost_qty}x {cost_name}"
                    self.add_label(overlay_text, font_size, False, "#98C379") 
                self.has_content = True

        def render_price():
            if self.user_settings.get_bool('ItemOverlay', 'show_price', fallback=True):
                if self.has_content: self.add_separator()
                raw_val = self.item_data.get('value')
                if raw_val is not None:
                    try: val_str = f"{int(raw_val):,}"
                    except ValueError: val_str = str(raw_val)
                else: val_str = "N/A"
                
                final_path = Constants.COIN_ICON_PATH
                if final_path and os.path.exists(final_path):
                    img_size = font_size + 4
                    safe_path = final_path.replace("\\", "/")
                    label_text = f"Price: <img src='{safe_path}' width='{img_size}' height='{img_size}' style='vertical-align: middle;'> <span style='color:#E5C07B'>{val_str}</span>"
                else:
                    label_text = f"Price: <span style='color:#E5C07B'>£{val_str}</span>"
                    
                self.add_label(label_text, font_size, True, color=None) 
                self.has_content = True

        def render_storage():
            if self.user_settings.get_bool('ItemOverlay', 'show_storage_info', fallback=True):
                if self.has_content: self.add_separator()
                
                final_path = Constants.STORAGE_ICON_PATH
                count_str = f"{self.stash_count:,}"
                
                if final_path and os.path.exists(final_path):
                    img_size = font_size + 4
                    safe_path = final_path.replace("\\", "/")
                    label_text = f"Stash: <img src='{safe_path}' width='{img_size}' height='{img_size}' style='vertical-align: middle;'> <span style='color:#ABB2BF'>{count_str}</span>"
                else:
                    label_text = f"Stash: <span style='color:#ABB2BF'>{count_str}</span>"
                
                self.add_label(label_text, font_size, True, color=None)
                self.has_content = True

        def render_crafting():
            if self.user_settings.get_bool('ItemOverlay', 'show_crafting_info', fallback=True):
                craft_bench, craft_time = self.item_data.get('craftBench'), self.item_data.get('craftTime')
                if isinstance(craft_bench, list): craft_bench = ", ".join([str(b).replace('_', ' ').title() for b in craft_bench])
                elif isinstance(craft_bench, str): craft_bench = craft_bench.replace('_', ' ').title()
                
                if craft_bench or self.blueprint_required:
                    if self.has_content: self.add_separator()
                    self.add_label("Crafting", font_size - 1, True, "#5C6370") 
                    if craft_bench: self.add_label(f"■ {craft_bench}{f' ({craft_time}s)' if craft_time else ''}", font_size, False, "#ABB2BF", 10)
                    if self.blueprint_required: self.add_label("■ Blueprint Required", font_size, True, "#61AFEF", 10) 
                    self.has_content = True

        def render_hideout():
            if not self.user_settings.get_bool('ItemOverlay', 'show_hideout_reqs', fallback=True): return
            show_future = self.user_settings.get_bool('ItemOverlay', 'show_all_future_reqs', fallback=False)
            
            filtered_reqs = []
            if self.hideout_reqs:
                for req in self.hideout_reqs:
                    if len(req) >= 4:
                        req_str, req_type, is_complete, needed_qty = req[0], req[1], req[2], req[3]
                        if req_type == 'next' or show_future:
                            filtered_reqs.append((req_str, req_type, is_complete, needed_qty))
                    else:
                        req_str, req_type = req[0], req[1]
                        if req_type == 'next' or show_future:
                            filtered_reqs.append((req_str, req_type, False, 0))
            
            if filtered_reqs:
                if self.has_content: self.add_separator()
                self.add_label("Hideout Upgrade:", font_size - 1, True, "#5C6370")
                for req_data in filtered_reqs:
                    req_str, req_type, is_complete, needed_qty = req_data
                    if is_complete:
                        color = "#4CAF50"  # Green
                        display_text = f"■ {req_str} <span style='color:#4CAF50'>✓</span>"
                    else:
                        color = "#98C379" if req_type == 'next' else "#D19A66" 
                        display_text = f"■ {req_str}"
                    self.add_label(display_text, font_size, False, color, 10)
                self.has_content = True

        def render_project():
            if not self.user_settings.get_bool('ItemOverlay', 'show_project_reqs', fallback=True): return
            show_future = self.user_settings.get_bool('ItemOverlay', 'show_all_future_project_reqs', fallback=False)
            
            # Handle both old format (2-tuple) and new format (4-tuple)
            filtered_reqs = []
            if self.project_reqs:
                for req in self.project_reqs:
                    if len(req) >= 4:
                        # New format: (display_str, req_type, is_complete, needed_qty)
                        req_str, req_type, is_complete, needed_qty = req[0], req[1], req[2], req[3]
                        if req_type == 'next' or show_future:
                            filtered_reqs.append((req_str, req_type, is_complete, needed_qty))
                    else:
                        # Old format: (display_str, req_type) - for backwards compatibility
                        req_str, req_type = req[0], req[1]
                        if req_type == 'next' or show_future:
                            filtered_reqs.append((req_str, req_type, False, 0))
            
            if filtered_reqs:
                if self.has_content: self.add_separator()
                self.add_label("Project Request:", font_size - 1, True, "#5C6370")
                for req_data in filtered_reqs:
                    req_str, req_type, is_complete, needed_qty = req_data
                    if is_complete:
                        # Show with green tick for completed requirements
                        color = "#4CAF50"  # Green
                        display_text = f"■ {req_str} <span style='color:#4CAF50'>✓</span>"
                    else:
                        color = "#98C379" if req_type == 'next' else "#D19A66" 
                        display_text = f"■ {req_str}"
                    self.add_label(display_text, font_size, False, color, 10)
                self.has_content = True

        def render_recycle():
            recycles = self.item_data.get('recyclesInto', {})
            if self.user_settings.get_bool('ItemOverlay', 'show_recycles_into', fallback=False) and recycles:
                if self.has_content: self.add_separator()
                self.add_label("Recycles Into:", font_size - 1, True, "#5C6370")
                for item_id_raw, quantity in recycles.items():
                    item_name = self.data_manager.get_localized_name(item_id_raw, self.lang_code)
                    comp_details = self.data_manager.get_item_by_name(self.data_manager.id_to_name_map.get(item_id_raw)) 
                    if not comp_details: comp_details = self.data_manager.id_to_item_map.get(item_id_raw)
                    comp_rarity = comp_details.get('rarity', 'Common') if comp_details else 'Common'
                    self.add_label(f"■ {quantity}x {item_name}", font_size, False, Constants.RARITY_COLORS.get(comp_rarity, "#FFFFFF"), 10)
                self.has_content = True

        def render_salvage():
            salvages = self.item_data.get('salvagesInto', {})
            if self.user_settings.get_bool('ItemOverlay', 'show_salvages_into', fallback=False) and salvages:
                if self.has_content: self.add_separator()
                self.add_label("Salvages Into:", font_size - 1, True, "#5C6370")
                for item_id_raw, quantity in salvages.items():
                    item_name = self.data_manager.get_localized_name(item_id_raw, self.lang_code)
                    comp_details = self.data_manager.id_to_item_map.get(item_id_raw)
                    comp_rarity = comp_details.get('rarity', 'Common') if comp_details else 'Common'
                    self.add_label(f"■ {quantity}x {item_name}", font_size, False, Constants.RARITY_COLORS.get(comp_rarity, "#FFFFFF"), 10)
                self.has_content = True

        def render_notes():
            if self.user_settings.get_bool('ItemOverlay', 'show_notes', fallback=True) and self.user_note:
                if self.has_content: self.add_separator()
                self.add_label("Notes", font_size - 1, True, "#5C6370")
                self.add_label(f"✎ {self.user_note}", font_size, False, "#FFEB3B", 10) 
                self.has_content = True

        def render_quest():
            if self.user_settings.get_bool('ItemOverlay', 'show_quest_reqs', fallback=True) and self.quest_reqs:
                if self.has_content: self.add_separator()
                self.add_label("Quest Requirement:", font_size - 1, True, "#5C6370")
                for req_str, is_complete in self.quest_reqs:
                    color = "#4CAF50" if is_complete else "#61AFEF"
                    display_text = f"■ {req_str}"
                    if is_complete: display_text += " <span style='color:#4CAF50'>✓</span>"
                    self.add_label(display_text, font_size, False, color, 10)
                self.has_content = True

        renderers = {
            'price': render_price,
            'storage': render_storage,
            'trader': render_trader,
            'notes': render_notes,
            'crafting': render_crafting,
            'hideout': render_hideout,
            'project': render_project,
            'quest': render_quest,
            'recycle': render_recycle,
            'salvage': render_salvage
        }

        saved_order_str = self.user_settings.get_str('ItemOverlay', 'section_order', fallback="")
        if saved_order_str:
            order = [x.strip() for x in saved_order_str.split(',') if x.strip() in renderers]
            for k in renderers:
                if k not in order: order.append(k)
        else:
            order = ['price', 'storage', 'trader', 'notes', 'crafting', 'hideout', 'project', 'quest', 'recycle', 'salvage']

        for key in order:
            if key in renderers: renderers[key]()

        self.adjustSize()
        
    def show_smart(self, x=None, y=None):
        # Delegate to base class with our settings
        return super().show_smart(x, y, user_settings=self.user_settings)

class QuestOverlayUI:
    @staticmethod
    def create_window(tracked_quests, user_settings, data_manager=None, lang_code="en"):
        duration = user_settings.get_float('QuestOverlay', 'duration_seconds', fallback=5.0) * 1000
        width = user_settings.get_int('QuestOverlay', 'width', fallback=350)
        opacity = user_settings.get_int('QuestOverlay', 'opacity', fallback=95) / 100.0
        font_size = user_settings.get_int('QuestOverlay', 'font_size', fallback=12)

        overlay = BaseOverlay(duration, min_width=width, max_width=width, opacity=opacity, enable_distance_close=False)
        overlay.set_border_color(Constants.RARITY_COLORS.get('Rare', '#4A5469')) 
        
        overlay.add_label("Tracked Quests", font_size + 2, True, Constants.RARITY_COLORS['Rare'])
        overlay.add_separator()

        if not tracked_quests:
            overlay.add_label("No quests tracked.", font_size)
        else:
            for i, quest in enumerate(tracked_quests):
                if i > 0: overlay.add_separator()
                
                overlay.add_label(quest.get('name', 'Unknown'), font_size, True, Constants.QUEST_HEADER_COLOR)
                
                if data_manager:
                    map_names = data_manager.get_quest_map_names(quest, lang_code=lang_code)
                    if map_names:
                        map_str = ", ".join(map_names)
                        overlay.add_label(f"Map: {map_str}", font_size - 1, False, "#61AFEF")
                
                for objective in quest.get('objectives', []):
                    is_completed = objective in quest.get('objectives_completed', [])
                    color = "#5C6370" if is_completed else Constants.QUEST_OBJECTIVE_COLOR 
                    txt = f"■ {objective}"
                    lbl = QLabel(txt); lbl.setWordWrap(True); lbl.setFont(QFont("Segoe UI", font_size))
                    if is_completed: lbl.setText(f"<span style='text-decoration: line-through;'>{txt}</span>")
                    lbl.setStyleSheet(f"color: {color}; margin-left: 10px; font-size: {font_size}pt;")
                    overlay.container_layout.addWidget(lbl)

        overlay.adjustSize()
        screen = overlay.screen().geometry(); h = overlay.size().height(); y = (screen.height() - h) // 2
        overlay.show_at_position(20, y)
        return overlay