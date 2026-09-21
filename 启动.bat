@echo off
title Bilibili Favorites Tool
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found! Please install Python first.
    start https://www.python.org/downloads/
    exit /b
)
pip install flask requests openpyxl Pillow -q 2>nul
python app.py
pause
