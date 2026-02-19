# AMDHwinfoReader
Reads and helps display AMD GPU stats from HWiNFO to a wallpaper in wallpaper engine

# For installation:

## Requirements:
- Requests (auto-installs from .bat file)
- pywin32 (auto-installs from .bat file)
- HWiNFO64 (Needs "Reporting to Gadget" and "Report Value in Gadget" Enabled under sensor settings in order to properly function, and for added QoL, enable "Auto Start", and all of the "minimize" settings as so it works entirely in the background)

## Installation guide:
First, isntall HWiNFO here: `https://www.hwinfo.com/download/` and download the 64 version, this will currently not work with 32 and portable version.
Go to HWiNFOPerfMonInstaller.bat, click "Download raw file', then right click -> run as administrator, Requests and pywin32 should autoinstall.

## Usage:
Should auto-start after install. Needs no further action after install. Any wallpaper using this should be "plug-and-play", already having preset keys for usage.
For any errors or compatibility issues, always contact wallpaper maker first, since, odds are, their wallpaper is out of date, or has some typo.

# For wallpaper developers:

## Where to find GPU information:
Gpu information should be stored at:"C:\ProgramData\AMDPerformanceMonitor\performance.json", be sure to enable "Report Value in gadget" in HWiNFO for the values your wallpaper will use, as not doing so will make them either not update, or not show in the json file.

## Where to find GPU name:
This is currently under development, but will soon be added inside the json file as well.
Matter of fact, any and all information will be under the json file. If other performance metrics are added, they may be under a different category (ie, CPU, GPU, etc)

## How values are stored:
All values are stored in the json as the raw value, so for "GPU Utilization", for 45%, it will show as 45.0 in jeson, an exact copy of the HWiNFO values.
The only thing this does not store is the units, so 1,500 MB will be stored as only 1500.0. Cross referencing with HWiNFO is recommended when making a wallpaper using these values.

# Compatibility:

## WHat GPU's does this support:
So far, given how it just takes the "does it have/start with GPU?" stats, it should, in theory, support all GPU's from AMD to NVIDIA, and any other, as long as HWiNFO displays it properly, and you have all the requirements and proper settings enabled.

# Q&A:

## Do I need shared memory enabled?
No, this reads directly from the HKEY_LOCAL_MACHINE registry, meaning you only need "Reporting to Gadget" and then "Report Value in Gadget" for the values that the wallpaper uses, and you're all good.

## Is this a virus?
No. As you can see the code directly, all it does is record your GPU stats for wallpapers to use. It cannot do anything else.

## How do I uninstall?
Open command prompt, run `sc stop AMDPerfMonitor`, then `sc delete AMDPerfMonitor`, afterwards you can also run `rmdir /s /q "C:\ProgramData\AMDPerformanceMonitor"` to delete the files.

## Does this support X and Y GPU?
In theory, yes. As long as HWiNFO displays X and Y GPU as GPU #0, it should work perfectly.

## Can I install this on Windows 10?
I am on windows 11, but you are free to test if it works or not. It should though.
