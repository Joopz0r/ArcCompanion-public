import os
import sys
import subprocess
import requests
import uuid
import hashlib
from PyQt6.QtCore import QObject, pyqtSignal

class AppUpdateChecker(QObject):
    """
    Checks a JSON file on a website to see if a newer version of the application is available.
    Also sends a hashed hardware ID to the server for anonymous usage tracking.
    
    Expected JSON format on website:
    {
        "version": "1.0.1",
        "download_url": "https://website.com/download",
        "exe_url": "https://website.com/downloads/ArcCompanion.exe"
    }
    """
    update_available = pyqtSignal(str, str, str) # (new_version_str, download_url, exe_url)
    update_progress = pyqtSignal(int)
    update_ready = pyqtSignal(str) # local_path
    check_finished = pyqtSignal() 

    def __init__(self, current_version, version_url):
        super().__init__()
        self.current_version = current_version
        self.version_url = version_url

    def _get_device_id(self):
        """Generates a hashed unique ID based on MAC address."""
        try:
            mac_address = uuid.getnode()
            mac_str = str(mac_address).encode('utf-8')
            # Hash it for privacy
            return hashlib.sha256(mac_str).hexdigest()[:16]
        except Exception:
            return "unknown_device"

    def run_check(self):
        try:
            # Generate the unique ID
            hwid = self._get_device_id()
            
            # Add ID and Version to request parameters
            params = {
                'uid': hwid,
                'current_version': self.current_version
            }
            
            # The server will log: GET /app_version.json?uid=...&current_version=1.0.0
            response = requests.get(self.version_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            remote_version = data.get("version", "0.0.0")
            download_url = data.get("download_url", "")
            exe_url = data.get("exe_url", "")

            if self._is_newer(remote_version, self.current_version):
                self.update_available.emit(remote_version, download_url, exe_url)
            else:
                self.check_finished.emit()

        except Exception as e:
            print(f"[AppUpdater] Check failed: {e}")
            self.check_finished.emit()

    def download_exe(self, url):
        """Downloads the new EXE to a temporary location."""
        try:
            temp_path = os.path.join(os.environ.get('TEMP', os.getcwd()), "ArcCompanion_new.exe")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.update_progress.emit(progress)
            
            self.update_ready.emit(temp_path)
        except Exception as e:
            print(f"[AppUpdater] Download failed: {e}")
            self.update_progress.emit(-1) # Error signal

    def apply_update(self, new_exe_path):
        """Creates a batch script to replace the current EXE and restarts the app."""
        try:
            current_exe = sys.executable
            if not current_exe.endswith(".exe"):
                # Not running as frozen EXE, just exit
                print("[AppUpdater] Not running as EXE, skipping update application.")
                return

            # Check for Write Permissions
            install_dir = os.path.dirname(current_exe)
            needs_admin = not os.access(install_dir, os.W_OK)

            batch_path = os.path.join(os.environ.get('TEMP', os.getcwd()), "update_arc_companion.bat")
            
            # Use 'timeout' for a small delay to ensure the app has closed
            # The 'start ""' is important to launch the new app without waiting
            batch_content = f"""@echo off
taskkill /F /PID {os.getpid()} >nul 2>&1
timeout /t 2 /nobreak >nul
copy /y "{new_exe_path}" "{current_exe}"
if exist "{current_exe}" (
    start "" "{current_exe}"
    del "{new_exe_path}"
)
del "%~f0"
"""
            with open(batch_path, "w") as f:
                f.write(batch_content)
            
            if needs_admin:
                print("[AppUpdater] Elevating privileges for update...")
                import ctypes
                # ShellExecute with 'runas' triggers the UAC prompt
                # 1 = SW_SHOWNORMAL (show window)
                # 0 = SW_HIDE (hide window) - using 0 to avoid flashing a big admin cmd window if possible, 
                # but for feedback 1 is safer so users see why it's taking time.
                ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f"/c \"{batch_path}\"", None, 1)
            else:
                # Run normally
                subprocess.Popen([batch_path], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            
            sys.exit(0)
        except Exception as e:
            print(f"[AppUpdater] Apply update failed: {e}")

    def _is_newer(self, remote_ver, local_ver):
        """
        Simple helper to compare version strings like '1.0.2' vs '1.0.1'.
        Returns True if remote_ver > local_ver.
        """
        try:
            r_parts = [int(x) for x in remote_ver.split('.')]
            l_parts = [int(x) for x in local_ver.split('.')]
            return r_parts > l_parts
        except ValueError:
            # Fallback for non-integer version schemes
            return remote_ver > local_ver