# usb_helper.py | !!!THIS IS A TEST, DO NOT ATTEMPT TO INSTAL/USE!!!

import time
import wmi
import json
from pathlib import Path

OUTPUT_FILE = Path(r"C:\ProgramData\AMDPerformanceMonitor\usb_devices.json")

def main():
    c = wmi.WMI()

    devices = []

    for device in c.Win32_PnPEntity():
        if device.PNPClass in ["HIDClass", "Keyboard", "Mouse"]:
            devices.append({
                "name": device.Name,
                "device_id": device.DeviceID
            })

    OUTPUT_FILE.write_text(json.dumps(devices, indent=2))

if __name__ == "__main__":
    main()
