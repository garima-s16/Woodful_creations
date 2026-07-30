# Woodful Creations - AI-Powered Management System

Comprehensive business management system for woodcraft and furniture design businesses.

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations
```

### 2. Set Up PostgreSQL

Follow the setup guide to create the database:
- Database: `woodful_creations`
- User: `woodful_user`

### 3. Backend Setup

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database URL and secret key
```

### 4. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
```

### 5. Run Applications

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
python main.py

# Terminal 2 - Frontend
cd frontend
npm start
```

Access the application:
- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Docker Deployment

```bash
docker-compose up
```

## System Requirements

- Python 3.9+
- Node.js 14+
- PostgreSQL 12+
- 8 GB RAM minimum

## Default Admin Users

User accounts are created via the database initialization scripts. See `SETUP_GUIDE.md` for instructions. Default usernames are configured in `backend/scripts/create_master_user.py`.

## Features

- Stock Inventory Management
- Cost Estimation
- Client Management
- Employee Management
- Attendance Tracking
- Interview Management
- AI Chat Assistant
- Analytics Dashboard
- Document Generation (PDF, Excel, Word)
- Multi-level Access Control
- Progressive Web App (PWA) — installable on iOS, Android, and desktop

## PWA and Mobile Support

The frontend is a Progressive Web App. To install:

- **iOS Safari**: Open the site and tap "Add to Home Screen"
- **Android Chrome**: Look for the install prompt or use the browser menu
- **Desktop**: Use the install icon in the address bar (Chrome/Edge)

To test PWA behavior locally, build and serve the production bundle:

```bash
cd frontend
npm run build
npx serve -s build
```

For production use, add icon files at `frontend/public/icons/icon-192.png`, `icon-512.png`, and `apple-touch-icon.png`.

## Support

For detailed setup instructions, see `SETUP_GUIDE.md`.
For project details, see `PROJECT_INFO.md`.

## License

Private Project - Woodful Creations
