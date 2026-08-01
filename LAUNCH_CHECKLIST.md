# Woodful Creations Launch Checklist

## Backend

- [ ] PostgreSQL is running
- [ ] `backend/.env` exists and contains a valid `DATABASE_URL`
- [ ] `backend/.env` contains a non-placeholder `SECRET_KEY`
- [ ] `SERVER_HOST` is set to `0.0.0.0` for device access
- [ ] Backend dependencies are installed
- [ ] `python main.py` starts successfully
- [ ] `http://localhost:8000/api/health` returns a healthy response

## Web frontend

- [ ] `frontend/.env` exists
- [ ] Frontend dependencies are installed
- [ ] `npm start` in `frontend/` launches the web app

## Native iPhone app

- [ ] Root dependencies are installed with `npm install`
- [ ] Expo starts with `npm run mobile:start` or `npm run mobile:start:tunnel`
- [ ] Expo Go is installed on the iPhone
- [ ] The iPhone can open the Expo project from the QR code
- [ ] The mobile login screen is using a reachable backend URL, not `localhost`
- [ ] `Test connection` succeeds inside the app
- [ ] Login succeeds on the iPhone
- [ ] Dashboard opens after login
- [ ] Inventory, Clients, Payments, Chat, and More tabs load on the iPhone

## Final verification

- [ ] Mobile session persists after app reload
- [ ] Inventory add flow works
- [ ] Client add flow works
- [ ] Chat messages receive backend responses
- [ ] Sensitive values are not documented in the repository
