Woodful Creations - Launch Guide

Quick Start

The Woodful Creations website is ready to launch. Follow these steps to get it running:

Prerequisites

- Node.js (v14 or higher)
- Python (v3.8 or higher)
- npm or yarn
- Git

Step 1: Clone or Navigate to Repository

Clone the repository:
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations

Step 2: Install Backend Dependencies

Navigate to backend directory:
cd backend

Install Python dependencies:
pip install -r requirements.txt

Step 3: Install Frontend Dependencies

Navigate to frontend directory:
cd ../frontend

Install Node dependencies:
npm install

Step 4: Start the Services

Option A: Run Services Simultaneously (Recommended)

From root directory, run:
npm run dev

This starts both backend (port 8000) and frontend (port 3000).

Option B: Run Services Separately

Terminal 1 - Start Backend:
cd backend
python main.py

Terminal 2 - Start Frontend:
cd frontend
npm start

Step 5: Access the Application

Frontend: http://localhost:3000
Backend API: http://localhost:8000

API Documentation: http://localhost:8000/docs

Login Credentials

Master Users:
Email: nikhil@woodful.com
Password: nikhil123

Email: garima@woodful.com
Password: garima123

Regular User:
Email: user@woodful.com
Password: user123

Demo Login:
Click "Demo Login" on the login page for instant access.

Features Currently Available

Dashboard - Overview of business metrics
Stock Inventory - Manage products with low stock alerts
AI Chat Assistant - Ask questions about inventory and orders
Navigation - Easy access to all modules

Upcoming Features

Cost Estimates - Create and share PDF estimates
Client Management - Track client orders and details
Attendance Management - Track employees and calculate salaries
Interview Tracking - Manage hiring process
Payment Management - Track payments (Master users only)
Advanced Analytics - Business reports and insights

Technology Stack

Frontend
- React 18.2
- React Router for navigation
- Axios for API communication
- CSS3 with custom design system
- Responsive design for desktop and mobile

Backend
- FastAPI (Python)
- JWT for authentication
- CORS support for cross-origin requests
- RESTful API design

Database
- SQLite for development
- PostgreSQL ready for production

Troubleshooting

Frontend won't load on localhost:3000
Check if port 3000 is available
Try: npm start from frontend directory
Check browser console for errors

Backend API not responding
Check if port 8000 is available
Verify Python dependencies installed
Run: python main.py from backend directory
Check API health: http://localhost:8000/api/health

CORS errors in console
Ensure backend is running on localhost:8000
Check CORS_ORIGINS in backend/.env

Login fails
Verify credentials: use demo accounts provided above
Check if backend API is responding

File Structure

Woodful_creations/
backend/
  - main.py (FastAPI application)
  - requirements.txt (Python dependencies)
  - .env (Backend configuration)
frontend/
  - src/ (React components and pages)
  - public/ (Static files)
  - package.json (Node dependencies)
  - .env (Frontend configuration)

Docker Deployment

To run with Docker:
docker-compose up

This starts both frontend and backend services.

Production Deployment

Update SECRET_KEY in backend/.env
Configure DATABASE_URL for PostgreSQL
Set ENVIRONMENT=production
Update CORS_ORIGINS for your domain
Build frontend: npm run build
Deploy using your preferred platform

Support

For issues or questions:
Check the documentation in PROJECT_REQUIREMENTS.md
Review API_REFERENCE.md for endpoint details
Check backend/API_DOCUMENTATION.md

Contact: support@woodfulcreations.com

Version Information

Woodful Creations v1.0.0
Release Date: June 2026
Status: Active Development