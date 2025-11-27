from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame, QGraphicsDropShadowEffect, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QCursor, QColor
import os
import math # Needed for distance calculation
from .constants import Constants

class BaseOverlay(QWidget):
    def __init__(self, duration_ms, min_width=None, max_width=None, opacity=0.98):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(opacity)
        
        # Use 0 margins for a clean "card" look with the gradient
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame()
        self.container.setObjectName("OverlayFrame")
        
        # Default styling: Linear Gradient Background + Subtle Border
        # The 'border-top' will be overridden by set_border_color
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
        
        # Add a subtle drop shadow to the window itself for pop
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.container.setGraphicsEffect(shadow)

        self.container_layout = QVBoxLayout(self.container)
        # Add padding inside the box so text isn't touching the edges
        self.container_layout.setContentsMargins(12, 10, 12, 10)
        self.container_layout.setSpacing(4) 
        
        self.main_layout.addWidget(self.container)

        if min_width: self.container.setMinimumWidth(min_width)
        if max_width: self.container.setMaximumWidth(max_width)
        
        # --- AUTO-CLOSE TIMER (Duration) ---
        self.duration_timer = QTimer(self)
        self.duration_timer.setSingleShot(True)
        self.duration_timer.timeout.connect(self.close)
        self.duration_timer.start(int(duration_ms))

        # --- MOUSE DISTANCE MONITOR (Radar) ---
        # Checks every 100ms if the mouse has moved too far away
        self.mouse_monitor_timer = QTimer(self)
        self.mouse_monitor_timer.timeout.connect(self.check_mouse_distance)
        self.mouse_monitor_timer.start(100) 
        
        # Distance threshold in pixels (how far away to trigger close)
        self.close_threshold = 350 

    def check_mouse_distance(self):
        """Calculates distance from mouse to the nearest edge of the overlay."""
        mouse_pos = QCursor.pos()
        rect = self.frameGeometry()
        
        # Calculate dx (distance in x axis)
        if mouse_pos.x() < rect.left():
            dx = rect.left() - mouse_pos.x()
        elif mouse_pos.x() > rect.right():
            dx = mouse_pos.x() - rect.right()
        else:
            dx = 0 # Mouse is within the horizontal range
            
        # Calculate dy (distance in y axis)
        if mouse_pos.y() < rect.top():
            dy = rect.top() - mouse_pos.y()
        elif mouse_pos.y() > rect.bottom():
            dy = mouse_pos.y() - rect.bottom()
        else:
            dy = 0 # Mouse is within the vertical range
            
        # Euclidean distance (Hypotenuse)
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > self.close_threshold:
            self.close()

    def set_border_color(self, color_hex):
        # Updates the Top Border to match rarity, keeps the rest subtle
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
        # FIX: Enable word wrap immediately so layout calculates height correctly
        lbl.setWordWrap(True)
        # FIX: Ensure label tries to expand vertically if needed
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        
        font = QFont("Segoe UI", font_size)
        if bold: font.setBold(True)
        lbl.setFont(font)
        
        style = f"margin-left: {indent}px;";
        if color: style += f" color: {color};"
        lbl.setStyleSheet(style)
        
        self.container_layout.addWidget(lbl)

    def show_at_cursor(self):
        cursor_pos = QCursor.pos()
        self.move(cursor_pos.x() + 20, cursor_pos.y() + 20)
        self.show()

    def show_at_position(self, x, y):
        self.move(x, y)
        self.show()

class ItemOverlayUI:
    @staticmethod
    def create_window(item_data, user_settings, blueprint_required, hideout_reqs, project_reqs, trade_info, data_manager, user_note="", lang_code="en"):
        duration = user_settings.getfloat('ItemOverlay', 'duration_seconds', fallback=3.0) * 1000
        font_size = user_settings.getint('ItemOverlay', 'font_size', fallback=12)
        
        min_w = max(280, font_size * 25)
        max_w = max(400, font_size * 35)
        overlay = BaseOverlay(duration, min_width=min_w, max_width=max_w) 
        
        rarity = item_data.get('rarity', 'Common')
        rarity_color = Constants.RARITY_COLORS.get(rarity, "#FFFFFF")
        
        overlay.set_border_color(rarity_color)
        
        # --- HEADER SECTION ---
        item_id = item_data.get('id')
        tracked_items = data_manager.user_progress.get('tracked_items', [])
        is_tracked = item_id and item_id in tracked_items
        show_indicator = user_settings.getboolean('ItemOverlay', 'show_tracked_indicator', fallback=True)
        
        # Get localized name
        display_name = data_manager.get_localized_name(item_data, lang_code)
        
        if is_tracked and show_indicator:
            display_name = f"★ {display_name}"
            
        # Item Name in Rarity Color, slightly larger
        overlay.add_label(display_name, font_size + 3, True, color=rarity_color)
        
        has_content = False

        # --- Render Functions ---
        def render_trader():
            nonlocal has_content
            if user_settings.getboolean('ItemOverlay', 'show_trader_info', fallback=True) and trade_info:
                if has_content: overlay.add_separator()
                
                for trade in trade_info:
                    trader, cost = trade.get('trader'), trade.get('cost', {})
                    cost_qty, cost_item_id = cost.get('quantity'), cost.get('itemId')
                    
                    if cost_item_id == "coins":
                        cost_name = "Coins"
                    else:
                        cost_name = data_manager.get_localized_name(cost_item_id, lang_code).title()

                    overlay_text = f"{trader.title()}: {cost_qty}x {cost_name}"
                    overlay.add_label(overlay_text, font_size, False, "#98C379") 
                has_content = True

        def render_price():
            nonlocal has_content
            if user_settings.getboolean('ItemOverlay', 'show_price', fallback=True):
                if has_content: overlay.add_separator()
                
                raw_val = item_data.get('value')
                
                # Format number with commas
                if raw_val is not None:
                    try:
                        val_str = f"{int(raw_val):,}"
                    except ValueError:
                        val_str = str(raw_val)
                else:
                    val_str = "N/A"
                
                # Define paths
                final_path = Constants.COIN_ICON_PATH

                if final_path and os.path.exists(final_path):
                    # Use Image: vertical-align: middle fixes floating issues
                    img_size = font_size + 4
                    safe_path = final_path.replace("\\", "/")
                    label_text = f"Price: <img src='{safe_path}' width='{img_size}' height='{img_size}' style='vertical-align: middle;'> <span style='color:#E5C07B'>{val_str}</span>"
                else:
                    # Fallback if image missing
                    label_text = f"Price: <span style='color:#E5C07B'>£{val_str}</span>"
                    
                overlay.add_label(label_text, font_size, True, color=None) 
                has_content = True

        def render_crafting():
            nonlocal has_content
            if user_settings.getboolean('ItemOverlay', 'show_crafting_info', fallback=True):
                craft_bench, craft_time = item_data.get('craftBench'), item_data.get('craftTime')
                if isinstance(craft_bench, list): craft_bench = ", ".join([str(b).replace('_', ' ').title() for b in craft_bench])
                elif isinstance(craft_bench, str): craft_bench = craft_bench.replace('_', ' ').title()
                
                if craft_bench or blueprint_required:
                    if has_content: overlay.add_separator()
                    overlay.add_label("Crafting", font_size - 1, True, "#5C6370") 
                    if craft_bench:
                        overlay.add_label(f"■ {craft_bench}{f' ({craft_time}s)' if craft_time else ''}", font_size, False, "#ABB2BF", 10)
                    if blueprint_required:
                        overlay.add_label("■ Blueprint Required", font_size, True, "#61AFEF", 10) 
                    has_content = True

        def render_hideout():
            nonlocal has_content
            if not user_settings.getboolean('ItemOverlay', 'show_hideout_reqs', fallback=True):
                return

            show_future = user_settings.getboolean('ItemOverlay', 'show_all_future_reqs', fallback=False)
            filtered_reqs = [r for r in hideout_reqs if r[1] == 'next' or show_future] if hideout_reqs else []

            if filtered_reqs:
                if has_content: overlay.add_separator()
                overlay.add_label("Hideout Upgrade:", font_size - 1, True, "#5C6370")
                for req_str, req_type in filtered_reqs:
                    color = "#98C379" if req_type == 'next' else "#D19A66" 
                    overlay.add_label(f"■ {req_str}", font_size, False, color, 10)
                has_content = True

        def render_project():
            nonlocal has_content
            if not user_settings.getboolean('ItemOverlay', 'show_project_reqs', fallback=True):
                return

            show_future = user_settings.getboolean('ItemOverlay', 'show_all_future_project_reqs', fallback=False)
            filtered_reqs = [r for r in project_reqs if r[1] == 'next' or show_future] if project_reqs else []

            if filtered_reqs:
                if has_content: overlay.add_separator()
                overlay.add_label("Project Request:", font_size - 1, True, "#5C6370")
                for req_str, req_type in filtered_reqs:
                    color = "#98C379" if req_type == 'next' else "#D19A66" 
                    overlay.add_label(f"■ {req_str}", font_size, False, color, 10)
                has_content = True

        def render_recycle():
            nonlocal has_content
            recycles = item_data.get('recyclesInto', {})
            if user_settings.getboolean('ItemOverlay', 'show_recycles_into', fallback=False) and recycles:
                if has_content: overlay.add_separator()
                overlay.add_label("Recycles Into:", font_size - 1, True, "#5C6370")
                for item_id_raw, quantity in recycles.items():
                    # Get localized name
                    item_name = data_manager.get_localized_name(item_id_raw, lang_code)
                    
                    # Need details for rarity color
                    comp_details = data_manager.get_item_by_name(data_manager.id_to_name_map.get(item_id_raw)) # Fallback lookup via English map
                    if not comp_details: comp_details = data_manager.id_to_item_map.get(item_id_raw) # Direct lookup
                    
                    comp_rarity = comp_details.get('rarity', 'Common') if comp_details else 'Common'
                    overlay.add_label(f"■ {quantity}x {item_name}", font_size, False, Constants.RARITY_COLORS.get(comp_rarity, "#FFFFFF"), 10)
                has_content = True

        def render_salvage():
            nonlocal has_content
            salvages = item_data.get('salvagesInto', {})
            if user_settings.getboolean('ItemOverlay', 'show_salvages_into', fallback=False) and salvages:
                if has_content: overlay.add_separator()
                overlay.add_label("Salvages Into:", font_size - 1, True, "#5C6370")
                for item_id_raw, quantity in salvages.items():
                    # Get localized name
                    item_name = data_manager.get_localized_name(item_id_raw, lang_code)
                    
                    # Need details for rarity color
                    comp_details = data_manager.id_to_item_map.get(item_id_raw)
                    comp_rarity = comp_details.get('rarity', 'Common') if comp_details else 'Common'
                    
                    overlay.add_label(f"■ {quantity}x {item_name}", font_size, False, Constants.RARITY_COLORS.get(comp_rarity, "#FFFFFF"), 10)
                has_content = True

        def render_notes():
            nonlocal has_content
            if user_settings.getboolean('ItemOverlay', 'show_notes', fallback=True) and user_note:
                if has_content: overlay.add_separator()
                overlay.add_label("Notes", font_size - 1, True, "#5C6370")
                overlay.add_label(f"✎ {user_note}", font_size, False, "#FFEB3B", 10) 
                has_content = True

        # Map keys to functions
        renderers = {
            'price': render_price,
            'trader': render_trader,
            'notes': render_notes,
            'crafting': render_crafting,
            'hideout': render_hideout,
            'project': render_project,
            'recycle': render_recycle,
            'salvage': render_salvage
        }

        # Determine Order
        saved_order_str = user_settings.get('ItemOverlay', 'section_order', fallback="")
        if saved_order_str:
            order = [x.strip() for x in saved_order_str.split(',') if x.strip() in renderers]
            # Append missing
            for k in renderers:
                if k not in order: order.append(k)
        else:
            # Default order
            order = ['price', 'trader', 'notes', 'crafting', 'hideout', 'project', 'recycle', 'salvage']

        # Execute Renderers
        for key in order:
            if key in renderers:
                renderers[key]()

        # FIX: Calculate size now that everything is laid out and wrapped
        overlay.adjustSize()

        # FIX: Ensure it stays on screen
        screen_geom = overlay.screen().geometry()
        cursor_pos = QCursor.pos()
        overlay_height, overlay_width = overlay.size().height(), overlay.size().width()
        pos_x, pos_y = cursor_pos.x() + 20, cursor_pos.y() + 20
        
        # Adjust Y if it falls off bottom
        if pos_y + overlay_height > screen_geom.height(): 
            pos_y = screen_geom.height() - overlay_height - 10
        
        # Adjust X if it falls off right
        if pos_x + overlay_width > screen_geom.width(): 
            pos_x = cursor_pos.x() - overlay_width - 20
        
        overlay.move(pos_x, pos_y)
        overlay.show()
        return overlay

class QuestOverlayUI:
    @staticmethod
    def create_window(tracked_quests, user_settings):
        duration = user_settings.getfloat('QuestOverlay', 'duration_seconds', fallback=5.0) * 1000
        width = user_settings.getint('QuestOverlay', 'width', fallback=350)
        opacity = user_settings.getint('QuestOverlay', 'opacity', fallback=95) / 100.0
        font_size = user_settings.getint('QuestOverlay', 'font_size', fallback=12)

        overlay = BaseOverlay(duration, min_width=width, max_width=width, opacity=opacity)
        overlay.set_border_color(Constants.RARITY_COLORS.get('Rare', '#4A5469')) 
        
        overlay.add_label("Tracked Quests", font_size + 2, True, Constants.RARITY_COLORS['Rare'])
        overlay.add_separator()

        if not tracked_quests:
            overlay.add_label("No quests tracked.", font_size)
        else:
            for i, quest in enumerate(tracked_quests):
                if i > 0:
                    overlay.add_separator()
                overlay.add_label(quest['name'], font_size, True, Constants.QUEST_HEADER_COLOR)
                for objective in quest.get('objectives', []):
                    is_completed = objective in quest.get('objectives_completed', [])
                    color = "#5C6370" if is_completed else Constants.QUEST_OBJECTIVE_COLOR 
                    txt = f"■ {objective}"
                    lbl = QLabel(txt); lbl.setWordWrap(True); lbl.setFont(QFont("Segoe UI", font_size))
                    if is_completed: lbl.setText(f"<span style='text-decoration: line-through;'>{txt}</span>")
                    lbl.setStyleSheet(f"color: {color}; margin-left: 10px;")
                    overlay.container_layout.addWidget(lbl)

        overlay.adjustSize()
        screen = overlay.screen().geometry(); h = overlay.size().height(); y = (screen.height() - h) // 2
        overlay.show_at_position(20, y)
        return overlay