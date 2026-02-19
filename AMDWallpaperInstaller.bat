@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM -------------------------------
REM Configuration
REM -------------------------------
SET SCRIPT_URL=https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/refs/heads/main/amd_hwinfo_monitor.py
SET SCRIPT_PATH=%ProgramData%\AMDPerformanceMonitor\amd_hwinfo_monitor.py

REM -------------------------------
REM Detect Python
REM -------------------------------
SET PYTHON_EXE=

for /f "tokens=*" %%i in ('where python 2^>nul') do (
    SET PYTHON_EXE=%%i
    goto :found_python
)

echo Python not found in PATH. Please install Python 3.10+ and add it to PATH.
pause
exit /b

:found_python
echo Using Python at: %PYTHON_EXE%

REM -------------------------------
REM Create directories
REM -------------------------------
if not exist "%ProgramData%\AMDPerformanceMonitor" (
    mkdir "%ProgramData%\AMDPerformanceMonitor"
)

REM -------------------------------
REM Install required Python packages
REM -------------------------------
echo Installing required Python packages...

"%PYTHON_EXE%" -m pip install --upgrade pip
"%PYTHON_EXE%" -m pip install requests pywin32

IF ERRORLEVEL 1 (
    echo Failed to install required packages. Please install requests and pywin32 manually.
    pause
    exit /b
)

REM -------------------------------
REM Download Python script
REM -------------------------------
echo Downloading AMD HWInfo monitor...
powershell -Command "Invoke-WebRequest -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT_PATH%'"

REM -------------------------------
REM Install the service
REM -------------------------------
echo Installing service...
"%PYTHON_EXE%" "%SCRIPT_PATH%" install

REM -------------------------------
REM Start the service
REM -------------------------------
echo Starting service...
"%PYTHON_EXE%" "%SCRIPT_PATH%" start

echo Done!
pause
ENDLOCAL
