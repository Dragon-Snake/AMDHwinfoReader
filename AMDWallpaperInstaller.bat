@echo off
chcp 65001 >nul
title AMD HWiNFO Reader Installer & Runner

echo ===========================================
echo AMD HWiNFO Reader Installer & Runner
echo ===========================================
echo.

REM -------------------------
REM Step 1: Check Python installation
REM -------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Please install Python:
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Python found:
python --version
echo.

REM -------------------------
REM Step 2: Create install folder
REM -------------------------
set INSTALL_DIR=%ProgramFiles%\AMDPerformanceMonitor
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Could not create folder. Try running as Administrator.
        pause
        exit /b 1
    )
)
echo Installing to: %INSTALL_DIR%
echo.

REM -------------------------
REM Step 3: Download Python script from GitHub
REM -------------------------
echo Downloading amd_hwinfo_monitor.py from GitHub...
powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/refs/heads/main/amd_hwinfo_monitor.py' -OutFile '%INSTALL_DIR%\amd_hwinfo_monitor.py'"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to download Python script.
    pause
    exit /b 1
)
echo Download complete.
echo.

REM -------------------------
REM Step 4: Run Python script
REM -------------------------
echo Running AMD HWInfo Monitor...
python "%INSTALL_DIR%\amd_hwinfo_monitor.py"

echo.
echo AMD HWInfo Monitor stopped.
pause
exit /b
