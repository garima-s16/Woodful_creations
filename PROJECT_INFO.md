# Woodful Creations Project Information

## Overview

Woodful Creations is a role-based business management system for woodcraft and furniture operations.

Current application surfaces:

- FastAPI backend
- React web frontend
- Expo/React Native iPhone app

## Functional areas

- Authentication
- Dashboard and operational summary
- Inventory management
- Client management
- Estimates
- Payments
- Attendance
- Interviews
- Analytics
- AI chat assistance

## Architecture summary

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT-based authentication

### Web frontend

- React
- React Router
- Axios

### Native mobile app

- Expo
- React Native
- AsyncStorage for local session persistence
- Shared backend API compatibility with the existing service routes

## Mobile app scope

The native mobile app focuses on daily operational workflows on iPhone:

- sign in
- dashboard overview
- inventory list and add flow
- client list and add flow
- payment workspace
- AI chat
- overview access to estimates, attendance, interviews, and analytics

## Security and configuration

The repository documentation does not include live credentials or secret values.
Use local environment files for:

- database connection strings
- JWT secret keys
- SMTP credentials
- API keys

## Launch references

- `README.md`
- `SETUP_GUIDE.md`
- `LAUNCH_CHECKLIST.md`
