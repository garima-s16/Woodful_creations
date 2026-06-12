@echo off
REM Woodful Creations - Start Script for Windows

echo.
echo ==========================================
echo Starting Woodful Creations
echo ==========================================
echo.

echo Starting Backend API on port 8000...
cd backend
start python main.py
cd ..

REM Wait for backend to start
timeout /t 3 /nobreak

echo.
echo Starting Frontend on port 3000...
cd frontend
npm start

echo.
echo ==========================================
