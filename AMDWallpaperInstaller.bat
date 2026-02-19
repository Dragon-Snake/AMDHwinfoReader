@echo off
title AMD HWiNFO Reader Installer (GitHub)

echo ===========================================
echo AMD HWiNFO Reader Installer (GitHub)
echo ===========================================
echo.

REM Step 1: Default install folder
set INSTALL_DIR=%ProgramFiles%\AMD Performance Monitor
echo Installing to: %INSTALL_DIR%

REM Step 2: Create folder if it doesn't exist
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Could not create folder. Try running as Administrator.
        pause
        exit /b
    )
)

REM Step 3: Download amdHwinfoReader.js from GitHub
echo Downloading latest amdHwinfoReader.js from GitHub...
powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/Dragon-Snake/AMDHwinfoReader/main/amdHwinfoReader.js' -OutFile '%INSTALL_DIR%\amdHwinfoReader.js'"

if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to download amdHwinfoReader.js
    pause
    exit /b
)

REM Step 4: Check if HWiNFO64.exe is running
echo Checking for HWiNFO64...
tasklist /FI "IMAGENAME eq HWiNFO64.exe" | find /I "HWiNFO64.exe" >nul
if %ERRORLEVEL% neq 0 (
    echo WARNING: HWiNFO64 is not running. Please start HWiNFO with Shared Memory enabled.
    set /p cont="Press ENTER to continue anyway or Ctrl+C to exit..."
)

REM Step 5: Test script polling (simulated check)
echo.
echo Testing AMD HWiNFO Reader...
set TEST_HTML=%TEMP%\AMDTest.html

(
echo ^<!DOCTYPE html^>
echo ^<html^>
echo ^<head^>
echo ^<title^>AMD Test^</title^>
echo ^<script src="%INSTALL_DIR%\amdHwinfoReader.js"^>^</script^>
echo ^</head^>
echo ^<body^>
echo ^<script^>
echo setTimeout(function() {^
echo     if(window.amdStats) {^
echo         alert("AMD HWiNFO Reader loaded successfully! GPU Usage: " + window.amdStats.gpuUsage + "%%");^
echo     } else {^
echo         alert("Failed to load AMD HWiNFO Reader or HWiNFO not running.");^
echo     }^
echo }, 2000);^
echo ^</script^>
echo ^</body^>
echo ^</html^>
) > "%TEST_HTML%"

start "" "%TEST_HTML%"

echo.
echo Please check the alert box. If it shows GPU usage, the install is successful.
pause

echo.
echo ===========================================
echo INSTALLATION COMPLETE
echo AMD HWiNFO Reader installed to: %INSTALL_DIR%
echo ===========================================
pause

exit /b

