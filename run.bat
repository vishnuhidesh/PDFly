@echo off
setlocal enabledelayedexpansion
title PDFly - Online PDF Suite

:: Change to script directory
cd /d "%~dp0"

echo ========================================================
echo                 Starting PDFly Suite
echo ========================================================
echo.

:: Detect Python executable
set "PYTHON_CMD="
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_CMD=python"
) else (
    py -3 --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py -3"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python is not installed or not found in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check the option "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Check for virtual environment and activate if available
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment (venv)...
    call "venv\Scripts\activate.bat"
    set "PYTHON_CMD=python"
) else if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment (.venv)...
    call ".venv\Scripts\activate.bat"
    set "PYTHON_CMD=python"
)

:: Verify dependencies
echo [INFO] Checking dependencies...
!PYTHON_CMD! -c "import django, pymupdf, pypdf, reportlab, PIL, whitenoise" >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] Installing missing dependencies from requirements.txt...
    !PYTHON_CMD! -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install required dependencies.
        pause
        exit /b 1
    )
)

:: Run database migrations
echo [INFO] Applying database migrations...
!PYTHON_CMD! manage.py migrate --noinput
if !errorlevel! neq 0 (
    echo [WARNING] Migration encountered a warning or error, continuing server startup...
)

:: Auto-launch browser after brief delay (2 seconds)
echo [INFO] Launching default web browser...
start "" /b cmd /c "ping -n 3 127.0.0.1 >nul & start http://127.0.0.1:8000"

echo.
echo ========================================================
echo   PDFly is running successfully!
echo.
echo   * URL:         http://127.0.0.1:8000
echo   * Stop Server: Press Ctrl+C in this window
echo ========================================================
echo.

:: Start Django development server
!PYTHON_CMD! manage.py runserver 127.0.0.1:8000

echo.
echo Server has stopped.
pause
