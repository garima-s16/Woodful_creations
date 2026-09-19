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
    if errorlevel 1 (
        echo ERROR: Failed to create the Python virtual environment.
        cd ..
        exit /b 1
    )
    cd ..
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

REM Activate virtual environment and install dependencies. Previously
REM none of these three steps checked errorlevel at all - batch does not
REM abort on a failing command the way bash's `set -e` does, so a failed
REM pip install (or venv activation) here silently fell through all the
REM way to "Setup Complete!" below with a half-installed environment.
echo Installing backend dependencies...
call backend\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate the Python virtual environment.
    exit /b 1
)
pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip/setuptools/wheel.
    call backend\venv\Scripts\deactivate.bat
    exit /b 1
)
pip install -r backend\requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install backend dependencies from backend\requirements.txt.
    call backend\venv\Scripts\deactivate.bat
    exit /b 1
)
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
        REM SECRET_KEY ships empty in .env.example (never a real secret in
        REM a committed file) - but app\platform\config.py requires a real
        REM 32+ char value just to import the app at all, which the
        REM migration step immediately below does. Left empty, "alembic
        REM upgrade head" below fails on every fresh setup before a user
        REM ever gets a chance to edit the file. Auto-generate a real
        REM local-dev-only secret now (Python is already required above),
        REM the same way .env.example's own comment tells a person to by
        REM hand - only runs inside this "doesn't exist yet" branch, so it
        REM can never overwrite a value someone already set.
        python -c "import re, secrets, pathlib; p = pathlib.Path('backend/.env'); t = p.read_text(); t = re.sub(r'(?m)^SECRET_KEY=.*$', 'SECRET_KEY=' + secrets.token_urlsafe(48), t); p.write_text(t)"
        if errorlevel 1 (
            echo ERROR: Failed to generate a SECRET_KEY into backend\.env.
            exit /b 1
        )
        echo Generated a local-development SECRET_KEY in backend\.env
        echo IMPORTANT: Please review backend\.env - the SECRET_KEY above is fine for local dev only; every other value (database, email, AI keys) still needs your own configuration
    )
) else (
    echo backend\.env already exists
)
echo.

REM Run database migrations - without this, a fresh clone has a venv,
REM dependencies, and a .env file, but no database tables at all, and
REM the app fails with confusing errors the moment it's actually run
REM (SQLite by default; uses whatever DATABASE_URL is configured in
REM backend\.env above). Only meaningful once .env exists, hence run
REM after the check above rather than immediately after dependency
REM install.
echo Running database migrations...
call backend\venv\Scripts\activate.bat
cd backend
alembic upgrade head
REM Previously this only printed a WARNING on failure and fell straight
REM through to "Setup Complete!" below with no tables in the database.
REM A failed migration must stop setup here, with a non-zero exit code.
if errorlevel 1 (
    echo.
    echo ERROR: Database migration failed. Check backend\.env's DATABASE_URL and SECRET_KEY, then run "cd backend ^&^& alembic upgrade head" manually to see the full error.
    cd ..
    call backend\venv\Scripts\deactivate.bat
    exit /b 1
) else (
    echo Migrations applied
)
cd ..
call backend\venv\Scripts\deactivate.bat
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
            if errorlevel 1 (
                echo ERROR: Failed to install frontend dependencies ^(npm install^).
                cd ..
                exit /b 1
            )
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
echo 2. Start both servers:
echo    - Run: start_all.bat
echo.
echo 3. Access the application:
echo    Backend API: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo    Frontend: http://localhost:3000
echo.
pause
