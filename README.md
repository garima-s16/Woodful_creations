Woodful Creations - AI-Powered Management System

Welcome to Woodful Creations, a comprehensive business management system designed for woodcraft and furniture design businesses.

Quick Start

1. Clone Repository
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations

2. Set Up PostgreSQL
Follow the setup guide to create the database:
- Database: woodful_creations
- User: woodful_user

3. Backend Setup
cd backend
python -m venv venv

Windows:
venv\Scripts\activate

macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

Copy .env.example to .env and configure:
cp .env.example .env

4. Frontend Setup
cd frontend
npm install
cp .env.example .env

5. Run Applications

Terminal 1 - Backend:
cd backend
source venv/bin/activate
python main.py

Terminal 2 - Frontend:
cd frontend
npm start

Access the application:
- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

Docker Deployment

docker-compose up

System Requirements
- Python 3.9+
- Node.js 14+
- PostgreSQL 12+
- 8GB RAM minimum

Default Admin Users
- Username: nikhils / Password: Nikhil*27
- Username: garimas / Password: Gullak*16

Features
- Stock Inventory Management
- Cost Estimation
- Client Management
- Employee Management
- Attendance Tracking
- Interview Management
- AI Chat Assistant
- Analytics Dashboard
- Document Generation
- Multi-level Access Control

Support
For detailed setup instructions, see SETUP_GUIDE.md
For project details, see PROJECT_INFO.md

License
Private Project - Woodful Creations
