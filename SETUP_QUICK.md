# QUICK SETUP GUIDE

## Prerequisites
- Python 3.9+
- Node.js 14+
- PostgreSQL 12+
- Git

## Installation (5 minutes)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Database
Create `.env` file in backend/:
```
DATABASE_URL=postgresql://user:password@localhost:5432/woodful_creations
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=your-openai-key
```

### 3. Initialize Database
```bash
python scripts/init_db.py
python scripts/create_master_user.py
```

### 4. Frontend Setup
```bash
cd frontend
npm install
```

### 5. Launch

Terminal 1 (Backend):
```bash
cd backend
python main.py
```

Terminal 2 (Frontend):
```bash
cd frontend
npm start
```

## Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Default User: nikhil@woodful.com / Welcome@123

## Troubleshooting

**Database Connection Error**
- Verify PostgreSQL is running
- Check DATABASE_URL in .env
- Ensure database exists: `createdb woodful_creations`

**Port Already in Use**
```bash
# Linux/Mac
lsof -i :8000

# Windows
netstat -ano | findstr :8000
```

**Module Not Found**
```bash
# Backend
pip install -r requirements.txt

# Frontend
rm -rf node_modules && npm install
```

## Next Steps
1. Login with master user credentials
2. Navigate to Stock Inventory
3. Add test products
4. Try AI Chat for inventory queries
5. Explore other features
