# Woodful Creations - Launch Checklist

Use this checklist to verify that your local development environment is correctly set up and ready to run.

---

## System Requirements

- [ ] Python 3.9 or higher: `python --version`
- [ ] Node.js 14 or higher: `node --version`
- [ ] PostgreSQL 12 or higher: `psql --version`
- [ ] 8 GB RAM minimum available
- [ ] 5 GB free disk space

---

## Database

- [ ] PostgreSQL service is running
- [ ] `woodful_creations` database exists: `psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='woodful_creations';"`
- [ ] `woodful_user` database user exists: `psql -U postgres -c "SELECT usename FROM pg_user WHERE usename='woodful_user';"`
- [ ] Database tables created: `psql -U woodful_user -d woodful_creations -c "\dt"`
- [ ] Master users created: `psql -U woodful_user -d woodful_creations -c "SELECT username, role FROM users;"`

---

## Backend

- [ ] Virtual environment created and activated (`(venv)` visible in prompt)
- [ ] Dependencies installed: `pip list | grep fastapi`
- [ ] `backend/.env` file present and configured (DATABASE_URL, SECRET_KEY, etc.)
- [ ] Backend starts without errors: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- [ ] Health check responds: `curl http://localhost:8000/api/health`
- [ ] Swagger UI accessible: http://localhost:8000/docs

---

## Frontend

- [ ] Node dependencies installed: `npm list react`
- [ ] `frontend/.env` file present with `REACT_APP_API_URL=http://localhost:8000`
- [ ] Development server starts: `npm start`
- [ ] Application loads in browser: http://localhost:3000
- [ ] No critical errors in browser console (DevTools F12)

---

## Login Verification

- [ ] Login page is visible at http://localhost:3000
- [ ] Master admin login succeeds (username: `garimas` or `nikhils`, use the password set during user creation)
- [ ] Full admin dashboard and all modules accessible after login
- [ ] Regular user login succeeds (username: `shwetav`)
- [ ] Regular user sees only permitted modules (no payment management, no user management)
- [ ] Logout clears the session and redirects to login page
- [ ] Invalid credentials show an error and do not allow access

---

## API Verification

- [ ] POST /api/auth/login returns a token for valid credentials
- [ ] GET /api/auth/me returns current user data with a valid token
- [ ] GET /api/users returns all users for master admin, 403 for regular user
- [ ] GET /api/health returns 200 OK

---

## Troubleshooting Reference

| Issue | Quick Fix |
|-------|-----------|
| PostgreSQL connection error | Verify service is running and DATABASE_URL in `.env` is correct |
| Backend port 8000 in use | Use `--port 8001` and update `REACT_APP_API_URL` in frontend `.env` |
| Frontend port 3000 in use | React will prompt to use an alternative port |
| Login fails | Confirm users were created with `SELECT username, role FROM users;` |
| Module not found | Ensure virtual environment is activated and `pip install -r requirements.txt` was run |

For detailed setup instructions, see SETUP_GUIDE.md.

---

## Final Sign-Off

- [ ] All services running without errors
- [ ] Login and logout verified for all user roles
- [ ] API endpoints responding correctly
- [ ] No sensitive data exposed in logs or browser console
- [ ] Ready to begin Phase 1 development

---

*Last Updated: June 2026*
