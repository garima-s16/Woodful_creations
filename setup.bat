@echo off
REM Woodful Creations - Development Setup Script for Windows

setlocal enabledelayedexpansion

echo ======================================
echo Woodful Creations - Setup Script
echo ======================================
echo.

REM Check if Python is installed
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%
echo.

REM Check if PostgreSQL is installed
echo Checking PostgreSQL installation...
psql --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: PostgreSQL is not installed
    echo Please install PostgreSQL from https://www.postgresql.org/download/
    echo Or continue with SQLite for testing
    set /p CONTINUE="Continue without PostgreSQL? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        exit /b 1
    )
) else (
    for /f "tokens=*" %%i in ('psql --version') do echo Found %%i
)
echo.

REM Create virtual environment for backend
echo Creating Python virtual environment for backend...
if not exist "backend\venv" (
    cd backend
    python -m venv venv
    cd ..
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

REM Activate virtual environment and install dependencies
echo Installing backend dependencies...
call backend\venv\Scripts\activate.bat
pip install --upgrade pip setuptools wheel
pip install -r backend\requirements.txt
call backend\venv\Scripts\deactivate.bat
echo Backend dependencies installed
echo.

REM Create logs directory
echo Creating logs directory...
if not exist "backend\logs" mkdir backend\logs
echo Logs directory created
echo.

REM Create uploads directory
echo Creating uploads directory...
if not exist "backend\uploads" mkdir backend\uploads
echo Uploads directory created
echo.

REM Check .env file
echo Checking environment configuration...
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy backend\.env.example backend\.env
        echo Created backend\.env from template
        echo IMPORTANT: Please edit backend\.env with your configuration
    )
) else (
    echo backend\.env already exists
)
echo.

REM Check frontend node_modules
echo Checking frontend setup...
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    if exist "frontend\package.json" (
        where npm >nul 2>&1
        if errorlevel 1 (
            echo WARNING: Node.js/npm is not installed
            echo Please install Node.js from https://nodejs.org/
            echo Then run: cd frontend ^&^& npm install
        ) else (
            cd frontend
            call npm install
            cd ..
            echo Frontend dependencies installed
        )
    )
) else (
    echo Frontend dependencies already installed
)
echo.

echo ======================================
echo Setup Complete!
echo ======================================
echo.
echo Next steps:
echo.
echo 1. Configure database (optional - can use SQLite for testing):
echo    - Edit backend\.env with your PostgreSQL credentials
echo    - Or leave as-is to use SQLite
echo.
echo 2. Start the backend server:
echo    - Run: start_backend.bat
echo.
echo 3. In another terminal, start the frontend:
echo    - Run: start_frontend.bat
echo.
echo 4. Access the application:
echo    Backend API: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo    Frontend: http://localhost:3000
echo.
pause
