@echo off
title Bilibili Favorites Tool - First Install

echo ===================================
echo   Bilibili Favorites Tool - Install
echo ===================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Please follow these steps to install Python:
    echo 1. Open https://www.python.org/downloads/
    echo 2. Download the latest version
    echo 3. Check "Add Python to PATH" during install
    echo 4. Run this script again after install
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b
)

echo [OK] Python detected:
python --version
echo.

echo [INFO] Installing dependencies, this may take a while...
pip install flask requests openpyxl Pillow
echo.

echo ===================================
echo [OK] Install complete!
echo.
echo Next time, just double-click start.bat to run
echo ===================================
echo.

python app.py

pause
