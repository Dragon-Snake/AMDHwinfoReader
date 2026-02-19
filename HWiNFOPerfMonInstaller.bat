@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM -------------------------------
REM Configuration
REM -------------------------------
SET SERVICE_NAME=AMDPerfMonitor
SET SCRIPT_URL=https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/refs/heads/main/amd_hwinfo_monitor.py
SET INSTALL_DIR=%ProgramData%\AMDPerformanceMonitor
SET SCRIPT_PATH=%INSTALL_DIR%\amd_hwinfo_monitor.py

echo.
echo ================================
echo AMD Performance Monitor Installer
echo ================================
echo.

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
echo.

REM -------------------------------
REM Check if service already exists
REM -------------------------------
sc query %SERVICE_NAME% >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo Existing installation detected.
    goto :update_mode
)

REM ==================================================
REM ================= INSTALL MODE ===================
REM ==================================================

echo Running fresh install...
echo.

REM Create install directory
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

REM Install required packages
echo Installing required Python packages...
"%PYTHON_EXE%" -m pip install --upgrade pip
"%PYTHON_EXE%" -m pip install requests pywin32

IF ERRORLEVEL 1 (
    echo Failed to install required packages.
    pause
    exit /b
)

REM Download script
echo Downloading monitor script...
powershell -Command "Invoke-WebRequest -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT_PATH%'"

REM Install service
echo Installing service...
"%PYTHON_EXE%" "%SCRIPT_PATH%" install

REM Set auto-start
sc config %SERVICE_NAME% start= auto

REM Start service
"%PYTHON_EXE%" "%SCRIPT_PATH%" start

echo.
echo Installation complete!
pause
exit /b

REM ==================================================
REM ================= UPDATE MODE ====================
REM ==================================================

:update_mode
echo Updating existing installation...
echo.

REM Stop service
echo Stopping service...
sc stop %SERVICE_NAME% >nul 2>&1
timeout /t 3 >nul

REM Backup existing script
if exist "%SCRIPT_PATH%" (
    copy /y "%SCRIPT_PATH%" "%SCRIPT_PATH%.bak" >nul
)

REM Download latest script
echo Downloading latest version...
powershell -Command "Invoke-WebRequest -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT_PATH%'"

IF ERRORLEVEL 1 (
    echo Download failed. Restoring backup...
    copy /y "%SCRIPT_PATH%.bak" "%SCRIPT_PATH%" >nul
    sc start %SERVICE_NAME%
    pause
    exit /b
)

REM Start service
echo Starting service...
sc start %SERVICE_NAME%

echo.
echo Update complete!
pause
ENDLOCAL
