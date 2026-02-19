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

# -------------------------
# Update Checker
# -------------------------

CURRENT_VERSION = "0.0.0.1"
VERSION_URL = "https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/main/version.txt"
UPDATE_CHECK_INTERVAL = 60*60*2  # check every 2 hours

def check_for_updates():
    try:
        r = requests.get(VERSION_URL, timeout=5)
        if r.status_code == 200:
            latest_version = r.text.strip()
            if latest_version != CURRENT_VERSION:
                logger.info(f"New version available: {latest_version} (current: {CURRENT_VERSION})")
            else:
                logger.info("You are running the latest version.")
        else:
            logger.warning(f"Failed to check updates (status code {r.status_code})")
    except Exception as e:
        logger.warning(f"Error checking updates: {e}")

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
                    value_raw = winreg.QueryValueEx(key, f"ValueRaw{i}")[0]
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




