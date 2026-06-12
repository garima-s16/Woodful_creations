@echo off
REM Woodful Creations - Frontend Start Script for Windows

echo Starting Woodful Creations Frontend...
echo.

REM Check if node_modules exists
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

REM Start the frontend
echo Starting React development server...
echo Frontend will be available at: http://localhost:3000
echo.
echo Press Ctrl+C to stop the server
echo.

cd frontend
call npm start
