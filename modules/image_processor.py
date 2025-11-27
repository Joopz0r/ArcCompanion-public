from PIL import Image, ImageGrab
import numpy as np
import ctypes
from typing import Optional, Tuple
from scipy.ndimage import label, find_objects

class ImageProcessor:
    @staticmethod
    def find_color_region(img: Image.Image, target_color: Tuple[int, int, int], tolerance: int = 40) -> Optional[Tuple[int, int, int, int]]:
        img_array = np.array(img.convert('RGB'))
        r, g, b = target_color
        mask = ((np.abs(img_array[:, :, 0] - r) <= tolerance) & 
                (np.abs(img_array[:, :, 1] - g) <= tolerance) & 
                (np.abs(img_array[:, :, 2] - b) <= tolerance))
        labeled_mask, num_features = label(mask)
        if num_features == 0:
            return None
        blob_sizes = np.bincount(labeled_mask.ravel())
        blob_sizes[0] = 0
        largest_blob_label = blob_sizes.argmax()
        if largest_blob_label == 0:
            return None
        blob_slices = find_objects(labeled_mask == largest_blob_label)
        if not blob_slices:
            return None
        y_slice, x_slice = blob_slices[0]
        padding = 5
        return (
            max(0, x_slice.start - padding), 
            max(0, y_slice.start - padding), 
            min(img.width, x_slice.stop + padding), 
            min(img.height, y_slice.stop + padding)
        )
    
    @staticmethod
    def capture_and_process(target_color: Optional[Tuple[int, int, int]], full_screen: bool = False):
        try:
            if full_screen:
                # Capture the entire primary screen
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                search_bbox = (0, 0, screen_width, screen_height)
            else:
                # Capture around the cursor
                pt = ctypes.wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                search_width, search_height = 1200, 1200
                search_bbox = (
                    max(0, pt.x - search_width // 2),
                    max(0, pt.y - search_height // 2),
                    min(screen_width, pt.x + search_width // 2),
                    min(screen_height, pt.y + search_height // 2)
                )

            search_img = ImageGrab.grab(bbox=search_bbox)
            
            if target_color:
                color_region_bbox = ImageProcessor.find_color_region(search_img, target_color)
                if color_region_bbox:
                    return search_img.crop(color_region_bbox)
            
            return search_img
        except Exception as e:
            print(f"Screen capture failed: {e}")
            return None