# Woodful Creations - Quick Start Guide

## Prerequisites

Before running the application, ensure you have the following installed:

1. **Python 3.10 or higher**
   - Download from: https://www.python.org/downloads/
   - On Windows: Check "Add Python to PATH" during installation

2. **Node.js 16 or higher** (for frontend)
   - Download from: https://nodejs.org/

3. **PostgreSQL 13 or higher** (optional, SQLite works for development)
   - Download from: https://www.postgresql.org/download/

## Quick Start (5 minutes)

### Option 1: Using Setup Scripts (Recommended)

#### On Linux/Mac:
```bash
chmod +x setup.sh start_all.sh start_backend.sh start_frontend.sh
./setup.sh        # Run once to set up environment
./start_all.sh    # Start both backend and frontend
```

#### On Windows:
```cmd
setup.bat         # Run once to set up environment
start_all.bat     # Start both backend and frontend
```

### Option 2: Manual Setup

#### Step 1: Backend Setup
```bash
cd backend

python -m venv venv

source venv/bin/activate    # On Linux/Mac
REM or
venv\Scripts\activate.bat    # On Windows

pip install -r requirements.txt

cp .env.example .env

python main.py
```

Backend available at: http://localhost:8000

#### Step 2: Frontend Setup (another terminal)
```bash
cd frontend

npm install

npm start
```

Frontend available at: http://localhost:3000

## Application Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs
- Health Check: http://localhost:8000/health

## Database Setup (Optional)

### PostgreSQL
```bash
creatdb woodful_creations
psql -U username -d woodful_creations < database/schema.sql
```

Update .env:
```
DATABASE_URL=postgresql://username:password@localhost:5432/woodful_creations
```

### SQLite (Default for Development)
No setup needed - uses local SQLite database

## Docker Setup (Alternative)

```bash
docker-compose up --build
```

Access:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Troubleshooting

### Backend Issues
- Check port 8000: `lsof -i :8000` (Mac/Linux)
- Check Python: `python --version` (need 3.10+)
- Reinstall deps: `pip install -r requirements.txt`

### Frontend Issues
- Check port 3000: `lsof -i :3000` (Mac/Linux)
- Check Node: `node --version` (need 16+)
- Clear cache: `npm cache clean --force`

### Database Issues
- Verify PostgreSQL running
- Check .env credentials
- Test: `psql -U username -h localhost -d woodful_creations`

## Project Structure

```
Woodful_creations/
backend/
  main.py
  requirements.txt
  app/
    core/
    api/routes/
    models/
    services/
  logs/
  uploads/

frontend/
  package.json
  src/
  public/

database/
  schema.sql

setup.sh/setup.bat
start_all.sh/start_all.bat
start_backend.sh/start_backend.bat
start_frontend.sh/start_frontend.bat
docker-compose.yml
```

## Environment Variables

Key .env variables:
```
DATABASE_URL=postgresql://user:password@localhost:5432/woodful_creations
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EMAIL_USER=your-email@gmail.com
OPENAI_API_KEY=your-api-key
ENVIRONMENT=development
DEBUG=True
```

## Next Steps

1. Set up database
2. Configure .env
3. Create master users (Nikhil & Garima)
4. Start developing!

Enjoy Woodful Creations!
