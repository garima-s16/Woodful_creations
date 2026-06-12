#!/bin/bash

OS_TYPE=$(uname -s)
case "$OS_TYPE" in
    Darwin*)
        OS_NAME="macOS"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        OS_NAME="Windows"
        ;;
    Linux*)
        OS_NAME="Linux"
        ;;
    *)
        OS_NAME="Unknown"
        ;;
esac

echo "WOODFUL CREATIONS - Application Launcher"
echo "Detected OS: $OS_NAME"
echo ""
echo "Select an option:"
echo "1. Run Full Setup (Backend + Frontend)"
echo "2. Run Backend Only (FastAPI)"
echo "3. Run Frontend Only (React)"
echo "4. Run Desktop App (PyQt5)"
echo "5. Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "Running full setup..."
        bash scripts/setup.sh
        
        echo ""
        echo "Setup complete. Starting services..."
        
        if [ "$OS_NAME" = "Windows" ]; then
            start cmd /k "cd backend && venv\Scripts\activate && uvicorn app.main:app --reload"
            start cmd /k "npm run dev"
        else
            cd backend
            source venv/bin/activate
            uvicorn app.main:app --reload &
            cd ..
            npm run dev &
        fi
        
        echo "Backend running on http://localhost:8000"
        echo "Frontend running on http://localhost:3000"
        echo "Press Ctrl+C to stop services"
        wait
        ;;
        
    2)
        echo "Starting FastAPI Backend..."
        cd backend
        
        if [ ! -d "venv" ]; then
            echo "Creating virtual environment..."
            python3 -m venv venv
        fi
        
        if [ "$OS_NAME" = "Windows" ]; then
            call venv\Scripts\activate.bat
        else
            source venv/bin/activate
        fi
        
        if [ ! -f "requirements.txt" ]; then
            echo "requirements.txt not found. Running setup first..."
            bash ../scripts/setup.sh
        fi
        
        echo "Installing dependencies..."
        pip install --upgrade pip > /dev/null 2>&1
        pip install -r requirements.txt > /dev/null 2>&1
        
        echo ""
        echo "Starting FastAPI server..."
        echo "Backend running on http://localhost:8000"
        echo "API Documentation: http://localhost:8000/docs"
        echo "Press Ctrl+C to stop"
        
        uvicorn app.main:app --reload
        ;;
        
    3)
        echo "Starting React Frontend..."
        
        if [ ! -f "package.json" ]; then
            echo "package.json not found. Running setup first..."
            bash scripts/setup.sh
        fi
        
        if [ ! -d "node_modules" ]; then
            echo "Installing Node dependencies..."
            npm install
        fi
        
        echo ""
        echo "Starting React development server..."
        echo "Frontend running on http://localhost:3000"
        echo "Press Ctrl+C to stop"
        
        npm run dev
        ;;
        
    4)
        echo "Starting PyQt5 Desktop Application..."
        
        if [ ! -d "desktop" ]; then
            echo "Desktop directory not found."
            exit 1
        fi
        
        cd desktop
        
        if [ ! -d "venv" ]; then
            echo "Creating virtual environment..."
            python3 -m venv venv
        fi
        
        if [ "$OS_NAME" = "Windows" ]; then
            call venv\Scripts\activate.bat
        else
            source venv/bin/activate
        fi
        
        if [ ! -f "requirements.txt" ]; then
            echo "requirements.txt not found."
            exit 1
        fi
        
        echo "Installing dependencies..."
        pip install --upgrade pip > /dev/null 2>&1
        pip install -r requirements.txt > /dev/null 2>&1
        
        echo ""
        echo "Starting Desktop Application..."
        
        if [ -f "main.py" ]; then
            python main.py
        else
            echo "main.py not found in desktop directory"
            exit 1
        fi
        ;;
        
    5)
        echo "Exiting..."
        exit 0
        ;;
        
    *)
        echo "Invalid choice. Exiting..."
        exit 1
        ;;
esac
