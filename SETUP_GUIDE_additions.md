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

4) Create the first administrator:
   python .\setup_local.py
   (creates all tables and prompts interactively for email, username, name, and password - nothing is passed as a command-line argument)

5) Run backend (example):
   cd backend
   .\venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

6) Run frontend (example):
   cd frontend
   npm install
   npm start

Note: Do not run these on production. Use environment-managed secrets for production deployment.
