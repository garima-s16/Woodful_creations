WEBSITE LAUNCH INSTRUCTIONS

Quick Start Guide

Prerequisites Installed:
- Node.js (v14+)
- Python 3.8+
- npm

Step 1: Install Dependencies

From the project root directory:

npm install
cd frontend && npm install && cd ..
cd backend && pip install -r requirements.txt && cd ..

Step 2: Start the Application

Option A: Run Everything at Once (Recommended)

From project root:
npm start

This will start both backend (port 8000) and frontend (port 3000) simultaneously.

Option B: Start Services Separately

Terminal 1 - Backend:
cd backend
python main.py

Terminal 2 - Frontend:
cd frontend
npm start

Step 3: Access the Website

Open your browser and navigate to:
http://localhost:3000

Step 4: Login

Use one of the demo accounts:

Master User (Nikhil):
- Email: nikhil@woodful.com
- Password: nikhil123
- Access: All features including Master Controls

Master User (Garima):
- Email: garima@woodful.com
- Password: garima123
- Access: All features including Master Controls

Regular User:
- Email: user@woodful.com
- Password: user123
- Access: Limited features (no Payments or Analytics)

Quick Demo:
Click "Demo Login" button to log in instantly as Nikhil

FEATURES AVAILABLE NOW

Dashboard:
- Overview of key business metrics
- Recent activity tracking
- Quick action buttons
- Statistics cards

Stock Inventory:
- View all products with quantity and pricing
- Add new products
- Search and filter by category
- Low stock alerts and warnings
- Product editing (Master and User roles)

AI Chat Widget:
- Available on all pages via floating Chat button
- Ask questions about inventory and business
- Real-time responses from AI
- Conversation history

Navigation:
- Easy access to all modules
- Role-based menu (Master sees Payments and Analytics)
- Profile management
- Logout functionality

FEATURES COMING SOON

Cost Estimates:
- Create professional estimates
- PDF generation with product images
- Cost breakdown and client details

Client Management:
- Individual client profiles
- Order history and status tracking
- Design, execution, and delivery status
- Payment tracking by client

Employee Attendance:
- Daily attendance tracking
- Salary calculation
- Salary slip generation (Indian law compliant)
- Payroll management

Interview Management:
- Interview scheduling
- Candidate tracking
- Status updates
- Hiring pipeline management

Payment Management (Master Users Only):
- View all outstanding payments
- Payment tracking and history
- Alerts for pending payments
- Payment reports

Advanced Analytics (Master Users Only):
- Custom business reports
- Data visualization
- Export to Excel, PDF, Word
- Performance metrics and KPIs

TECHNICAL DETAILS

Frontend Stack:
- React 18.2.0
- Redux Toolkit for state management
- React Router for navigation
- Axios for API calls
- CSS3 with responsive design
- Mobile-friendly interface

Backend Stack:
- FastAPI (Python)
- JWT authentication
- CORS enabled
- RESTful API design
- In-memory database (development)

Project Structure:
frontend/
  src/
    pages/          - Page components
    components/     - Reusable components
    styles/         - CSS stylesheets
    utils/          - API client and utilities
    redux/          - State management
    index.jsx       - React entry point

backend/
  main.py           - FastAPI application
  requirements.txt  - Python dependencies
  .env              - Configuration

TROUBLESHOOTING

Issue: Port already in use
Solution: Kill the process on port 3000 or 8000, or change the port

Issue: Frontend can't connect to backend
Solution: Ensure backend is running on localhost:8000
Check browser console for CORS errors
Verify API_URL in frontend/.env

Issue: Login fails with all credentials
Solution: Check if backend is running
Verify database credentials in backend/.env
Try restarting both services

Issue: Sidebar not showing
Solution: Refresh the page
Check browser console for JavaScript errors
Clear browser cache

Issue: Chat widget not responding
Solution: Verify backend API is accessible
Check network tab in browser dev tools
Ensure authToken is stored in localStorage

BUILD FOR PRODUCTION

Frontend Build:
cd frontend
npm run build

This creates optimized production build in frontend/build directory.

Environment Variables for Production:
Update frontend/.env:
REACT_APP_API_URL=https://your-api-domain.com

Update backend/.env:
DEBUG=False
SECRET_KEY=your-secure-secret-key
DATABASE_URL=postgresql://user:pass@host/db
ENVIRONMENT=production

DOCKER DEPLOYMENT

From project root:
docker-compose up

This starts:
- Frontend on http://localhost:3000
- Backend API on http://localhost:8000

DATABASE SETUP (Production)

For PostgreSQL database:
1. Create database: CREATE DATABASE woodful_creations;
2. Update DATABASE_URL in backend/.env
3. Run migrations (when implemented)

API DOCUMENTATION

Access Swagger UI at: http://localhost:8000/docs
Access ReDoc at: http://localhost:8000/redoc

Key Endpoints:
POST   /api/auth/login           - User login
GET    /api/dashboard            - Dashboard data
GET    /api/inventory            - Get all products
POST   /api/inventory            - Add product
PATCH  /api/inventory/{id}       - Update product
POST   /api/chat                 - Send chat message
GET    /api/health               - API health check

SUPPORT & HELP

Check LAUNCH_GUIDE.md for detailed setup
Review backend/API_DOCUMENTATION.md for API details
Check frontend/src for component structure
Review .env files for configuration options

For issues:
1. Check browser console for errors
2. Check backend console output
3. Verify environment variables
4. Check network requests in DevTools

Version: 1.0.0
Last Updated: June 2026
Status: Active Development