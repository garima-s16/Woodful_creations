@echo off
REM Woodful Creations - Development Setup Script for Windows

setlocal enabledelayedexpansion

REM Every check/command below uses a path relative to this script's own
REM folder (backend\venv, backend\requirements.txt, frontend\node_modules,
REM ...) - it never assumed the caller's current directory matched where
REM this file lives, which silently broke it whenever that assumption was
REM wrong: launching via "Run as administrator" starts a batch file with
REM its working directory forced to C:\Windows\System32, not the script's
REM folder; a desktop shortcut with a different "Start in" value, or
REM running this from an already-open terminal sitting in some other
REM directory, have the same effect. Every relative path then resolves
REM against the wrong folder and the script fails immediately with no
REM useful message. cd /d "%~dp0" pins the working directory to this
REM file's own location first, regardless of how/from-where it was
REM launched - the same fix woodful_full_verification.bat already applies
REM via its own SCRIPT_DIR.
cd /d "%~dp0"

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
        pause
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
        pause
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
    pause
    exit /b 1
)
pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip/setuptools/wheel.
    call backend\venv\Scripts\deactivate.bat
    pause
    exit /b 1
)
pip install -r backend\requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install backend dependencies from backend\requirements.txt.
    call backend\venv\Scripts\deactivate.bat
    pause
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
REM
REM The explanatory comments and the "review your .env" message used to
REM live INSIDE the if/else block below - one as multi-line REM comments,
REM the other as an echo line containing literal, unescaped parentheses
REM "(database, email, AI keys)". Windows cmd.exe parses an entire
REM parenthesized if/else block as one unit before running it, and it
REM counts parentheses and quote characters even inside REM comments and
REM echo text that sit inside that block - even in the branch that never
REM executes. An unescaped "(" or ")" in there, or an odd number of "
REM characters, throws off cmd's block-matching and aborts the whole
REM statement with "... was unexpected at this time." before a single
REM line of it runs. That is exactly what was happening here: even
REM though backend\.env already existed (so only the harmless "else"
REM line should have run), the unused "if" branch's malformed text broke
REM the parse for the entire block. Fix: explanatory comments now live
REM here, above the block, where they can't affect its parsing; the
REM "review your .env" message below has its parentheses escaped with
REM ^( and ^) so cmd treats them as literal characters, not block syntax.
REM
REM SECRET_KEY ships empty in .env.example (never a real secret in a
REM committed file) - but app\platform\config.py requires a real 32+
REM char value just to import the app at all, which the migration step
REM immediately below does. Left empty, alembic upgrade head below fails
REM on every fresh setup before a user ever gets a chance to edit the
REM file. Auto-generate a local-dev-only secret now (Python is already
REM required above), the same way .env.example's own comment tells a
REM person to by hand - only runs inside the "doesn't exist yet" branch
REM below, so it can never overwrite a value someone already set.
echo Checking environment configuration...
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy backend\.env.example backend\.env
        echo Created backend\.env from template
        python -c "import re, secrets, pathlib; p = pathlib.Path('backend/.env'); t = p.read_text(); t = re.sub(r'(?m)^SECRET_KEY=.*$', 'SECRET_KEY=' + secrets.token_urlsafe(48), t); p.write_text(t)"
        if errorlevel 1 (
            echo ERROR: Failed to generate a SECRET_KEY into backend\.env.
            pause
            exit /b 1
        )
        echo Generated a local-development SECRET_KEY in backend\.env
        echo IMPORTANT: Please review backend\.env - the SECRET_KEY above is fine for local dev only; every other value ^(database, email, AI keys^) still needs your own configuration
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
    pause
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
                pause
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
