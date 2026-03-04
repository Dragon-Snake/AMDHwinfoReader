"""
AMD Performance Monitor Service
Runs in the background as a Windows Service and logs GPU stats to performance.json
"""

import os
import sys
import json
import time
import threading
import logging
from pathlib import Path
import winreg
import win32ts
import win32service
import win32serviceutil
import win32event
import servicemanager
import requests
import re
import subprocess
import socket
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from logging.handlers import RotatingFileHandler

# -------------------------
# Update Checker
# -------------------------

CURRENT_VERSION = "0.0.2.5"
SCRIPT_URL = "https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/main/amd_hwinfo_monitor.py"
SERVICE_NAME = "AMDPerfMonitor"
UPDATE_CHECK_INTERVAL = 60*60*2  # check every 2 hours

def parse_version(version_str):
    return tuple(int(x) for x in version_str.split("."))


def is_newer_version(remote, local):
    return parse_version(remote) > parse_version(local)

def extract_version_from_script(script_text):
    match = re.search(r'CURRENT_VERSION\s*=\s*"([^"]+)"', script_text)
    if match:
        return match.group(1)
    return None

def read_local_script_version():
    current_file = Path(sys.argv[0])
    try:
        text = current_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("Failed to read as UTF-8, falling back to latin1")
        text = current_file.read_text(encoding="latin1")  # safe for regex parsing

    version = extract_version_from_script(text)
    if version:
        return version

    return CURRENT_VERSION

def create_session():
    session = requests.Session()

    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session

def check_for_updates():
    try:
        logger.info("Checking for updates...")

        session = create_session()

        try:
            r = session.get(SCRIPT_URL, timeout=(5, 10))
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error during update check: {e}")
            return

        if r.status_code != 200:
            logger.warning(f"Failed to download script ({r.status_code})")
            return

        remote_script = r.text
        remote_version = extract_version_from_script(remote_script)

        if not remote_version:
            logger.warning("Could not extract remote version.")
            return

        local_version = read_local_script_version()

        logger.info(f"Remote: {remote_version} | Local: {local_version}")

        if not is_newer_version(remote_version, local_version):
            logger.info("Already up to date.")
            return

        logger.info(f"New version available: {remote_version}")
        perform_update(remote_script, remote_version)

    except Exception as e:
        logger.warning(f"Update check failed: {e}")

def perform_update(new_script_text, new_version):
    try:
        logger.info("Preparing update...")

        current_file = Path(sys.argv[0])
        program_dir = current_file.parent

        temp_file = program_dir / "amd_update.tmp"
        backup_file = program_dir / "amd_backup.bak"
        bat_file = program_dir / "update_restart.bat"

        temp_file.write_text(new_script_text, encoding="utf-8")

        bat_file.write_text(f"""@echo off
sc stop {SERVICE_NAME}
timeout /t 5 >nul

echo Backing up current file...
copy /y "{current_file}" "{backup_file}"

echo Replacing file...
copy /y "{temp_file}" "{current_file}"

echo Starting service...
sc start {SERVICE_NAME}
timeout /t 5 >nul

sc query {SERVICE_NAME} | find "RUNNING" >nul
if errorlevel 1 (
    echo Service failed to start. Restoring backup...
    copy /y "{backup_file}" "{current_file}"
    sc start {SERVICE_NAME}
)

del "{temp_file}"
del "%~f0"
""")

        subprocess.Popen(
            ["cmd", "/c", str(bat_file)],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        logger.info("Update process launched.")

    except Exception as e:
        logger.exception(f"Update failed: {e}")


# -------------------------
# Config and Logging
# -------------------------

PROGRAM_DATA_DIR = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "AMDPerformanceMonitor"
PROGRAM_DATA_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = PROGRAM_DATA_DIR / "amd_performance.log"
handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1_000_000,   # 1 MB per file
    backupCount=3,       # keep 3 old logs
    encoding="utf-8"
)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)

handler.setFormatter(formatter)

logger = logging.getLogger("AMDPerfMonitor")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False
logger.info("Logging initialized with rotation.")

CONFIG_FILE = PROGRAM_DATA_DIR / "config.json"
DEFAULT_CONFIG = {
    "poll_interval": 1,
    "gpu_adapter": 0,
    "collect": {
        "hwinfo": True
    }
}

# -------------------------
# Helper Functions
# -------------------------

def get_active_user_profile_dir():
    try:
        session_id = win32ts.WTSGetActiveConsoleSessionId()

        if session_id == 0xFFFFFFFF:
            return None  # No active session (normal)

        try:
            user_token = win32ts.WTSQueryUserToken(session_id)
        except Exception as e:
            # Suppress normal "token does not exist" (1008)
            if "1008" in str(e):
                return None
            logger.warning(f"Unexpected WTS token error: {e}")
            return None

        import win32profile
        profile_dir = win32profile.GetUserProfileDirectory(user_token)
        return Path(profile_dir)

    except Exception as e:
        logger.warning(f"Unexpected user profile error: {e}")
        return None

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}  # merge with defaults
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}")
    return DEFAULT_CONFIG.copy()

def _extract_hwinfo_raw():
    raw = {}
    base_path = r"SOFTWARE\HWiNFO64\VSB"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as key:
            i = 0
            while True:
                try:
                    label = winreg.QueryValueEx(key, f"Label{i}")[0]
                    value_raw = winreg.QueryValueEx(key, f"Value{i}")[0]

                    if label:
                        raw[label] = value_raw

                    i += 1
                except FileNotFoundError:
                    break  # End of values (normal)

    except FileNotFoundError:
        # HWiNFO not running or VSB not available (normal)
        return raw
    except Exception as e:
        logger.warning(f"Unexpected HWiNFO registry error: {e}")

    return raw

def _classify_hwinfo(raw_sensors):
    structured = {
        "gpu": {},
        "cpu": {},
        "memory": {},
        "other": {}
    }

    for label, value in raw_sensors.items():
        lower = label.lower()

        if _is_gpu(label, lower):
            structured["gpu"][label] = value
        elif _is_cpu(label, lower):
            structured["cpu"][label] = value
        elif _is_memory(label, lower):
            structured["memory"][label] = value
        else:
            structured["other"][label] = value

    return structured

def _is_gpu(label, lower):
    return any(keyword in lower for keyword in [
        "gpu", "graphics", "d3d"
    ])

def _is_cpu(label, lower):
    return any(keyword in lower for keyword in [
        "cpu", "core", "package"
    ])

def _is_memory(label, lower):
    return any(keyword in lower for keyword in [
        "memory", "ram", "dimm"
    ])

def collect_amd_stats(config):
    stats = {}

    if config.get("collect", {}).get("hwinfo", False):
        stats["hwinfo"] = read_hwinfo_sensors()

    return stats

# -------------------------
# Windows Service
# -------------------------

class AMDPerfMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "AMDPerfMonitor"
    _svc_display_name_ = "AMD Performance Monitor Service"
    _svc_description_ = "Monitors AMD GPU stats from HWiNFO and logs locally (no web service)."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.config = load_config()
        self.data_file = PROGRAM_DATA_DIR / "performance.json"
        self.monitor_thread = None
        self.hwinfo_available = None

    def SvcStop(self):
        logger.info("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

        self.running = False
        win32event.SetEvent(self.hWaitStop)

        for t in [self.monitor_thread, getattr(self, "update_thread", None)]:
            if t and t.is_alive():
                t.join(timeout=5)

        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        logger.info("Service stopped cleanly.")

    def SvcDoRun(self):
        logger.info("AMD Performance Monitor Service starting...")
        servicemanager.LogInfoMsg("AMD Service starting...")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        
        self.running = True

        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        # Start update check thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

        # Keep main thread alive, allow fast stop
        while self.running:
            result = win32event.WaitForSingleObject(self.hWaitStop, 1000)
            if result == win32event.WAIT_OBJECT_0:
                self.running = False
                break

    def read_hwinfo_sensors(self):
        raw_sensors = _extract_hwinfo_raw()
        available = bool(raw_sensors)

        if self.hwinfo_available is None:
            self.hwinfo_available = available

        elif available != self.hwinfo_available:
            if available:
                logger.info("HWiNFO sensors detected.")
            else:
                logger.info("HWiNFO sensors unavailable.")
            self.hwinfo_available = available

        return _classify_hwinfo(raw_sensors)

    def monitor_loop(self):
        while self.running:
            try:
                stats = {}

                if self.config.get("collect", {}).get("hwinfo", False):
                    stats["hwinfo"] = self.read_hwinfo_sensors()
                    
                # Write main ProgramData file
                tmp_file = self.data_file.with_suffix(".tmp")
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)

                tmp_file.replace(self.data_file)

                # Write per-user file (if active user exists)
                user_profile = get_active_user_profile_dir()
                if user_profile:
                    user_dir = user_profile / "AMDPerformanceMonitor"
                    user_dir.mkdir(parents=True, exist_ok=True)

                    user_file = user_dir / "performance.json"

                    user_tmp = user_file.with_suffix(".tmp")
                    with open(user_tmp, "w", encoding="utf-8") as f:
                        json.dump(stats, f, ensure_ascii=False, indent=2)

                    user_tmp.replace(user_file)
            except Exception as e:
                logger.exception(f"Error collecting AMD stats: {e}")

            # Wait instead of sleep (interruptible)
            wait_time_ms = int(self.config.get("poll_interval", 1) * 1000)
            result = win32event.WaitForSingleObject(self.hWaitStop, wait_time_ms)

            if result == win32event.WAIT_OBJECT_0:
                break

    def update_loop(self):
        while self.running:
            check_for_updates()

            # Wait exactly UPDATE_CHECK_INTERVAL, interruptible
            wait_time_ms = UPDATE_CHECK_INTERVAL * 1000
            result = win32event.WaitForSingleObject(self.hWaitStop, wait_time_ms)

            if result == win32event.WAIT_OBJECT_0:
                break

# -------------------------
# Entry Point
# -------------------------

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(AMDPerfMonitorService)

