Woodful Creations - AI-Powered Management System

Welcome to Woodful Creations, a comprehensive business management system designed for woodcraft and furniture design businesses.

Quick Start

1. Clone Repository

   git clone https://github.com/garima-s16/Woodful_creations.git
   cd Woodful_creations

2. Set Up PostgreSQL

   Follow the setup guide to create the database:
   - Database: woodful_creations
   - User: woodful_user

3. Backend Setup

   cd backend
   python -m venv venv

   Windows:
     venv\Scripts\activate

   macOS/Linux:
     source venv/bin/activate

   pip install -r requirements.txt

   Copy .env.example to .env and configure:
     cp .env.example .env

4. Frontend Setup

   cd frontend
   npm install
   cp .env.example .env

5. Run Applications

   Terminal 1 - Backend:
     cd backend
     source venv/bin/activate
     python main.py

   Terminal 2 - Frontend:
     cd frontend
     npm start

   Access the application:
   - Web: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

Docker Deployment

   docker-compose up

System Requirements

- Python 3.9+
- Node.js 14+
- PostgreSQL 12+
- 8GB RAM minimum

Default Admin Users

No accounts ship with this repository. Create your own via
`backend/scripts/create_master_user.py` (see SETUP_GUIDE.md). Placeholders
below are examples only — real credentials were previously committed here
and have been removed; see the security note in SETUP_GUIDE.md.

- Username: <your-choice> / Password: <CHANGE_ME_ADMIN2_PASSWORD>
- Username: <your-choice> / Password: <CHANGE_ME_ADMIN1_PASSWORD>

Features

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

PWA and Mobile / Desktop Install (new)

This project now includes Progressive Web App (PWA) support so the frontend can be installed on iOS (as an "Add to Home Screen" web app), Android, and desktop browsers that support PWAs. The changes are intentionally minimal and avoid new dependencies.

What was changed

- frontend/public/index.html: added PWA meta tags and manifest link; updated viewport and theme-color.
- frontend/src/index.js: registers a service worker on window load.
- frontend/src/App.css: added safe-area (iOS notch) CSS variables and mobile tap-target improvements.
- frontend/public/service-worker.js: added a conservative service worker that caches the app shell and provides network fallback for API requests.

Files that should exist for full PWA behavior (manifest and icons)

- frontend/public/manifest.json: controls install behavior and references icons (icon-192.png and icon-512.png).
- frontend/public/icons/icon-192.png
- frontend/public/icons/icon-512.png
- frontend/public/icons/apple-touch-icon.png

If these manifest and icon files are not present in your local copy, create them as shown in the project notes or add your own images at the locations above. Placeholder icons may be used temporarily but should be replaced with proper artwork for production.

How the service worker works (summary)

- install: caches the application root (index.html) to provide a basic offline shell.
- fetch: uses a network-first strategy for API (/api/) requests and a cache-first approach for other GET requests. The service worker is conservative to avoid brittle precaching of hashed build assets. For a full precache, migrate to a Workbox-based setup.

Testing the PWA locally

1. Development server (fast feedback)

   cd frontend
   npm install
   npm start

   Development servers may not always register service workers due to dev tooling. To test PWA behavior, build the production bundle and serve it.

2. Production build (recommended for testing service worker and installability)

   cd frontend
   npm run build
   npx serve -s build

   Open the served URL in Chrome/Edge/Firefox or Safari and check DevTools > Application to confirm the manifest and service worker are active. On Android Chrome you should see an install prompt; on iOS open the site in Safari and use "Add to Home Screen".

Notes and recommendations

- No new npm packages were added; the frontend remains a Create React App (react-scripts) project.
- The service worker added here is intentionally simple. If you need robust offline behavior and accurate precaching of built assets, consider using Workbox or CRA's service worker generation during build.
- To produce native desktop applications (Windows/macOS) instead of a web-installed PWA, consider adding an Electron or Tauri wrapper. This is outside the scope of the present changes and would add build tooling.
- Replace placeholder icons with final artwork in frontend/public/icons/ to improve user experience when the app is installed.

Support

For detailed setup instructions, see SETUP_GUIDE.md
For project details, see PROJECT_INFO.md

License

Private Project - Woodful Creations
