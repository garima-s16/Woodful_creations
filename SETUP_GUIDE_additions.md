Additions to SETUP_GUIDE for bootstrap:

1) Place logo:
   - Copy your logo image to frontend\public\logo.png

2) Create virtualenv and install backend deps:
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt

3) Initialize DB tables and seed sample data:
   cd backend\scripts
   # Ensure DATABASE_URL in backend\app\core\config.py points to your local DB
   python .\seed_sample_data.py

4) Create master users (if not created by seeder):
   python .\create_master_user.py --email admin1@example.com --username admin1 --name "Garima Sharma" --password "<CHANGE_ME_ADMIN1_PASSWORD>"
   python .\create_master_user.py --email admin2@example.com --username admin2 --name "Nikhil" --password "<CHANGE_ME_ADMIN2_PASSWORD>"

5) Run backend (example):
   cd backend
   .\venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

6) Run frontend (example):
   cd frontend
   npm install
   npm start

Note: Do not run these on production. Use environment-managed secrets for production deployment.
