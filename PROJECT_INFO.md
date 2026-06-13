# Woodful Creations - Project Information

## Overview

**Woodful Creations** is a comprehensive AI-powered business management system designed specifically for woodcraft and furniture design businesses. It provides an integrated platform for managing inventory, estimating costs, tracking employees, managing clients, and generating business documents.

---

## Project Details

### Project Name
Woodful Creations - AI-Powered Management System

### Current Version
2.0.0

### Status
Foundation Complete, Ready for Feature Implementation

### Last Updated
June 2026

---

## Technology Stack

### Frontend
- **Framework**: React 18.2.0
- **Routing**: React Router DOM 6
- **State Management**: Redux & Redux Toolkit
- **HTTP Client**: Axios
- **Mobile/Desktop**: React Native (prepared)

### Backend
- **Framework**: FastAPI 0.104.1
- **Server**: Uvicorn ASGI
- **ORM**: SQLAlchemy 2.0
- **Validation**: Pydantic
- **Authentication**: JWT + Bcrypt

### Database
- **Primary Database**: PostgreSQL 12+
- **Driver**: psycopg2

### Desktop Application
- **Framework**: PyQt5 (prepared for implementation)

### Additional Technologies
- **File Generation**: ReportLab (PDF), python-docx (Word), openpyxl (Excel)
- **AI Integration**: OpenAI API, LangChain
- **Email**: SMTP (Gmail, custom), SendGrid
- **DevOps**: Docker, Docker Compose

---

## Core Features

### 1. **Stock Inventory Management**
   - Real-time inventory tracking
   - AI-powered low stock alerts
   - Automated reorder suggestions
   - Stock movement history

### 2. **Cost Estimation**
   - Material cost calculator
   - Labor cost estimation
   - Project-based pricing
   - PDF estimate generation
   - Client estimate delivery

### 3. **Employee Management**
   - Attendance tracking
   - Salary management
   - Role-based access control
   - Performance metrics

### 4. **Interview Tracking**
   - Candidate management
   - Interview scheduling
   - Feedback documentation
   - Hiring pipeline

### 5. **Client Management**
   - Client database
   - Project tracking
   - Communication history
   - Relationship management

### 6. **Payment Management**
   - Payment tracking
   - Invoice generation
   - Payment status monitoring
   - Financial reporting

### 7. **AI Chat Assistant**
   - Natural language queries
   - Business insights
   - Data-driven recommendations
   - Real-time assistance

### 8. **Analytics Dashboard**
   - Business metrics
   - Revenue tracking
   - Inventory analytics
   - Performance insights

### 9. **Document Generation**
   - PDF reports
   - Excel exports
   - Word documents
   - Custom templates

### 10. **Multi-Level Access Control**
   - Role-based permissions
   - Master users (Nikhil & Garima)
   - Department-level access
   - Activity logging

---

## System Requirements

### Hardware Requirements
- **Operating System**: Windows 10/11, macOS, or Linux
- **RAM**: Minimum 8GB (16GB recommended)
- **Storage**: Minimum 5GB free space
- **Processor**: Dual-core processor (2.4 GHz or higher recommended)
- **Internet**: Required for initial setup and email features

### Software Requirements
- **Python**: Version 3.9 to 3.14+ (recommended: 3.10+)
- **Node.js**: Version 14 or higher (LTS versions recommended)
- **PostgreSQL**: Version 12 or higher
- **Git**: For version control
- **npm or yarn**: For package management

---

## Project Structure

```
Woodful_creations/
├── backend/                          # FastAPI backend
│   ├── app/
│   │   ├── core/                    # Core configuration
│   │   │   ├── config.py           # App configuration
│   │   │   ├── database.py         # Database setup
│   │   │   └── security.py         # Authentication
│   │   ├── api/
│   │   │   └── routes/             # API endpoints
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── services/               # Business logic
│   │   └── schemas/                # Pydantic schemas
│   ├── main.py                     # Application entry point
│   ├── requirements.txt            # Python dependencies
│   └── .env                        # Environment variables
│
├── frontend/                         # React frontend
│   ├── public/                      # Static assets
│   ├── src/
│   │   ├── components/             # Reusable components
│   │   ├── pages/                  # Page components
│   │   ├── services/               # API services
│   │   ├── redux/                  # State management
│   │   └── styles/                 # CSS styles
│   ├── package.json               # NPM dependencies
│   └── .env                        # Environment variables
│
├── database/                         # Database files
│   └── schema.sql                  # Database schema
│
├── scripts/                          # Utility scripts
│   ├── init_db.py                  # Database initialization
│   └── create_master_user.py       # Master user creation
│
├── docker-compose.yml              # Docker configuration
├── setup.sh / setup.bat            # Setup scripts
└── start_all.sh / start_all.bat    # Start all services
```

---

## Installation Overview

For detailed setup instructions with Python 3.14 compatibility, please refer to **SETUP_GUIDE.md**.

### Quick Steps
1. Clone the repository
2. Set up PostgreSQL database
3. Configure backend (.env file)
4. Install backend dependencies (Python 3.14 compatible)
5. Configure frontend (.env file)
6. Install frontend dependencies
7. Run database migrations
8. Start the application

---

## Accessing the Application

### Web Interface
- **URL**: http://localhost:3000
- **Default Master Users**: Nikhil, Garima

### Backend API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Port**: 8000

### Desktop Application
- Launch directly from the PyQt5 application terminal

---

## Master Users

The following users have administrative access:
- **Nikhil** - Master Administrator
- **Garima** - Master Administrator

These users have full access to all system features and can manage other users' permissions.

---

## Development Roadmap

### Completed
- ✅ Project foundation and structure
- ✅ Backend infrastructure (FastAPI setup)
- ✅ Frontend infrastructure (React setup)
- ✅ Database configuration
- ✅ Docker setup

### In Progress
- 🔄 Stock Inventory Module (Priority 1)
- 🔄 AI Chat Integration (Priority 2)
- 🔄 Authentication System (Priority 3)

### Planned
- 📋 Cost Estimation Module
- 📋 Employee Management
- 📋 Client Management
- 📋 Payment Tracking
- 📋 Analytics Dashboard
- 📋 Desktop Application (PyQt5)
- 📋 Production Deployment

---

## Support & Documentation

### Key Documents
1. **SETUP_GUIDE.md** - Detailed installation and configuration
2. **API_REFERENCE.md** - Backend API documentation
3. **PROJECT_REQUIREMENTS.md** - Complete feature specifications

### Getting Help
- Check the relevant module documentation
- Review FastAPI docs at http://localhost:8000/docs
- Contact the development team (Nikhil & Garima)

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 2.0.0 | June 2026 | Foundation complete, Python 3.14 compatible |
| 1.0.0 | June 2026 | Initial setup and structure |

---

## License

Private Project - Woodful Creations

---

*Last Updated: June 2026*
