from PyQt6.QtCore import QObject, pyqtSignal
import requests
import json
import os
from modules.core.constants import Constants
from concurrent.futures import ThreadPoolExecutor, as_completed

# The base URL for downloading the raw file content
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Joopz0r/arcraiders-data/main/"
# URL for the raw versions.json manifest, bypassing Git Tree API limits
REMOTE_MANIFEST_URL = "https://raw.githubusercontent.com/Joopz0r/arcraiders-data/main/versions.json"

# --- MODIFIED: Added maps.json to managed paths ---
MANAGED_PATHS = [
    'items/',
    'hideout/',
    'quests/',
    'images/',
    'projects.json',
    'trades.json',
    'maps.json'
]
# --------------------------------------------------------------------------

class UpdateChecker(QObject):
    """
    Runs on a background thread to check for and download data updates
    from the GitHub repository without freezing the UI.
    """
    checking_for_updates = pyqtSignal()
    update_check_finished = pyqtSignal(list, str)
    download_progress = pyqtSignal(int, int, str)
    update_complete = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.local_versions = self._load_local_versions()

    def _load_local_versions(self):
        """Loads the local versions.json file, or returns an empty dict if not found."""
        versions_path = os.path.join(Constants.DATA_DIR, 'versions.json')
        if os.path.exists(versions_path):
            try:
                with open(versions_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def run_check(self):
        """The main entry point to start checking for updates."""
        self.checking_for_updates.emit()
        
        try:
            # Download the raw versions.json directly to bypass API rate limits
            response = requests.get(REMOTE_MANIFEST_URL, timeout=10)
            response.raise_for_status()
            remote_versions_map = response.json()
        except requests.exceptions.RequestException as e:
            self.update_check_finished.emit([], f"Error: Could not connect to GitHub. ({e})")
            return
        except json.JSONDecodeError:
            self.update_check_finished.emit([], "Error: Invalid version data received.")
            return

        files_to_download = []
        
        # The raw versions.json is a simple flat dictionary ({"path": "hash"})
        if isinstance(remote_versions_map, dict):
            for path, remote_sha in remote_versions_map.items():
                # Filter by managed paths
                if any(path.startswith(p) for p in MANAGED_PATHS):
                    local_sha = self.local_versions.get(path)
                    if local_sha != remote_sha:
                        files_to_download.append({'path': path, 'sha': remote_sha})
        
        if not files_to_download:
            self.update_check_finished.emit([], "You are up to date!")
        else:
            self.update_check_finished.emit(files_to_download, f"{len(files_to_download)} new or updated files found.")

    def _download_single_file(self, file_info):
        """Helper to download a single file. Returns (success, path, error_msg/None)."""
        path = file_info['path']
        request_url = GITHUB_RAW_URL + path
        try:
            response = requests.get(request_url, timeout=10)
            response.raise_for_status()
            
            local_path = os.path.join(Constants.DATA_DIR, path)
            dir_name = os.path.dirname(local_path)
            if not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            return True, path, None
        except Exception as e:
            return False, path, str(e)

    def download_updates(self, files_to_download):
        """Downloads the list of files provided by the check using parallel threads."""
        total_files = len(files_to_download)
        
        # Use ThreadPoolExecutor for parallel downloads
        # Limiting max_workers to 8 to avoid overwhelming the network or system
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Create a map of future -> file_info
            future_to_file = {
                executor.submit(self._download_single_file, f): f 
                for f in files_to_download
            }
            
            completed_count = 0
            errors = []
            
            for future in as_completed(future_to_file):
                completed_count += 1
                success, path, error_msg = future.result()
                
                # Emit progress for each completed file
                self.download_progress.emit(completed_count, total_files, os.path.basename(path))
                
                if success:
                    # Update local version only on success
                    # Need to find the sha for this path
                    for item in files_to_download:
                        if item['path'] == path:
                            self.local_versions[path] = item['sha']
                            break
                else:
                    errors.append(f"{path}: {error_msg}")

        if errors:
            # If there were errors, show the first one (or a summary)
            self.update_complete.emit(False, f"Failed to download {len(errors)} files. First error: {errors[0]}")
        else:
            # Save the new versions.json
            versions_path = os.path.join(Constants.DATA_DIR, 'versions.json')
            try:
                with open(versions_path, 'w', encoding='utf-8') as f:
                    json.dump(self.local_versions, f, indent=2)
                self.update_complete.emit(True, "Update successful! Please restart the application for changes to take effect.")
            except IOError as e:
                self.update_complete.emit(False, f"Error saving new version file: {e}")

    def download_language(self, lang_code):
        """Downloads a specific Tesseract language file."""
        filename = f"{lang_code}.traineddata"
        # Using tessdata_fast for better performance/size ratio
        url = f"https://github.com/tesseract-ocr/tessdata_fast/raw/main/{filename}"
        target_path = os.path.join(Constants.TESSDATA_DIR, filename)
        
        if os.path.exists(target_path):
            self.update_complete.emit(True, f"Language data for {lang_code} is already installed.")
            return

        self.download_progress.emit(0, 100, f"Downloading {filename}...")
        
        try:
            os.makedirs(Constants.TESSDATA_DIR, exist_ok=True)
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Emit progress as percentage if we know total size
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.download_progress.emit(percent, 100, f"Downloading {filename}")
            
            self.update_complete.emit(True, f"Successfully downloaded {filename}")
            
        except Exception as e:
            if os.path.exists(target_path): os.remove(target_path)
            self.update_complete.emit(False, f"Failed to download language data: {e}")