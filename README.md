# Woodful Creations - Stock Management (Web + iPhone)

This repository now provides a shared FastAPI backend with:
- **Web app** (browser usage on Windows/macOS)
- **Expo React Native mobile app** (iPhone-compatible)
- **Stock management workflow + downloadable Excel report**

## Implemented modules
- Dashboard
- Material Master (live stock master)
- Stock In / Purchase Register
- Stock Out / Material Issue Register
- Suppliers
- Settings

## Backend business logic
Current stock per material is calculated as:

`opening stock + total purchased - total issued`

Status rules:
- `OUT OF STOCK` when current stock `<= 0`
- `LOW STOCK` when current stock `> 0` and `<= minimum stock`
- `STOCK OK` otherwise

Dashboard includes:
- Total Stock Value
- Low Stock Items count
- Out of Stock count
- Purchase Value
- Dynamic category summary (item count, stock quantity, stock value)

## Excel download
Endpoint:

`GET /api/stock-management/reports/stock/download`

Workbook contains styled sheets:
- Dashboard
- Material Master
- Stock In - Purchases
- Stock Out - Issues
- Suppliers

## API endpoints (stock workflow)
Base: `/api/stock-management`

- `GET/POST /materials`
- `PUT/DELETE /materials/{material_id}`
- `GET/POST /stock-in`
- `GET/POST /stock-out`
- `GET/POST /suppliers`
- `GET/PUT /settings`
- `GET /dashboard`
- `GET /reports/stock/download`

## Environment variables
### Backend (`backend/.env`)
Copy `backend/.env.example` and edit if needed.

Key values:
- `DATABASE_URL` (default: `sqlite:///./woodful_creations.db`)
- `SERVER_HOST` (default: `0.0.0.0`)
- `SERVER_PORT` (default: `8000`)
- `ALLOWED_ORIGINS` (JSON list)

### Web (`frontend/.env`)
- `REACT_APP_API_URL=http://localhost:8000`

### Mobile (`mobile/.env`)
Copy `mobile/.env.example`:
- `EXPO_PUBLIC_API_URL=http://YOUR_LAN_IP:8000`

> For a physical iPhone, use your computer's LAN IP (not localhost).

## Setup (Windows/macOS)

### 1) Backend
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

### 2) Web app
```bash
cd frontend
npm install
cp .env.example .env
npm start
```
Open: `http://localhost:3000`

### 3) Mobile app (Expo, iPhone)
```bash
cd mobile
npm install
cp .env.example .env
npm start
```
Then:
- install **Expo Go** on iPhone
- scan QR from Expo terminal/browser
- ensure phone and backend machine are on same network

## How to use Excel download
1. Open Dashboard tab in web app (or mobile dashboard flow).
2. Click **Download Excel** (web) or **Open Excel Download** (mobile).
3. File downloads from backend report endpoint.

## Quick start from repo root
```bash
npm run install-all
npm run dev
# or run web+backend+mobile together
npm run dev:all
```
