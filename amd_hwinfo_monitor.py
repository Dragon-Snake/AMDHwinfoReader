#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AMD Performance Monitor (HWiNFO only, local)
Reads AMD GPU stats from HWiNFO and saves to performance.json locally.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
import winreg

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
# Main Loop
# -------------------------

def read_hwinfo_sensors(adapter_index=0, test=False):
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

                    if test:
                        print(f"[TEST] Label{i}: {label}, ValueRaw{i}: {value_raw}")

                    # Only collect GPU stats in normal mode
                    if not test:
                        sensors[label] = value_raw

                    i += 1
                except FileNotFoundError:
                    break
    except Exception as e:
        logger.warning(f"Failed to read HWiNFO registry: {e}")
    return sensors

def main():
    config = load_config()
    data_file = PROGRAM_DATA_DIR / "performance.json"

    logger.info("Starting AMD HWInfo monitor (local)...")
    print("Press Ctrl+C to stop.")

    # One-time test print of all HWiNFO labels
    print("=== HWiNFO Registry Labels (Test) ===")
    read_hwinfo_sensors(test=True)
    print("=== End Test ===\n")

    try:
        while True:
            stats = collect_amd_stats(config)

            # Save to JSON
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)

            # Print stats to terminal
            print(f"[{time.strftime('%H:%M:%S')}] GPU Stats: {stats['gpu']}")

            time.sleep(config.get("poll_interval", 1))
    except KeyboardInterrupt:
        logger.info("AMD HWInfo monitor stopped by user.")


if __name__ == "__main__":
    main()


