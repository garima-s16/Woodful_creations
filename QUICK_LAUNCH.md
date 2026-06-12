QUICK START - WOODFUL CREATIONS

OPTION 1: Automated Setup (Recommended)

Linux/Mac:
  chmod +x install.sh
  ./install.sh

Windows:
  install.bat

This will:
  - Check Node.js and Python installation
  - Install all dependencies
  - Display launch instructions

OPTION 2: Manual Setup

1. Install dependencies:
   npm install
   cd frontend && npm install && cd ..
   cd backend && pip install -r requirements.txt && cd ..

2. Start the services:
   npm start

3. Open browser:
   http://localhost:3000

LOGIN CREDENTIALS

Master User (Nikhil):
  Email: nikhil@woodful.com
  Password: nikhil123

Master User (Garima):
  Email: garima@woodful.com
  Password: garima123

Regular User:
  Email: user@woodful.com
  Password: user123

Demo Login:
  Click "Demo Login" button for instant access

WHAT'S RUNNING

Backend API:
  - URL: http://localhost:8000
  - API Docs: http://localhost:8000/docs
  - Health Check: http://localhost:8000/api/health

Frontend:
  - URL: http://localhost:3000
  - Technology: React 18
  - Features: Dashboard, Stock Inventory, AI Chat

FEATURES AVAILABLE

Dashboard:
  - Business metrics overview
  - Recent activity feed
  - Quick action buttons

Stock Inventory:
  - View all products
  - Add/Edit products
  - Search and filter
  - Low stock alerts

AI Chat Assistant:
  - Available on all pages
  - Answer inventory questions
  - Provide business insights

Navigation:
  - Easy menu system
  - Role-based access
  - User profile management

TROUBLESHOOTING

Port Already in Use:
  Backend (8000): lsof -ti:8000 | xargs kill -9
  Frontend (3000): lsof -ti:3000 | xargs kill -9

Backend Won't Start:
  - Check Python 3.8+ is installed
  - Verify dependencies: pip install -r requirements.txt
  - Check backend/.env file

Frontend Won't Load:
  - Check Node.js v14+ is installed
  - Clear npm cache: npm cache clean --force
  - Delete node_modules: rm -rf node_modules && npm install

Connection Issues:
  - Ensure backend is running first
  - Check CORS settings in backend/.env
  - Clear browser cache and localStorage

NEXT STEPS

After launching:
  1. Explore Dashboard
  2. Add products to Stock Inventory
  3. Try AI Chat widget
  4. Familiarize with navigation

Coming Soon:
  - Client Management
  - Cost Estimates
  - Attendance Tracking
  - Interview Management
  - Advanced Analytics

For detailed documentation, see:
  - STARTUP_GUIDE.md
  - LAUNCH_GUIDE.md
  - PROJECT_REQUIREMENTS.md
