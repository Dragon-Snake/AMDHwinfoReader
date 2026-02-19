#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AMD Performance Monitor Service (HWiNFO only)
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

CURRENT_VERSION = "0.0.0.1"
SCRIPT_URL = "https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/main/amd_hwinfo_monitor.py"
SERVICE_NAME = "AMDPerfMonitor"
UPDATE_CHECK_INTERVAL = 60*60*2  # check every 2 hours

def parse_version(version_str):
    return tuple(int(x) for x in version_str.split("."))


def is_newer_version(remote, local):
    return parse_version(remote) > parse_version(local)

def extract_version_from_script(script_text):
    match = re.search(r'CURRENT_VERSION\s*=\s*"([^"]+)"', script_text)
    return match.group(1) if match else None

def extract_version_from_script(script_text):
    """
    Extracts CURRENT_VERSION = "x.x.x.x" from script text
    """
    match = re.search(r'CURRENT_VERSION\s*=\s*"([^"]+)"', script_text)
    if match:
        return match.group(1)
    return None

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

        logger.info(f"Remote: {remote_version} | Local: {CURRENT_VERSION}")

        if not is_newer_version(remote_version, CURRENT_VERSION):
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
    """Read HWiNFO sensors from registry"""
    sensors = {}
    try:
        base_path = r"SOFTWARE\HWiNFO64\VSB"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as key:
            i = 0
            while True:
                try:
                    label = winreg.QueryValueEx(key, f"Label{i}")[0]
                    value_raw = winreg.QueryValueEx(key, f"Value{i}")[0]
                    if label:
                        sensors[label] = value_raw
                    i += 1
                except FileNotFoundError:
                    break
    except Exception as e:
        logger.warning(f"Failed to read HWiNFO registry: {e}")
    return sensors


def collect_amd_stats(config):
    """Return a dict of AMD GPU stats only"""
    data = {"timestamp": time.time()}
    if config["collect"].get("hwinfo", True):
        data["gpu"] = read_hwinfo_sensors()
    else:
        data["gpu"] = {}
    return data


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

    def SvcDoRun(self):
        logger.info("AMD Performance Monitor Service starting...")
        self.running = True

        # Start monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=False)
        self.monitor_thread.start()

        # Start update check thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=False)
        self.update_thread.start()

        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

    def monitor_loop(self):
        while self.running:
            try:
                stats = collect_amd_stats(self.config)
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)
                logger.info(f"GPU Stats Updated: {len(stats['gpu'])} sensors")
            except Exception as e:
                logger.exception(f"Error collecting AMD stats: {e}")
            time.sleep(self.config.get("poll_interval", 1))

    def update_loop(self):
        last_check = 0
        while self.running:
            now = time.time()
            if now - last_check > UPDATE_CHECK_INTERVAL:
                check_for_updates()
                last_check = now
            time.sleep(60)


# -------------------------
# Entry Point
# -------------------------

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(AMDPerfMonitorService)






