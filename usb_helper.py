#    !!!THIS IS FOR TESTING PURPOSES!!!
# usb_helper.py
# Raw Input HID listener using ctypes
# Writes live device input to JSON

import ctypes
import ctypes.wintypes as wintypes
import json
import threading
import time
from pathlib import Path

# =========================
# Configuration
# =========================

OUTPUT_FILE = Path(r"C:\ProgramData\AMDPerformanceMonitor\usb_input.json")
UPDATE_INTERVAL = 0.05  # 20Hz output refresh

# =========================
# Windows Constants
# =========================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_INPUT = 0x00FF
RIM_TYPEHID = 2

RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00002000
RIDI_DEVICENAME = 0x20000007
RIDI_DEVICEINFO = 0x2000000b

WM_INPUT_DEVICE_CHANGE = 0X00FE

# HID usage pages
USAGE_PAGE_GENERIC = 0x01
USAGE_JOYSTICK = 0x04
USAGE_GAMEPAD = 0x05
USAGE_MULTI_AXIS = 0x08

# Load hid.dll and setupapi.dll
hid = ctypes.WinDLL("hid.dll")
setupapi = ctypes.WinDLL("setupapi.dll")

# Device opening
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3

GIDC_ARRIVAL = 1
GIDC_REMOVAL = 2

# HIDP Report Types
HidP_Input = 0
HidP_Output = 1
HidP_Feature = 2

HIDP_STATUS_SUCCESS = 0x00110000

WNDPROCTYPE = ctypes.WINFUNCTYPE(
    wintypes.LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
)

class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROCTYPE),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]

# =========================
# Raw Input Structures
# =========================

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]
    
class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [
        ("hDevice", wintypes.HANDLE),
        ("dwType", wintypes.DWORD),
    ]
    
class RID_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("_union", ctypes.c_byte * 64)  # enough space for union
    ]

class RAWHID(ctypes.Structure):
    _fields_ = [
        ("dwSizeHid", wintypes.DWORD),
        ("dwCount", wintypes.DWORD),
        ("bRawData", ctypes.c_ubyte * 1)  # variable length
    ]

# =========================
# user32.dll Functions
# =========================

# Get raw input data
user32.GetRawInputData.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT
]
user32.GetRawInputData.restype = wintypes.UINT

# Register raw input devices
user32.RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE),
    wintypes.UINT,
    wintypes.UINT
]
user32.RegisterRawInputDevices.restype = wintypes.BOOL

# Get device info (THIS IS REQUIRED for descriptors later)
user32.GetRawInputDeviceInfoW.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    wintypes.LPVOID,
    ctypes.POINTER(wintypes.UINT)
]
user32.GetRawInputDeviceInfoW.restype = wintypes.UINT

# Window class registration
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.RegisterClassW.restype = wintypes.ATOM

# Window creation
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

# Message loop
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT
]
user32.GetMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.DefWindowProcW.restype = wintypes.LRESULT

# =========================
# kernel32.dll Functions
# =========================

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE
]
kernel32.CreateFileW.restype = wintypes.HANDLE

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

# Get list of raw input devices
user32.GetRawInputDeviceList.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICELIST),
    ctypes.POINTER(wintypes.UINT)
]
user32.GetRawInputDeviceList.restype = wintypes.UINT

# =========================
# HID Structures (for hid.dll)
# =========================

class HIDP_PREPARSED_DATA(ctypes.Structure):
    pass  # opaque structure (we don't define fields)

PHIDP_PREPARSED_DATA = ctypes.POINTER(HIDP_PREPARSED_DATA)

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]
    
class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", wintypes.USHORT),
        ("ReportID", wintypes.BYTE),
        ("IsAlias", wintypes.BYTE),
        ("BitField", wintypes.USHORT),
        ("LinkCollection", wintypes.USHORT),
        ("LinkUsage", wintypes.USHORT),
        ("LinkUsagePage", wintypes.USHORT),
        ("IsRange", wintypes.BYTE),
        ("IsStringRange", wintypes.BYTE),
        ("IsDesignatorRange", wintypes.BYTE),
        ("IsAbsolute", wintypes.BYTE),
        ("HasNull", wintypes.BYTE),
        ("Reserved", wintypes.BYTE),
        ("BitSize", wintypes.USHORT),
        ("ReportCount", wintypes.USHORT),
        ("Reserved2", wintypes.USHORT * 5),
        ("UnitsExp", wintypes.ULONG),
        ("Units", wintypes.ULONG),
        ("LogicalMin", wintypes.LONG),
        ("LogicalMax", wintypes.LONG),
        ("PhysicalMin", wintypes.LONG),
        ("PhysicalMax", wintypes.LONG),
    ]

class HIDP_BUTTON_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", wintypes.USHORT),
        ("ReportID", wintypes.BYTE),
        ("IsAlias", wintypes.BYTE),
        ("BitField", wintypes.USHORT),
        ("LinkCollection", wintypes.USHORT),
        ("LinkUsage", wintypes.USHORT),
        ("LinkUsagePage", wintypes.USHORT),
        ("IsRange", wintypes.BYTE),
        ("IsStringRange", wintypes.BYTE),
        ("IsDesignatorRange", wintypes.BYTE),
        ("IsAbsolute", wintypes.BYTE),
        ("Reserved", wintypes.BYTE * 10),
        ("UsageMin", wintypes.USHORT),
        ("UsageMax", wintypes.USHORT),
        ("StringMin", wintypes.USHORT),
        ("StringMax", wintypes.USHORT),
        ("DesignatorMin", wintypes.USHORT),
        ("DesignatorMax", wintypes.USHORT),
        ("DataIndexMin", wintypes.USHORT),
        ("DataIndexMax", wintypes.USHORT),
    ]

# Input parsing
class HIDParser:
    def __init__(self, descriptor):
        self.preparsed = descriptor["preparsed"]
        self.caps = descriptor["caps"]
        self.button_caps = descriptor["button_caps"]
        self.value_caps = descriptor["value_caps"]
        self._owns_preparsed = True

        self.input_report_length = self.caps.InputReportByteLength

    def parse(self, report_bytes):
        if not report_bytes:
            return {}

        report_buffer = ctypes.create_string_buffer(report_bytes, len(report_bytes))
        report_ptr = ctypes.cast(report_buffer, ctypes.c_void_p)

        result = {
            "buttons": {},
            "values": {}
        }

        # Parse buttons
        for caps in self.button_caps:
            self._parse_buttons(caps, report_ptr, len(report_bytes), result)

        # Parse values
        for caps in self.value_caps:
            self._parse_values(caps, report_ptr, len(report_bytes), result)

        return result

    def _parse_buttons(self, caps, report_ptr, report_length, result):
        usage_count = wintypes.ULONG(16)
        usage_array = (wintypes.USHORT * 16)()

        status = hid.HidP_GetUsages(
            HidP_Input,
            caps.UsagePage,
            caps.LinkCollection,
            usage_array,
            ctypes.byref(usage_count),
            self.preparsed,
            report_ptr,
            report_length
        )

        if status != HIDP_STATUS_SUCCESS:
            return

        for i in range(usage_count.value):
            usage = usage_array[i]
            key = f"Page{caps.UsagePage}_Usage{usage}"
            result["buttons"][key] = True
    
    def _parse_values(self, caps, report_ptr, report_length, result):
        if caps.IsRange:
            usage_min = caps.UsageMin
            usage_max = caps.UsageMax
            usages = range(usage_min, usage_max + 1)
        else:
            usages = [caps.UsageMin]

        for usage in usages:
            value = wintypes.ULONG()

            status = hid.HidP_GetUsageValue(
                HidP_Input,
                caps.UsagePage,
                caps.LinkCollection,
                usage,
                ctypes.byref(value),
                self.preparsed,
                report_ptr,
                report_length
            )

            if status != HIDP_STATUS_SUCCESS:
                continue

            key = f"Page{caps.UsagePage}_Usage{usage}"
            result["values"][key] = value.value
            
    def close(self):
        if self.preparsed:
            hid.HidD_FreePreparsedData(self.preparsed)
            self.preparsed = None

# =========================
# hid.dll Function Prototypes
# =========================

# Preparsed data is an opaque pointer
hid.HidD_GetPreparsedData.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_void_p)
]
hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN

hid.HidD_FreePreparsedData.argtypes = [
    ctypes.c_void_p
]
hid.HidD_FreePreparsedData.restype = wintypes.BOOLEAN

hid.HidP_GetCaps.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(HIDP_CAPS)
]
hid.HidP_GetCaps.restype = wintypes.ULONG

hid.HidP_GetButtonCaps.argtypes = [
    wintypes.USHORT,               # ReportType
    ctypes.POINTER(HIDP_BUTTON_CAPS),
    ctypes.POINTER(wintypes.USHORT),
    ctypes.c_void_p
]
hid.HidP_GetButtonCaps.restype = wintypes.ULONG


hid.HidP_GetValueCaps.argtypes = [
    wintypes.USHORT,
    ctypes.POINTER(HIDP_VALUE_CAPS),
    ctypes.POINTER(wintypes.USHORT),
    ctypes.c_void_p
]
hid.HidP_GetValueCaps.restype = wintypes.ULONG


hid.HidP_GetUsages.argtypes = [
    wintypes.USHORT,               # ReportType
    wintypes.USHORT,               # UsagePage
    wintypes.USHORT,               # LinkCollection
    ctypes.POINTER(wintypes.USHORT),
    ctypes.POINTER(wintypes.ULONG),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.ULONG
]
hid.HidP_GetUsages.restype = wintypes.ULONG


hid.HidP_GetUsageValue.argtypes = [
    wintypes.USHORT,
    wintypes.USHORT,
    wintypes.USHORT,
    wintypes.USHORT,
    ctypes.POINTER(wintypes.ULONG),
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.ULONG
]
hid.HidP_GetUsageValue.restype = wintypes.ULONG

# =========================
# Enumerate Functions
# =========================

def enumerate_hid_devices():
    device_count = wintypes.UINT(0)

    # First call gets count
    user32.GetRawInputDeviceList(None, ctypes.byref(device_count))

    if device_count.value == 0:
        return []

    device_array = (RAWINPUTDEVICELIST * device_count.value)()

    user32.GetRawInputDeviceList(
        device_array,
        ctypes.byref(device_count)
    )

    devices = []

    for device in device_array:
        if device.dwType != RIM_TYPEHID:
            continue

        # Get required buffer size for device name
        size = wintypes.UINT(0)

        user32.GetRawInputDeviceInfoW(
            device.hDevice,
            RIDI_DEVICENAME,
            None,
            ctypes.byref(size)
        )

        if size.value == 0:
            continue

        buffer = ctypes.create_unicode_buffer(size.value)

        user32.GetRawInputDeviceInfoW(
            device.hDevice,
            RIDI_DEVICENAME,
            buffer,
            ctypes.byref(size)
        )

        device_path = buffer.value

        # Open device using CreateFileW
        handle = kernel32.CreateFileW(
            device_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-2).value

        if handle != INVALID_HANDLE_VALUE:
            devices.append((device_path, handle))

    return devices

# =========================
# Global State
# =========================

device_data = {}
lock = threading.Lock()

device_handle_cache = {}

# =========================
# Descriptor Retrieval
# =========================

def get_hid_descriptor(device_handle):
    preparsed = ctypes.c_void_p()

    if not hid.HidD_GetPreparsedData(device_handle, ctypes.byref(preparsed)):
        return None

    caps = HIDP_CAPS()

    status = hid.HidP_GetCaps(preparsed, ctypes.byref(caps))
    if status != HIDP_STATUS_SUCCESS:
        hid.HidD_FreePreparsedData(preparsed)
        return None

    # ---- Get Button Caps ----
    button_count = wintypes.USHORT(caps.NumberInputButtonCaps)
    button_caps = None

    if button_count.value > 0:
        button_array = (HIDP_BUTTON_CAPS * button_count.value)()
        status = hid.HidP_GetButtonCaps(
            HidP_Input,
            button_array,
            ctypes.byref(button_count),
            preparsed
        )

        if status == HIDP_STATUS_SUCCESS:
            button_caps = list(button_array[:button_count.value])
        else:
            button_caps = []

    else:
        button_caps = []

    # ---- Get Value Caps ----
    value_count = wintypes.USHORT(caps.NumberInputValueCaps)
    value_caps = None

    if value_count.value > 0:
        value_array = (HIDP_VALUE_CAPS * value_count.value)()
        status = hid.HidP_GetValueCaps(
            HidP_Input,
            value_array,
            ctypes.byref(value_count),
            preparsed
        )

        if status == HIDP_STATUS_SUCCESS:
            value_caps = list(value_array[:value_count.value])
        else:
            value_caps = []
    else:
        value_caps = []

    return {
        "preparsed": preparsed,
        "caps": caps,
        "button_caps": button_caps,
        "value_caps": value_caps,
    }

# =========================
# Raw Input Processing
# =========================

def get_device_path_from_handle(raw_handle):
    size = wintypes.UINT(0)

    # First call to get required buffer size
    user32.GetRawInputDeviceInfoW(
        raw_handle,
        RIDI_DEVICENAME,
        None,
        ctypes.byref(size)
    )

    if size.value == 0:
        return None

    buffer = ctypes.create_unicode_buffer(size.value)

    result = user32.GetRawInputDeviceInfoW(
        raw_handle,
        RIDI_DEVICENAME,
        buffer,
        ctypes.byref(size)
    )

    if result == 0xFFFFFFFF:
        return None

    return buffer.value

def caps_to_dict(caps):
    return {
        "Usage": caps.Usage,
        "UsagePage": caps.UsagePage,
        "InputReportByteLength": caps.InputReportByteLength,
        "NumberInputButtonCaps": caps.NumberInputButtonCaps,
        "NumberInputValueCaps": caps.NumberInputValueCaps,
    }

def process_raw_input(lparam):
    size = wintypes.UINT(0)

    result = user32.GetRawInputData(
        lparam,
        RID_INPUT,
        None,
        ctypes.byref(size),
        ctypes.sizeof(RAWINPUTHEADER)
    )
    
    if result == 0xFFFFFFFF or size.value == 0:
        return

    buffer = ctypes.create_string_buffer(size.value)

    result = user32.GetRawInputData(
        lparam,
        RID_INPUT,
        buffer,
        ctypes.byref(size),
        ctypes.sizeof(RAWINPUTHEADER)
    )
    
    if result == 0xFFFFFFFF or result != size.value:
        return

    header = RAWINPUTHEADER.from_buffer_copy(buffer)

    if header.dwType != RIM_TYPEHID:
        return

    device_key = str(header.hDevice)

    # ---- Get Device Path ----
    if device_key not in device_handle_cache:
        path = get_device_path_from_handle(header.hDevice)
        if not path:
            return

        handle = open_device(path)
        if not handle:
            return

        descriptor = get_hid_descriptor(handle)
        if not descriptor:
            return

        parser = HIDParser(descriptor)

        device_handle_cache[device_key] = {
            "path": path,
            "handle": handle,
            "parser": parser,
            "caps": descriptor["caps"]
        }

    # ---- Store Raw Report ----
    
    hid_offset = ctypes.sizeof(RAWINPUTHEADER)

    hid_struct = RAWHID.from_buffer_copy(buffer, hid_offset)

    report_size = hid_struct.dwSizeHid * hid_struct.dwCount

    report_offset = ctypes.sizeof(RAWINPUTHEADER) + ctypes.sizeof(RAWHID)

    report = buffer[report_offset:report_offset + report_size]
    
    if not report:
        return

    with lock:
        cache = device_handle_cache[device_key]
        parsed = cache["parser"].parse(report)
        
        device_data[device_key] = {
            "descriptor": {
                "path": cache["path"],
                "caps":caps_to_dict(cache["caps"])
        },
        "parsed_input": parsed
}

def open_device(device_path):
    handle = kernel32.CreateFileW(
        device_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )

    if handle == wintypes.HANDLE(-1).value:
        return None

    return handle

# =========================
# Window Procedure
# =========================

def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        process_raw_input(lparam)

    elif msg == WM_INPUT_DEVICE_CHANGE:

        if wparam == GIDC_REMOVAL:
            with lock:
                for key, value in device_handle_cache.items():
                    value["parser"].close()
                    kernel32.CloseHandle(value["handle"])
                
                device_handle_cache.clear()
                device_data.clear()
        if wparam == GIDC_ARRIVAL:
            pass

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

global_wnd_proc = WNDPROCTYPE(wnd_proc)
_global_wndclass = None

# =========================
# Window Setup
# =========================

def create_window():
    class_name = "USBHelperWindow"

    wndclass = WNDCLASS()
    wndclass.style = 0
    wndclass.cbClsExtra = 0
    wndclass.cbWndExtra = 0
    wndclass.hIcon = None
    wndclass.hCursor = None
    wndclass.hbrBackground = None
    wndclass.lpszMenuName = None
    wndclass.lpfnWndProc = global_wnd_proc
    wndclass.lpszClassName = class_name
    wndclass.hInstance = kernel32.GetModuleHandleW(None)
    
    global _global_wndclass
    _global_wndclass = wndclass
    
    if not user32.RegisterClassW(ctypes.byref(wndclass)):
        raise ctypes.WinError()

    hwnd = user32.CreateWindowExW(
        0,
        class_name,
        "USB Helper",
        0,
        0, 0, 0, 0,
        None,
        None,
        wndclass.hInstance,
        None
    )
    
    if not hwnd:
        raise ctypes.WinError()

    rid = RAWINPUTDEVICE()
    rid.usUsagePage = 0x01   # Generic Desktop Controls
    rid.usUsage = 0x00       # All usages
    rid.dwFlags = RIDEV_INPUTSINK | RIDEV_DEVNOTIFY
    rid.hwndTarget = hwnd

    if not user32.RegisterRawInputDevices(
        ctypes.byref(rid),
        1,
        ctypes.sizeof(RAWINPUTDEVICE)
    ):
        raise ctypes.WinError()
    
    return hwnd

# =========================
# Output Thread
# =========================

def output_loop():
    while True:
        with lock:
            tmp = OUTPUT_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(device_data))
            tmp.replace(OUTPUT_FILE)

        time.sleep(UPDATE_INTERVAL)

# =========================
# Main
# =========================

def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    hwnd = create_window()

    threading.Thread(target=output_loop, daemon=True).start()

    msg = wintypes.MSG()

    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

if __name__ == "__main__":
    main()
