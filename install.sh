#!/bin/bash

# Woodful Creations - Complete Launch Script

echo "=========================================="
echo "Woodful Creations - Website Launcher"
echo "=========================================="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    echo "Please install Node.js from https://nodejs.org"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3 from https://python.org"
    exit 1
fi

echo "Node.js version: $(node --version)"
echo "Python version: $(python3 --version)"
echo ""

# Install root dependencies
echo "Step 1: Installing root dependencies..."
npm install

# Install frontend dependencies
echo ""
echo "Step 2: Installing frontend dependencies..."
cd frontend
npm install
cd ..

# Install backend dependencies
echo ""
echo "Step 3: Installing backend dependencies..."
cd backend
pip install -r requirements.txt
cd ..

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "To start the website, run:"
echo "  npm start"
echo ""
echo "This will start:"
echo "  - Backend API: http://localhost:8000"
echo "  - Frontend: http://localhost:3000"
echo ""
echo "Login with:"
echo "  Email: nikhil@woodful.com"
echo "  Password: nikhil123"
echo ""
echo "Or click 'Demo Login' for instant access"
echo "=========================================="
