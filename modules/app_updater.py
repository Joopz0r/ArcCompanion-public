from PyQt6.QtCore import QObject, pyqtSignal
import requests
import uuid
import hashlib

class AppUpdateChecker(QObject):
    """
    Checks a JSON file on a website to see if a newer version of the application is available.
    Also sends a hashed hardware ID to the server for anonymous usage tracking.
    
    Expected JSON format on website:
    {
        "version": "1.0.1",
        "download_url": "https://website.com/download"
    }
    """
    update_available = pyqtSignal(str, str) # (new_version_str, download_url)
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

            if self._is_newer(remote_version, self.current_version):
                self.update_available.emit(remote_version, download_url)
            else:
                self.check_finished.emit()

        except Exception as e:
            print(f"[AppUpdater] Check failed: {e}")
            self.check_finished.emit()

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