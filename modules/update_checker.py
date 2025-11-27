from PyQt6.QtCore import QObject, pyqtSignal
import requests
import json
import os
from .constants import Constants

# The URL for the GitHub API to get the file tree of the repository
GITHUB_API_URL = "https://api.github.com/repos/Joopz0r/arcraiders-data/git/trees/main?recursive=1"
# The base URL for downloading the raw file content
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Joopz0r/arcraiders-data/main/"

# --- MODIFIED: This list now matches the structure of the GITHUB REPOSITORY ---
# We will look for these paths at the root of the remote repository.
MANAGED_PATHS = [
    'items/',
    'hideout/',
    'quests/',
    'images/',
    'projects.json',
    'trades.json'
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
            response = requests.get(GITHUB_API_URL, timeout=10)
            response.raise_for_status()
            remote_files = response.json()
        except requests.exceptions.RequestException as e:
            self.update_check_finished.emit([], f"Error: Could not connect to GitHub. ({e})")
            return

        remote_versions = {}
        for file_info in remote_files.get('tree', []):
            path = file_info.get('path')
            if file_info.get('type') == 'blob' and any(path.startswith(p) for p in MANAGED_PATHS):
                remote_versions[path] = file_info.get('sha')
        
        files_to_download = []
        for path, remote_sha in remote_versions.items():
            local_sha = self.local_versions.get(path)
            if local_sha != remote_sha:
                files_to_download.append({'path': path, 'sha': remote_sha})
        
        if not files_to_download:
            self.update_check_finished.emit([], "You are up to date!")
        else:
            self.update_check_finished.emit(files_to_download, f"{len(files_to_download)} new or updated files found.")

    def download_updates(self, files_to_download):
        """Downloads the list of files provided by the check."""
        total_files = len(files_to_download)
        for i, file_info in enumerate(files_to_download):
            path = file_info['path']
            sha = file_info['sha']
            self.download_progress.emit(i + 1, total_files, os.path.basename(path))

            try:
                download_url = GITHUB_RAW_URL + path
                file_content_response = requests.get(download_url, timeout=10)
                file_content_response.raise_for_status()

                # --- MODIFIED: Construct the correct LOCAL save path ---
                # This prepends our "data/" directory to the path received from GitHub.
                # e.g., GitHub's "items/gun.json" becomes local "data/items/gun.json"
                local_path = os.path.join(Constants.DATA_DIR, path)
                # --------------------------------------------------------

                dir_name = os.path.dirname(local_path)
                if not os.path.exists(dir_name):
                    os.makedirs(dir_name)

                with open(local_path, 'wb') as f:
                    f.write(file_content_response.content)
                
                # The key in our versions file should still be the GitHub path for future checks
                self.local_versions[path] = sha

            except requests.exceptions.RequestException as e:
                self.update_complete.emit(False, f"Error downloading {path}: {e}")
                return

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