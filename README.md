# Woodful Creations

Woodful Creations is a business management system for inventory, clients, estimates, payments, attendance, interviews, analytics, and AI chat.

This repository now supports:

- the existing web frontend in `frontend/`
- the FastAPI backend in `backend/`
- a native Expo/React Native iPhone app from the repository root

## Repository layout

- `backend/` FastAPI API and database models
- `frontend/` React web frontend
- `mobile/` React Native mobile source used by Expo
- `database/` SQL schema assets

## Core mobile coverage

The native app reuses the existing backend APIs and product concepts for:

- authentication
- dashboard overview
- inventory
- clients
- payments
- AI chat
- additional module overviews for estimates, attendance, interviews, and analytics

## Prerequisites

- Node.js 18 or newer
- npm 9 or newer
- Python 3.9 or newer
- PostgreSQL 12 or newer
- An iPhone with Expo Go installed for the standard device workflow

## Backend setup

1. Create and activate a virtual environment:

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   ```

2. Install backend dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create `backend/.env` from `backend/.env.example` and set at least:
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `SERVER_HOST=0.0.0.0`
   - `SERVER_PORT=8000`

4. Start the backend:
   ```bash
   python main.py
   ```

The API should be available at `http://localhost:8000` on the host machine.

## Web frontend setup

1. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

2. Create `frontend/.env` from `frontend/.env.example`.

3. Start the web frontend:
   ```bash
   npm start
   ```

## Native iPhone app setup with Expo

1. From the repository root, install root dependencies:

   ```bash
   npm install
   ```

2. Start the Expo development server:

   ```bash
   npm run mobile:start:tunnel
   ```

   If your local network works reliably, you can also use:

   ```bash
   npm run mobile:start
   ```

3. Open Expo Go on your iPhone.

4. Scan the QR code shown by Expo.

5. In the mobile login screen, set the API server URL to a backend address reachable from your iPhone. Use your computer's LAN IP, for example:

   ```text
   http://192.168.1.25:8000
   ```

   Do not use `http://localhost:8000` on the phone unless the backend is running on the phone itself.

6. Tap `Test connection` in the app.

7. Sign in with an existing backend user account.

## iPhone launch notes

- Your iPhone must be able to reach the machine running the backend.
- `SERVER_HOST=0.0.0.0` allows the backend to listen on the local network.
- If the QR code connection is blocked by the network, use `npm run mobile:start:tunnel`.
- The mobile app stores the selected API URL and session locally on the device.

## Useful commands

From the repository root:

```bash
npm run mobile:start
npm run mobile:start:tunnel
npm run mobile:ios
npm run backend
npm run frontend
npm run build
npm run lint
```

## Additional documentation

- `SETUP_GUIDE.md` detailed setup steps
- `LAUNCH_CHECKLIST.md` launch verification checklist
- `PROJECT_INFO.md` product and architecture summary
