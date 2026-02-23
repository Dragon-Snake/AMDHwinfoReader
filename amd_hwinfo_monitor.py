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
import win32service
import win32serviceutil
import win32event
import servicemanager
import requests
import re
import subprocess

# -------------------------
# Update Checker
# -------------------------

CURRENT_VERSION = "0.0.1.5"
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

def check_for_updates():
    try:
        logger.info("Checking for updates...")

        r = requests.get(SCRIPT_URL, timeout=10)
        if r.status_code != 200:
            logger.warning(f"Failed to download script ({r.status_code})")
            return

        remote_script = r.text
        remote_version = extract_version_from_script(remote_script)

        if not remote_version:
            logger.warning("Could not extract remote version.")
            return

        # Read the **actual file** version, not in-memory
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger("AMDPerfMonitor")

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

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}  # merge with defaults
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}")
    return DEFAULT_CONFIG.copy()

def read_hwinfo_sensors():
    raw_sensors = _extract_hwinfo_raw()
    return _classify_hwinfo(raw_sensors)

def _extract_hwinfo_raw():
    raw = {}

    try:
        base_path = r"SOFTWARE\HWiNFO64\VSB"
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
                    break

    except Exception as e:
        logger.warning(f"Failed to read HWiNFO registry: {e}")

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

    def SvcStop(self):
        logger.info("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

        self.running = False
        win32event.SetEvent(self.hWaitStop)

        for t in [self.monitor_thread, getattr(self, "update_thread", None)]:
            if t and t.is_alive():
                t.join(timeout=5)

        logger.info("Service stopped cleanly.")

    def SvcDoRun(self):
        logger.info("AMD Performance Monitor Service starting...")
        self.running = True

        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        # Start update check thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        # Keep main thread alive, allow fast stop
        while self.running:
            result = win32event.WaitForSingleObject(self.hWaitStop, 1000)
            if result == win32event.WAIT_OBJECT_0:
                self.running = False
                break

    def monitor_loop(self):
        while self.running:
            try:
                stats = collect_amd_stats(self.config)
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.exception(f"Error collecting AMD stats: {e}")

            # Wait instead of sleep (interruptible)
            wait_time_ms = int(self.config.get("poll_interval", 1) * 1000)
            result = win32event.WaitForSingleObject(self.hWaitStop, wait_time_ms)

            if result == win32event.WAIT_OBJECT_0:
                break

    def update_loop(self):
        last_check = 0

        while self.running:
            now = time.time()
            # Only run the update if interval has passed
            if now - last_check > UPDATE_CHECK_INTERVAL:
                check_for_updates()
                last_check = now

            # Wait in small increments to allow fast stop
            wait_ms = 200  # 0.2 seconds
            total_wait_ms = 60 * 1000  # 1 minute between checks (or whatever)
            waited = 0

            while self.running and waited < total_wait_ms:
                result = win32event.WaitForSingleObject(self.hWaitStop, wait_ms)
                if result == win32event.WAIT_OBJECT_0:
                    self.running = False
                    break
                waited += wait_ms

# -------------------------
# Entry Point
# -------------------------

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(AMDPerfMonitorService)

