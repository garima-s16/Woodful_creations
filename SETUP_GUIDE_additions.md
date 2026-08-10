Additions to SETUP_GUIDE for bootstrap:

1) Place logo:
   - Copy your logo image to frontend\public\logo.png

2) Create virtualenv and install backend deps:
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt

3) Initialize DB tables and seed sample data:
   cd backend
   # Copy backend\.env.example to backend\.env and set DATABASE_URL there (never edit config.py directly)
   cd scripts
   python .\seed_sample_data.py

4) Create master users (if not created by seeder):
   python .\create_master_user.py --email garima@woodfulcreations.com --username garimas --name "Garima Sharma"
   python .\create_master_user.py --email nikhil@woodfulcreations.com --username nikhils --name "Nikhil"
   # Omit --password so you are prompted interactively - keeps real passwords out of shell history and git

5) Run backend (example):
   cd backend
   .\venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

6) Run frontend (example):
   cd frontend
   npm install
   npm start

Note: Do not run these on production. Use environment-managed secrets for production deployment.
