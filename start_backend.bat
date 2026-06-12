@echo off
REM Woodful Creations - Backend Start Script for Windows

echo Starting Woodful Creations Backend...
echo.

REM Check if virtual environment exists
if not exist "backend\venv" (
    echo ERROR: Virtual environment not found
    echo Please run setup.bat first
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist "backend\.env" (
    echo WARNING: backend\.env not found
    echo Using .env.example as template
    copy backend\.env.example backend\.env
)

REM Activate virtual environment and start server
echo Starting FastAPI server...
echo API will be available at: http://localhost:8000
echo API Documentation: http://localhost:8000/api/docs
echo.
echo Press Ctrl+C to stop the server
echo.

call backend\venv\Scripts\activate.bat
cd backend
python main.py
pause
