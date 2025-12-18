import re
import os
import pytesseract
import cv2
import numpy as np
from PIL import ImageEnhance, Image
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

import difflib
# RapidFuzz check
try:
    from rapidfuzz import process, fuzz; _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

from modules.core.constants import Constants
from .image_processor import ImageProcessor


def normalize_for_matching(text: str) -> str:
    """Normalize text for fuzzy matching - removes spaces, periods, and converts to lowercase."""
    return re.sub(r'[\s.\-()]+', '', text).lower()


def fix_roman_numeral_ocr(text: str) -> str:
    """
    Fix common OCR errors with Roman numerals.
    The OCR often misreads:
      - 'II' as 'Il' (two I's read as I + lowercase L)
      - 'III' as 'Ill' or 'IIl' 
      - 'IV' as 'lV' or 'Iv'
    """
    # Common patterns at the end of item names (case insensitive positions)
    # Order matters - check longer patterns first
    fixed = text
    
    # Fix III patterns (must check before II patterns)
    fixed = re.sub(r'[iIlL]{3}$', 'III', fixed)  # Any combo of i/I/l/L at end -> III
    fixed = re.sub(r'[iIlL]{3}\b', 'III', fixed)  # Any combo of i/I/l/L before word boundary
    
    # Fix II patterns  
    fixed = re.sub(r'[IL]l$', 'II', fixed)  # Il or Ll at end -> II
    fixed = re.sub(r'l[IL]$', 'II', fixed)  # lI or lL at end -> II
    fixed = re.sub(r'[IL]l\b', 'II', fixed)  # Il before word boundary
    fixed = re.sub(r'l[IL]\b', 'II', fixed)  # lI before word boundary
    
    # Fix IV patterns
    fixed = re.sub(r'[lI][vV]$', 'IV', fixed)  # lV or IV at end
    fixed = re.sub(r'[lI][vV]\b', 'IV', fixed)  # lV before word boundary
    
    return fixed


class ItemScanner:
    def __init__(self, config, data_manager):
        """
        :param config: The app config object (contains tesseract path, debug flags).
        :param data_manager: The DataManager instance for looking up item details.
        """
        self.cmd_config = config
        self.data_manager = data_manager
        
        # Default Settings
        self.target_color = (249, 238, 223)
        self.ocr_lang_code = 'eng'
        self.json_lang_code = 'en'
        self.full_screen_mode = False 
        self.save_debug_images = False # Default Off
        
        # Configure Tesseract Path if provided
        if self.cmd_config.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.cmd_config.tesseract_path

    def update_settings(self, target_color, ocr_lang_code, json_lang_code, full_screen_mode=False, save_debug_images=False):
        """Updates scanner settings when the user changes preferences."""
        self.target_color = target_color
        self.ocr_lang_code = ocr_lang_code
        self.json_lang_code = json_lang_code
        self.full_screen_mode = full_screen_mode
        self.save_debug_images = save_debug_images

    def _get_language_filtered_items(self) -> List[Tuple[str, dict]]:
        """
        Get item names filtered by the currently selected JSON language.
        Returns a list of (name, item_data) tuples for only the selected language.
        This prevents matching against Chinese/Japanese/etc names when English is selected.
        """
        lang_code = self.json_lang_code if self.json_lang_code else 'en'
        
        # Use a set to track unique items by their 'id' to avoid duplicates
        seen_ids = set()
        filtered_items = []
        
        for name, item_data in self.data_manager.items.items():
            item_id = item_data.get('id')
            if item_id and item_id in seen_ids:
                continue
            
            # Get the localized name for the selected language
            names_dict = item_data.get('names', {})
            if isinstance(names_dict, dict):
                localized_name = names_dict.get(lang_code)
                if localized_name:
                    filtered_items.append((localized_name, item_data))
                    if item_id:
                        seen_ids.add(item_id)
                elif 'en' in names_dict:
                    # Fallback to English if selected language not available
                    filtered_items.append((names_dict['en'], item_data))
                    if item_id:
                        seen_ids.add(item_id)
            else:
                # Legacy format: just use the name field
                base_name = item_data.get('name')
                if base_name:
                    filtered_items.append((base_name, item_data))
                    if item_id:
                        seen_ids.add(item_id)
        
        return filtered_items

    def _find_best_match(self, candidates: List[str], item_names: List[str], name_to_actual: dict) -> Tuple[Optional[str], float]:
        """
        Find the best matching item name from candidates.
        Uses multiple matching strategies and picks the best overall result.
        """
        best_name, best_score = None, 0
        
        # Create normalized versions of item names for secondary matching
        # This helps match "TACTICALMK.2" to "Tactical Mk. 2"
        item_names_lower = [name.lower() for name in item_names]
        lower_to_actual = {name.lower(): name for name in item_names}
        normalized_to_actual = {normalize_for_matching(name): name for name in item_names}
        normalized_items = list(normalized_to_actual.keys())
        
        all_matches: List[Tuple[str, float, str]] = []  # (item_name, score, method)
        
        for candidate in candidates:
            if len(candidate) < 3:
                continue
                
            candidate_lower = candidate.lower()
            candidate_normalized = normalize_for_matching(candidate)
            
            if _HAS_RAPIDFUZZ:
                # Strategy 1: WRatio - best for handling length differences and partial matches
                result = process.extractOne(candidate_lower, item_names_lower, scorer=fuzz.WRatio)
                if result and result[1] > 0:
                    all_matches.append((lower_to_actual[result[0]], result[1], "WRatio"))
                
                # Strategy 2: Normalized matching (no spaces/punctuation)
                # This helps when OCR removes spaces like "TACTICALMK.2" -> "tacticalmk2"
                result_norm = process.extractOne(candidate_normalized, normalized_items, scorer=fuzz.ratio)
                if result_norm and result_norm[1] > 0:
                    actual_name = normalized_to_actual[result_norm[0]]
                    # Boost score slightly for normalized matches that are very close in length
                    len_diff = abs(len(candidate_normalized) - len(result_norm[0]))
                    length_bonus = max(0, 10 - len_diff * 2)  # Up to 10 bonus points for same length
                    boosted_score = min(100, result_norm[1] + length_bonus)
                    all_matches.append((actual_name, boosted_score, "Normalized"))
                
                # Strategy 3: Token sort ratio for handling word order differences
                result_token = process.extractOne(candidate_lower, item_names_lower, scorer=fuzz.token_sort_ratio)
                if result_token and result_token[1] > 0:
                    all_matches.append((lower_to_actual[result_token[0]], result_token[1], "TokenSort"))
            else:
                # Fallback for difflib (slower/less accurate)
                matches = difflib.get_close_matches(candidate_lower, item_names_lower, n=1, cutoff=0.5)
                if matches:
                    score = difflib.SequenceMatcher(None, candidate_lower, matches[0]).ratio() * 100
                    all_matches.append((lower_to_actual[matches[0]], score, "Difflib"))
            
            # --- NEW: Direct Substring/Prefix Boost ---
            # If the candidate perfectly matches the start of an item name, give it a massive boost
            # This runs regardless of which fuzzy library is used
            for item_name_l in item_names_lower:
                if item_name_l.startswith(candidate_lower) or candidate_lower in item_name_l:
                    actual = lower_to_actual[item_name_l]
                    # Simple scoring for exact substring
                    score = 90 if item_name_l.startswith(candidate_lower) else 80
                    all_matches.append((actual, score, "Substring"))
        
        # Find the best match across all strategies
        # Prefer higher scores, and for ties prefer matches with similar length to candidate
        if all_matches:
            # Sort by score descending
            all_matches.sort(key=lambda x: x[1], reverse=True)
            
            # Debug: show top matches
            if self.cmd_config.debug and len(all_matches) > 0:
                print(f"[DEBUG] Top 3 matches:")
                for i, (name, score, method) in enumerate(all_matches[:3]):
                    print(f"  {i+1}. '{name}' = {score:.1f} ({method})")
            
            best_name, best_score, _ = all_matches[0]
        
        return best_name, best_score

    def scan_screen(self, full_screen: bool = False) -> Optional[Dict[str, Any]]:
        """
        Captures screen, processes image, runs OCR, finds item, and gathers all data.
        Returns a dictionary of item data or None if nothing found.
        """
        # If user setting says full screen mode is ON, override the parameter
        if self.full_screen_mode:
            full_screen = True

        # Prepare Debug Paths
        debug_path = None
        debug_prefix = None
        if self.save_debug_images:
            debug_path = os.path.join(os.path.expanduser("~"), "Pictures", "ArcCompanion_Debug")
            os.makedirs(debug_path, exist_ok=True)
            debug_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. Capture Image
        # The ImageProcessor now uses MSS (Fast) + OpenCV (Accuracy)
        img = ImageProcessor.capture_and_process(self.target_color, full_screen=full_screen, debug_path=debug_path, debug_prefix=debug_prefix)
        
        if img is None:
            return None
        
        # --- DEBUG: SAVE RAW TOOLTIP IMAGE (Cropped Result) ---
        if self.save_debug_images and debug_path and debug_prefix:
            try:
                cropped_filename = f"{debug_prefix}_tooltip_result.png"
                img.save(os.path.join(debug_path, cropped_filename))
            except Exception as e:
                print(f"Failed to save debug cropped image: {e}")
        # ---------------------------------------
        
        # --- OPTIMIZATION: Crop to Header (with minimum height for small tooltips) ---
        w, h = img.size
        if self.cmd_config.debug:
            print(f"[DEBUG] Tooltip size: {w}x{h}")
        
        if h > 100:
            # For small/medium tooltips, use a larger percentage to not cut off the name
            # For larger tooltips, 30% is enough to get just the header
            # 400px+ are the big detailed tooltips where 30% works fine
            crop_percent = 0.50 if h < 400 else 0.30
            crop_height = max(100, int(h * crop_percent))  # At least 100px for the name
            if self.cmd_config.debug:
                print(f"[DEBUG] Cropping to {crop_height}px ({crop_percent*100:.0f}% of {h})")
            img = img.crop((0, 0, w, crop_height))
        else:
            if self.cmd_config.debug:
                print(f"[DEBUG] Tooltip too small to crop, using full height")
        # ----------------------------------------------
        
        # --- FIX: Trim edges to remove artifacts from screen boundaries ---
        # When tooltips are near screen edges, we sometimes capture gray bars or
        # UI elements that corrupt the OCR. Trim a few pixels from all edges.
        w, h = img.size
        edge_trim = 10 if w > 100 else 5  # Smaller trim for narrow images
        if w > edge_trim * 2 and h > edge_trim * 2:
            img = img.crop((edge_trim, 0, w - edge_trim, h))  # Trim left and right edges
        # -----------------------------------------------------------------

        # 3. Enhance Image for OCR (Using OpenCV - much faster than PIL)
        img_np = np.array(img)
        
        # Convert to Grayscale
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_np

        # Rescale if too small (Tesseract loves ~30-40px high text)
        # If the image height is small, upscale it
        if h < 200:
            scale_factor = 2.0
            gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

        # High Contrast / Thresholding
        # We use simple thresholding or adaptive thresholding for better OCR
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Convert back to PIL for Tesseract (pytesseract expectation)
        img = Image.fromarray(thresh)
        
        # --- DEBUG: SAVE PROCESSED HEADER IMAGE ---
        if self.save_debug_images and debug_path and debug_prefix:
            try:
                processed_filename = f"{debug_prefix}_processed_header.png"
                img.save(os.path.join(debug_path, processed_filename))
            except Exception as e:
                print(f"Failed to save debug processed image: {e}")
        # ---------------------------------------
        
        # 4. Setup Language / Tesseract Config
        custom_lang_file = os.path.join(Constants.TESSDATA_DIR, f"{self.ocr_lang_code}.traineddata")
        
        # Determine effective language
        if os.path.exists(custom_lang_file):
            os.environ["TESSDATA_PREFIX"] = Constants.TESSDATA_DIR
            lang = self.ocr_lang_code
        else:
            if "TESSDATA_PREFIX" in os.environ: del os.environ["TESSDATA_PREFIX"]
            if self.ocr_lang_code != 'eng':
                print(f"[WARN] Language file for '{self.ocr_lang_code}' not found. Falling back to 'eng'.")
            lang = 'eng'

        # Optimized Flags:
        # --oem 1: Use LSTM engine (standard/fast)
        # --psm 6: Assume a single uniform block of text
        # -c tessedit_do_invert=0: Don't spend time trying to invert colors
        tess_options = "--psm 6 --oem 1 -c tessedit_do_invert=0"

        # Apply whitelist ONLY if English is selected
        if lang == 'eng':
            # Whitelist: a-z, A-Z, 0-9, Hyphen, Period, Parentheses
            whitelist = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.() "
            tess_config = f"{tess_options} -c tessedit_char_whitelist={whitelist}"
        else:
            tess_config = tess_options
        
        # 5. Run OCR
        try:
            raw_text = pytesseract.image_to_string(img, lang=lang, config=tess_config)
            lines = raw_text.splitlines()
        except Exception as e:
            print(f"[Error] OCR Failed: {e}")
            return None

        if not lines: 
            return None
            
        # 6. Clean Text
        # I have kept the period . and parens () but moved the dash - to the end so it doesn't crash.
        cleaned = [re.sub(r'[^a-zA-Z0-9\s.\(\)-]', '', l).strip() for l in lines if len(l.strip()) >= 3]
        
        # --- DEBUG PRINT ADDED HERE ---
        print(f"[DEBUG] OCR Raw Text: {cleaned}")
        # ------------------------------
        
        # 7. Fuzzy Match against Database (LANGUAGE-FILTERED)
        # Only search against item names in the currently selected language
        filtered_items = self._get_language_filtered_items()
        item_names = [name for name, _ in filtered_items]
        name_to_item = {name: item for name, item in filtered_items}
        
        if self.cmd_config.debug:
            print(f"[DEBUG] Searching against {len(item_names)} items in language '{self.json_lang_code}'")
        
        # Create candidates (single lines + combined adjacent lines for multi-line names)
        search_candidates = cleaned + [f"{cleaned[i]} {cleaned[i+1]}" for i in range(len(cleaned) - 1)] if len(cleaned) > 1 else cleaned
        
        # Fix common OCR errors with Roman numerals (Il -> II, Ill -> III, etc.)
        search_candidates = [fix_roman_numeral_ocr(c) for c in search_candidates]
        
        if self.cmd_config.debug:
            print(f"[DEBUG] Candidates after Roman numeral fix: {search_candidates}")
        
        best_name, best_score = self._find_best_match(search_candidates, item_names, name_to_item)

        # Apply minimum threshold
        if best_score < 65:  # Slightly lowered from 70 since we have better matching now
            best_name = None

        if self.cmd_config.debug: 
            print(f"[DEBUG] Best Match: '{best_name}' with score {best_score}")

        if not best_name:
            return None

        # 8. Aggregate Data
        print(f"Item Found: {best_name}. gathering data...")
        item_details = self.data_manager.get_item_by_name(best_name)
        item_id = item_details.get('id') if item_details else None
        
        user_note = self.data_manager.get_item_note(item_id) if item_id else ""
        stash_count = self.data_manager.get_stash_count(item_id) if item_id else 0
        
        # Blueprint Logic
        is_bp = False
        is_collected_bp = False
        if item_details:
            is_bp = (item_details.get('type') == "Blueprint") or ("Blueprint" in item_details.get('name', ''))
            if is_bp:
                is_collected_bp = stash_count > 0

        # Construct final data packet
        return {
            "item": item_details, 
            "trade": self.data_manager.find_trades_for_item(best_name),
            "hideout": self.data_manager.find_hideout_requirements(best_name, lang_code=self.json_lang_code), 
            "project": self.data_manager.find_project_requirements(best_name, lang_code=self.json_lang_code),
            "quest": self.data_manager.find_quest_item_requirements(best_name, lang_code=self.json_lang_code),
            "blueprint": is_bp,
            "note": user_note,
            "stash_count": stash_count,
            "is_collected_bp": is_collected_bp
        }