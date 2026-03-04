#    !!!THIS IS A TEST, DO NOT ATTEMPT TO INSTAL/USE!!!

import json
import time
from pathlib import Path
import pywinusb.hid as hid
from threading import Lock

OUTPUT_FILE = Path(r"C:\ProgramData\AMDPerformanceMonitor\usb_input.json")

lock = Lock()
device_reports = {}
device_list = []


def raw_handler(data, device_key):
    global device_reports

    with lock:
        device_reports[device_key] = list(data)


def main():
    global device_list

    all_devices = hid.HidDeviceFilter().get_devices()

    active_devices = []

    for device in all_devices:
        try:
            if not device.product_name:
                continue

            device_key = f"{device.vendor_id:04X}:{device.product_id:04X}"

            device_info = {
                "vendor_id": device.vendor_id,
                "product_id": device.product_id,
                "product_name": device.product_name,
                "serial_number": device.serial_number
            }

            device_list.append(device_info)

            device.open()

            device.set_raw_data_handler(
                lambda data, key=device_key: raw_handler(data, key)
            )

            active_devices.append(device)

        except Exception:
            continue

    # Continuous dump loop
    while True:
        try:
            with lock:
                output = {
                    "devices": device_list,
                    "raw_reports": device_reports
                }

            OUTPUT_FILE.write_text(json.dumps(output, indent=2))

            time.sleep(0.1)

        except KeyboardInterrupt:
            break
        except Exception:
            pass


if __name__ == "__main__":
    main()
