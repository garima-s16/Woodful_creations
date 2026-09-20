@echo off
cd /d "C:\Automation_Files\Woodful_creations"
echo ======================================
echo WOODFUL VERIFICATION - BACKEND PYTEST
echo ======================================
cd backend
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: could not activate backend venv
    goto FRONTEND
)
python -u -m pytest -q --tb=short > ..\test_results_backend.log 2>&1
echo BACKEND_EXIT_CODE=%errorlevel% >> ..\test_results_backend.log
type ..\test_results_backend.log
call venv\Scripts\deactivate.bat
cd ..

:FRONTEND
echo.
echo ======================================
echo WOODFUL VERIFICATION - FRONTEND BUILD
echo ======================================
cd frontend
call npm run build > ..\test_results_frontend.log 2>&1
echo FRONTEND_EXIT_CODE=%errorlevel% >> ..\test_results_frontend.log
type ..\test_results_frontend.log
cd ..

echo.
echo ======================================
echo ALL CHECKS COMPLETE
echo See test_results_backend.log and test_results_frontend.log in the project folder for the full output.
echo ======================================
pause
