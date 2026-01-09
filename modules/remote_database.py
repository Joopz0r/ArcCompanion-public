from PyQt6.QtCore import QObject, pyqtSignal
import requests
import json
import re
import os
from pathlib import Path
from .constants import Constants

try:
    import demjson3
    HAS_DEMJSON3 = True
except ImportError:
    HAS_DEMJSON3 = False
    print("Warning: demjson3 not available. Remote database download will not work.")


class RemoteDatabaseDownloader(QObject):
    """
    Downloads and parses item database from a remote JavaScript file,
    then merges recommendation data into local item JSON files.
    """
    download_progress = pyqtSignal(str)  # Status message
    download_complete = pyqtSignal(bool, str)  # success, message
    status_update = pyqtSignal(str)  # General status updates

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.items_raw_file = Path(Constants.DATA_DIR) / "items_raw.json"
        self.items_dir = Path(Constants.ITEMS_DIR)

    def set_ready_status(self, ready=True):
        """Update ready indicator (for UI status)"""
        status = "Ready" if ready else "Not Ready"
        self.status_update.emit(status)

    def download_database(self):
        """Download and parse the item database from web, then merge with /items"""
        if not HAS_DEMJSON3:
            self.download_complete.emit(False, "demjson3 library is not installed. Please install it via: pip install demjson3")
            return False

        try:
            self.download_progress.emit("Downloading database...")
            self.set_ready_status(False)

            # Get URL from config
            database_url = self.config_manager.get_remote_database_url()
            if not database_url:
                self.download_complete.emit(False, "Database URL is not configured.")
                return False

            # Download JavaScript file containing item data
            resp = requests.get(database_url, timeout=30)
            resp.raise_for_status()
            js_text = resp.text

            self.download_progress.emit("Parsing database...")

            # Find the array containing item data (const q = [...])
            match = re.search(r"const\s+q\s*=\s*\[", js_text)
            if not match:
                raise RuntimeError("Could not locate item dataset in JavaScript file")

            # Extract the full array by matching brackets
            start_pos = match.end() - 1
            bracket_count = 0
            in_string = False
            escape_next = False
            string_char = None

            # Parse through characters to find matching closing bracket
            for i in range(start_pos, len(js_text)):
                char = js_text[i]

                # Handle escape sequences
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                # Handle string literals
                if char in ('"', "'", '`') and not in_string:
                    in_string = True
                    string_char = char
                    continue
                elif char == string_char and in_string:
                    in_string = False
                    string_char = None
                    continue

                # Count brackets only outside strings
                if not in_string:
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            q_array = js_text[start_pos:i + 1]
                            break
            else:
                raise RuntimeError("Could not find matching closing bracket for item array")

            # Parse JavaScript array to Python list using demjson3
            items = demjson3.decode(q_array)

            # Save to items_raw.json (optional, for debugging)
            try:
                self.items_raw_file.parent.mkdir(parents=True, exist_ok=True)
                self.items_raw_file.write_text(
                    json.dumps(items, indent=2),
                    encoding="utf-8"
                )
            except Exception as e:
                print(f"Warning: Could not save items_raw.json: {e}")

            # Merge recommendations into /items folder
            self.download_progress.emit("Merging recommendations...")
            merged_count = self.merge_recommendations(items)

            self.download_complete.emit(True, f"Successfully downloaded and merged {merged_count} recommendations.")
            self.set_ready_status(True)
            return True

        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)[:100]}"
            self.download_complete.emit(False, error_msg)
            self.set_ready_status(False)
            return False
        except Exception as e:
            error_msg = f"Error: {str(e)[:100]}"
            self.download_progress.emit(f"✗ {error_msg}")
            self.download_complete.emit(False, error_msg)
            self.set_ready_status(False)
            return False

    def merge_recommendations(self, raw_items):
        """Merge recommendation data from raw items into /items/*.json files"""
        if not self.items_dir.exists():
            return 0

        # Create recommendation lookup
        recommendations = {}
        for item in raw_items:
            item_id = item.get("id", "")
            recommendation = item.get("recommendation", "")
            if item_id and recommendation:
                recommendations[item_id] = recommendation

        merged_count = 0

        # Update each file in /items
        for item_file in self.items_dir.glob("*.json"):
            try:
                with open(item_file, 'r', encoding='utf-8') as f:
                    item_data = json.load(f)

                item_id = item_data.get("id", "")

                # Only update if no recommendation exists
                if "recommendation" not in item_data or not item_data["recommendation"]:
                    if item_id in recommendations:
                        item_data["recommendation"] = recommendations[item_id]

                        with open(item_file, 'w', encoding='utf-8') as f:
                            json.dump(item_data, f, indent=2, ensure_ascii=False)
                        merged_count += 1
            except Exception as e:
                print(f"Warning: Could not merge recommendation for {item_file.name}: {e}")

        return merged_count
