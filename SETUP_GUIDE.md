# Woodful Creations Setup Guide

## 1. Clone the repository

```bash
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations
```

## 2. Configure PostgreSQL

Create a PostgreSQL database for the application and a database user with access to it.

Example SQL:

```sql
CREATE DATABASE woodful_creations;
CREATE USER woodful_user WITH PASSWORD 'replace_this_password';
GRANT ALL PRIVILEGES ON DATABASE woodful_creations TO woodful_user;
```

## 3. Configure the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `backend/.env` with your real values.

Required values:

- `DATABASE_URL`
- `SECRET_KEY`
- `SERVER_HOST=0.0.0.0`
- `SERVER_PORT=8000`

Start the backend:

```bash
python main.py
```

Verify the API:

```bash
curl http://localhost:8000/api/health
```

## 4. Configure the web frontend

```bash
cd ../frontend
npm install
cp .env.example .env
npm start
```

## 5. Configure and run the Expo iPhone app

From the repository root:

```bash
cd ..
npm install
npm run mobile:start:tunnel
```

Then:

1. Install Expo Go on your iPhone.
2. Scan the Expo QR code.
3. On the mobile login screen, enter a backend URL reachable from your iPhone, such as `http://192.168.1.25:8000`.
4. Tap `Test connection`.
5. Sign in with an existing backend user account.

## 6. Troubleshooting iPhone connectivity

### Problem: the phone cannot reach the backend

Check the following:

- the backend is running
- the backend machine and iPhone are on networks that can reach each other
- the backend is listening on `0.0.0.0:8000`
- local firewall rules allow inbound traffic on port 8000

### Problem: Expo Go cannot open the app from the QR code

Try the tunnel workflow:

```bash
npm run mobile:start:tunnel
```

### Problem: the mobile app still points at localhost

On the login screen, replace the API URL with your machine's LAN IP and test again.
