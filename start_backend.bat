@echo off
REM Woodful Creations - Start backend only
cd /d "%~dp0backend"

if not exist "venv" (
    echo No virtual environment found. Run setup.bat first.
    exit /b 1
)

call venv\Scripts\activate.bat
python main.py
