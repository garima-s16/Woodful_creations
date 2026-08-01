# Woodful Creations

Woodful Creations contains:

- a FastAPI backend in `backend/`
- a React web application in `frontend/`
- a prepared Expo-based iPhone app scaffold in `mobile/`

The current priority is the laptop web experience, so the repository is set up to let you preview the project in a browser first on Windows or macOS.

## Run the web app on your laptop

### 1. Start the backend

```bash
cd backend
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Then install and run:

```bash
pip install -r requirements.txt
python main.py
```

Backend URL: `http://localhost:8000`

### 2. Start the web frontend

Open a second terminal:

```bash
cd frontend
npm install
npm start
```

Web app URL: `http://localhost:3000`

## What the web app shows now

- a clean landing page for laptop viewing
- backend health status using `REACT_APP_API_URL`
- a quick overview of the main business areas
- a direct link to FastAPI docs at `http://localhost:8000/docs`

## Native iPhone app preparation

The repository also includes `mobile/`, a small Expo app scaffold for future native iPhone work.

To install and open it later:

```bash
cd mobile
npm install
npm start
```

Then open the project in Expo Go on your iPhone. For real-device testing, set `EXPO_PUBLIC_API_URL` to your computer's LAN IP instead of `localhost`.

## Environment files

- copy `frontend/.env.example` to `frontend/.env`
- copy `mobile/.env.example` to `mobile/.env` if you want to override the mobile API URL

Do not commit passwords, tokens, or private contact details into repository files.

## More documentation

- `SETUP_GUIDE.md`
- `PROJECT_INFO.md`
- `LAUNCH_CHECKLIST.md`

## License

Private project - Woodful Creations
