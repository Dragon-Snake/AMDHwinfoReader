#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AMD Performance Monitor Service (HWiNFO only, local)
Reads AMD GPU stats from HWiNFO and saves to performance.json locally.
"""

import os
import sys
import json
import time
import threading
import logging
from pathlib import Path

# Windows service libraries
import win32service
import win32serviceutil
import win32event
import winreg
import servicemanager

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
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
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

def read_hwinfo_sensors(adapter_index=0):
    """Read HWiNFO sensors for AMD GPU from registry"""
    sensors = {}
    try:
        base_path = r"SOFTWARE\HWiNFO64\VSB"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as key:
            i = 0
            while True:
                try:
                    label = winreg.QueryValueEx(key, f"Label{i}")[0]
                    value_raw = winreg.QueryValueEx(key, f"ValueRaw{i}")[0]
                    if label and "GPU" in label:
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
        data["gpu"] = read_hwinfo_sensors(config.get("gpu_adapter", 0))
    else:
        data["gpu"] = {}
    return data

# -------------------------
# Windows Service
# -------------------------

class AMDPerfMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "AMDPerfMonitor"
    _svc_display_name_ = "AMD Performance Monitor Service"
    _svc_description_ = "Monitors AMD GPU stats from HWiNFO (local, no web service)"

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
        win32event.SetEvent(self.hWaitStop)
        self.running = False

    def SvcDoRun(self):
        logger.info("AMD Performance Monitor starting...")
        self.running = True
        self.main()

    # -------------------------
    # Monitoring Loop
    # -------------------------

    def update_loop(self):
        while self.running:
            try:
                stats = collect_amd_stats(self.config)
                with open(self.data_file, "w", encoding="utf-8") as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)
                logger.debug(f"Stats updated: {stats}")
            except Exception as e:
                logger.error(f"Error updating stats: {e}")
            time.sleep(self.config.get("poll_interval", 1))

    # -------------------------
    # Main
    # -------------------------

    def main(self):
        self.monitor_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Monitoring loop started")
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

# -------------------------
# Run Service
# -------------------------

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(AMDPerfMonitorService)
