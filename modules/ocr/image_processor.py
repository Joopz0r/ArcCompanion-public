import mss
import cv2
import numpy as np
import ctypes
from PIL import Image
from typing import Optional, Tuple
import os

class ImageProcessor:
    @staticmethod
    def find_color_region(img_bgr: np.ndarray, target_color_rgb: Tuple[int, int, int], tolerance: int = 40) -> Optional[Tuple[int, int, int, int]]:
        """
        Uses OpenCV (cv2) to find a color blob.
        
        :param img_bgr: A numpy array in BGR format (standard for OpenCV/MSS).
        :param target_color_rgb: The user's config color in RGB (e.g., 249, 238, 223).
        """
        # 1. Flip User Config from RGB to BGR to match OpenCV's format
        r, g, b = target_color_rgb
        target_bgr = (b, g, r)
        
        # 2. Define Lower/Upper Bounds
        lower = np.array([max(0, c - tolerance) for c in target_bgr], dtype=np.uint8)
        upper = np.array([min(255, c + tolerance) for c in target_bgr], dtype=np.uint8)
        
        # 3. Create Mask (The heavy math happens here, extremely fast in C++)
        mask = cv2.inRange(img_bgr, lower, upper)
        
        # 4. Find Contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
            
        # 5. Find Largest Blob
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Filter out tiny noise (e.g., less than 50 pixels area)
        if w * h < 50:
            return None
            
        # 6. Add Padding
        padding = 5
        h_img, w_img = img_bgr.shape[:2]
        
        x1 = int(max(0, x - padding))
        y1 = int(max(0, y - padding))
        x2 = int(min(w_img, x + w + padding))
        y2 = int(min(h_img, y + h + padding))
        
        return (x1, y1, x2, y2)
    
    @staticmethod
    def capture_and_process(target_color: Optional[Tuple[int, int, int]], full_screen: bool = False, debug_path: str = None, debug_prefix: str = None):
        try:
            with mss.mss() as sct:
                # --- 1. Determine Capture Region ---
                # --- 1. Determine Capture Region ---
                if full_screen:
                    # Monitor 1 is usually the Primary Monitor (default fallback)
                    monitor_region = sct.monitors[1]
                    
                    # Attempt to find which monitor the mouse is on
                    pt = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    
                    # Iterate over all monitors (skipping index 0 which is 'all monitors combined')
                    for i, monitor in enumerate(sct.monitors[1:], start=1):
                        # mss monitor dict keys: 'left', 'top', 'width', 'height'
                        m_left = monitor["left"]
                        m_top = monitor["top"]
                        m_right = m_left + monitor["width"]
                        m_bottom = m_top + monitor["height"]
                        
                        if m_left <= pt.x < m_right and m_top <= pt.y < m_bottom:
                            monitor_region = monitor
                            break
                else:
                    # Capture around cursor
                    pt = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    
                    # Fallback system metrics usually return primary screen size
                    # For multi-monitor "around cursor", we just need valid global coordinates
                    # mss handles global coordinates fine without needing specific monitor index
                    
                    search_width, search_height = 1200, 1200
                    
                    left = int(max(0, pt.x - search_width // 2))
                    top = int(max(0, pt.y - search_height // 2))
                    # Note: We can't easily clamp 'right'/'bottom' to a specific monitor without knowing which one,
                    # but mss handles out-of-bounds gracefully usually. 
                    # For safety, we can just define the rect without clamping to screen_width/height 
                    # (since that was only primary monitor anyway).
                    
                    monitor_region = {
                        "top": top,
                        "left": left,
                        "width": search_width,
                        "height": search_height
                    }

                # --- 2. Capture (Raw Bytes) ---
                sct_img = sct.grab(monitor_region)
                
                # --- 3. Prepare Formats ---
                
                # Format A: Numpy Array (for OpenCV detection)
                # MSS returns BGRA. We drop the Alpha channel to get BGR.
                img_np = np.array(sct_img)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

                # Format B: PIL Image (for Output/Tesseract)
                # We convert bytes directly to RGB for PIL
                img_pil = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                # --- 4. DEBUG SAVING (Raw) ---
                if debug_path and debug_prefix:
                    try:
                        raw_filename = f"{debug_prefix}_raw.png"
                        img_pil.save(os.path.join(debug_path, raw_filename))
                    except Exception as e:
                        print(f"Failed to save debug raw image: {e}")

                # --- 5. Detect & Crop ---
                bbox = None
                if target_color:
                    # Pass the BGR numpy array + RGB config color
                    bbox = ImageProcessor.find_color_region(img_bgr, target_color)
                
                if bbox:
                    # Crop the PIL image using coordinates found by OpenCV
                    return img_pil.crop(bbox)
            
            # If no color found, return the full search area (fallback)
            return img_pil
            
        except Exception as e:
            print(f"Screen capture failed: {e}")
            return None