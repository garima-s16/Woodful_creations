# Woodful Creations - AI-Powered Management System

Woodful Creations is a comprehensive business management system designed for woodcraft and furniture design businesses.

## Features

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

## System Requirements

- Python 3.9+
- Node.js 14+
- PostgreSQL 12+
- 8 GB RAM minimum

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then edit .env with your values
```

### 3. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
```

### 4. Run Locally

Open two terminals:

```bash
# Terminal 1 - Backend
cd backend && source venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend && npm start
```

Access points:
- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Docker (alternative)

```bash
docker-compose up
```

## Documentation

- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Full installation and configuration guide
- [PROJECT_INFO.md](PROJECT_INFO.md) - Architecture, modules, roles, and roadmap
- [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) - Launch verification checklist

## License

Private Project - Woodful Creations
