@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM ==================================================
REM =================== CONFIGURE ====================
REM ==================================================
SET SERVICE_NAME=AMDPerfMonitor
SET SCRIPT_URL=https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/refs/heads/main/amd_hwinfo_monitor.py
SET INSTALL_DIR=%ProgramData%\AMDPerformanceMonitor
SET SCRIPT_PATH=%INSTALL_DIR%\amd_hwinfo_monitor.py
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
SET LOGFILE=%INSTALL_DIR%\install.log

echo.
echo =================================
echo AMD Performance Monitor Installer
echo =================================
echo.

REM ==================================================
REM ================= DETECT PYTHON ==================
REM ==================================================
SET PYTHON_EXE=
SET PYTHON_ARGS=

REM Try python launcher first (preferred on Windows)
for /f "tokens=*" %%i in ('where py 2^>nul') do (
    SET PYTHON_EXE=py
    SET PYTHON_ARGS=-3
    goto :check_python
)

REM Fallback to python in PATH
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    SET PYTHON_EXE=%%i
    SET PYTHON_ARGS=
    goto :check_python
)

echo Python 3.10+ not found. Please install Python and add it to PATH.
pause
exit /b

:check_python
echo Found Python. Verifying version...

REM Get full version string (e.g., 3.11.7)
for /f "tokens=2" %%v in ('"%PYTHON_EXE%" %PYTHON_ARGS% -c "import sys; print(sys.version.split()[0])"') do (
    set PY_VER=%%v
)

if not defined PY_VER (
    echo Failed to detect Python version.
    pause
    exit /b
)

REM Split into major + minor
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

REM Enforce Python 3.10+
if !PY_MAJOR! LSS 3 (
    echo Python 3.10+ is required.
    pause
    exit /b
)

if !PY_MAJOR! EQU 3 if !PY_MINOR! LSS 10 (
    echo Python 3.10+ is required.
    pause
    exit /b
)

echo Using Python:
"%PYTHON_EXE%" %PYTHON_ARGS% --version
echo.

REM ==================================================
REM ================= CHECK SERVICE ==================
REM ==================================================
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
"%PYTHON_EXE%" %PYTHON_ARGS% -m ensurepip --upgrade >nul 2>&1
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade pip requests pywin32
"%PYTHON_EXE%" %PYTHON_ARGS% -m pywin32_postinstall -install

IF ERRORLEVEL 1 (
    echo Failed to install required packages.
    pause
    exit /b
)

REM Download script
echo Downloading monitor script...
powershell -Command "try { Invoke-WebRequest -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT_PATH%' -ErrorAction Stop } catch { exit 1 }"
IF ERRORLEVEL 1 (
    echo Download failed.
    pause
    exit /b
)

REM Install service
echo Installing service...
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPT_PATH%" install
IF ERRORLEVEL 1 (
    echo Service installation failed.
    pause
    exit /b
)

REM Set auto-start
timeout /t 2 >nul
sc config %SERVICE_NAME% start= auto >nul
IF ERRORLEVEL 1 (
    echo Failed to set service to auto-start.
)

REM Start service
"%PYTHON_EXE%" %PYTHON_ARGS% "%SCRIPT_PATH%" start
sc query %SERVICE_NAME% | find "RUNNING" >nul
IF ERRORLEVEL 1 (
    echo Service failed to start.
    pause
    exit /b
)

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
sc stop %SERVICE_NAME% >nul 2>&1

echo Waiting for service to stop...
set WAITCOUNT=0

:wait_stop
sc query %SERVICE_NAME% | find "STOPPED" >nul
if !errorlevel! equ 0 goto stopped

set /a WAITCOUNT+=1
if %WAITCOUNT% geq 30 (
    echo Service failed to stop within 30 seconds.
    pause
    exit /b
)

timeout /t 1 >nul
goto wait_stop

:stopped

REM Ensure required Python packages are installed
echo Verifying Python dependencies...
"%PYTHON_EXE%" %PYTHON_ARGS% -m ensurepip --upgrade >nul 2>&1
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade requests pywin32
"%PYTHON_EXE%" %PYTHON_ARGS% -m pywin32_postinstall -install >nul 2>&1
IF ERRORLEVEL 1 (
    echo Failed to verify/install Python dependencies.
    sc start %SERVICE_NAME%
    pause
    exit /b
)

REM Backup existing script
if exist "%SCRIPT_PATH%" (
    copy /y "%SCRIPT_PATH%" "%SCRIPT_PATH%.bak" >nul
)

REM Download latest script
echo Downloading latest version...
powershell -Command "try { Invoke-WebRequest -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT_PATH%' -ErrorAction Stop } catch { exit 1 }"

IF ERRORLEVEL 1 (
    echo Download failed. Restoring backup...
    copy /y "%SCRIPT_PATH%.bak" "%SCRIPT_PATH%" >nul
    sc start %SERVICE_NAME%
    pause
    exit /b
)

if not exist "%SCRIPT_PATH%" (
    echo Download failed.
    exit /b
)

REM Start service
echo Starting service...
sc start %SERVICE_NAME%
sc query %SERVICE_NAME% | find "RUNNING" >nul
IF ERRORLEVEL 1 (
    echo Service failed to start.
    pause
    exit /b
)

echo.
echo Update complete!
pause
ENDLOCAL

