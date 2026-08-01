# Woodful Creations - Project Information

## Overview

**Woodful Creations** is a comprehensive AI-powered business management system designed specifically for woodcraft and furniture design businesses. It provides an integrated platform for managing inventory, clients, employees, costs, payments, and more with role-based access control and advanced analytics.

---

## Project Details

### Project Name
Woodful Creations - AI-Powered Management System

### Current Version
2.0.0

### Status
Foundation Complete, Ready for Local Environment Launch

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
- **Build Tool**: Create React App

### Backend
- **Framework**: FastAPI 0.104.1
- **Server**: Uvicorn ASGI
- **ORM**: SQLAlchemy 2.0
- **Validation**: Pydantic
- **Authentication**: JWT + Bcrypt + OTP
- **Python Version**: 3.9 to 3.14 (Recommended: 3.14)

### Database
- **Primary Database**: PostgreSQL 12+
- **Driver**: psycopg2
- **Caching**: Redis 7
- **Query Language**: SQL

### Desktop Application
- **Framework**: PyQt5 5.15.9 (prepared for implementation)

### Additional Technologies
- **File Generation**: ReportLab (PDF), python-docx (Word), openpyxl (Excel)
- **AI Integration**: OpenAI API, LangChain 0.1.0
- **Email**: SMTP (Gmail, custom), SendGrid
- **DevOps**: Docker, Docker Compose
- **Authentication**: python-jose, passlib with bcrypt
- **Async Support**: aiofiles, asyncio

---

## Core Features & Modules

### 1. Stock Inventory Management (Priority 1)
Real-time inventory tracking with AI-powered alerts
- Product management and categorization
- Real-time stock level monitoring
- Low stock alerts (configurable thresholds)
- Automated reorder suggestions
- Stock movement history and analytics
- Batch operations for bulk updates
- Search and filter capabilities

### 2. Cost Estimation (Priority 2)
Material and labor cost calculation with beautiful PDF delivery
- Material cost calculator with predefined components
- Labor cost estimation based on hours/rates
- Project-based pricing templates
- Cost breakdown by product/category
- PDF estimate generation with:
  - High-quality product images
  - Itemized cost details
  - Client information
  - Tax calculations
  - Payment terms and conditions
- Email delivery of estimates
- Estimate templates and history
- Version control for estimates

### 3. Client Management (Priority 3)
Comprehensive client database with project tracking
- Client profile and contact details
- Complete product order history
- Multi-status tracking per product:
  - Design status
  - Execution status
  - Delivery status
- Payment tracking (received and pending)
- Design approval workflow
- Change request management
- ETA for each product delivery
- Communication history per client
- Client-specific analytics

### 4. Employee Management (Priority 4)
Attendance and salary management as per Indian law
- Employee database and roles
- Real-time attendance tracking
- Monthly attendance reports
- Salary calculation engine (India-compliant):
  - Basic + DA + HRA calculations
  - Deductions (PF, TDS, etc.)
  - Overtime calculations
- Digital salary slip generation (PDF)
- Leave management (PL, CL, SL)
- Performance metrics tracking
- Employee role and permission assignment

### 5. Interview Management (Priority 5)
Recruitment pipeline and candidate tracking
- Candidate database
- Interview scheduling and reminders
- Interview feedback documentation
- Candidate status tracking (Applied, Shortlisted, Selected, Rejected)
- Hiring pipeline visualization
- Interview round tracking
- Candidate ranking and notes

### 6. Payment Management (Priority 6)
Financial tracking (Nikhil & Garima only)
- Client payment tracking
- Invoice generation
- Payment status monitoring:
  - Pending
  - Partially paid
  - Fully paid
  - Overdue
- Financial reporting and analytics
- Payment reminder system
- Late payment alerts
- Payment reconciliation
- Multi-currency support (if needed)

### 7. AI Chat Assistant
Natural language business intelligence
- Natural language query processing
- Business insights generation
- Data-driven recommendations
- Context-aware responses
- Multi-turn conversation support
- Query history and export
- Smart suggestions based on data

### 8. Analytics Dashboard
Comprehensive business metrics
- Business metrics overview (real-time KPIs)
- Revenue tracking and trends
- Inventory analytics and forecasting
- Performance insights by department
- Custom report builder
- Data visualization (charts, graphs)
- Excel/PDF export functionality
- Departmental-level analytics

### 9. Document Generation & File Management
Multi-format document export
- PDF reports with custom formatting
- Excel workbook generation
- Word document creation
- Custom template system
- Batch document generation
- Email document delivery
- Document storage and versioning

### 10. Multi-Level Access Control
Role-based permission system
- Master users (Nikhil & Garima): Full access to all features and data
- Regular users: Limited access based on role
- Department-level access controls
- View-only vs. edit permissions
- Activity logging and audit trail
- Permission management interface

---

## User Roles & Permissions

### Master Administrators (2 users)
**Users**: Nikhil (nikhils) & Garima (garimas)
- Full access to all modules and features
- Can view and update all data across all departments
- Can add/remove regular users
- Can modify permissions
- Can access payment management (sensitive data)
- Cannot be deleted from system
- Full access to analytics and reports

### Regular Users
**Users**: shwetav (Stock team member)
- Limited data access based on department
- Can view stock inventory
- Can update product status (design/execution/delivery)
- Can view only assigned client information
- Cannot access payment management
- Cannot modify user permissions
- Cannot see other users' data outside their scope

### User Credentials

| Role | Username | Password | Email | Access Level |
|------|----------|----------|-------|--------------|
| Master Admin | garimas | \<password\> | garima@woodfulcreations.com | Full |
| Master Admin | nikhils | \<password\> | nikhil@woodfulcreations.com | Full |
| Regular User | shwetav | \<password\> | shweta@woodfulcreations.com | Limited |

---

## System Requirements

### Hardware Requirements
- **Operating System**: Windows 10/11, macOS, or Linux
- **RAM**: Minimum 8GB (16GB recommended for production)
- **Storage**: Minimum 5GB free space
- **Processor**: Dual-core processor (2.4 GHz or higher)
- **Internet**: Required for initial setup, email features, and AI services

### Software Requirements
- **Python**: Version 3.9 to 3.14 (Recommended: 3.14)
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
│   │   │   └── security.py         # Authentication & JWT
│   │   ├── api/
│   │   │   └── routes/             # API endpoints by module
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── services/               # Business logic layer
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   └── utils/                  # Helper functions
│   ├── main.py                     # Application entry point
│   ├── requirements.txt            # Python dependencies
│   ├── .env                        # Environment variables
│   ├── Dockerfile                  # Docker configuration
│   └── logs/                       # Application logs
│
├── frontend/                         # React frontend
│   ├── public/                      # Static assets & Woodful logo
│   ├── src/
│   │   ├── components/             # Reusable UI components
│   │   ├── pages/                  # Page components for each module
│   │   ├── services/               # API client services
│   │   ├── redux/                  # State management
│   │   ├── styles/                 # CSS modules (no emojis)
│   │   ├── utils/                  # Helper functions
│   │   └── App.js                  # Root component
│   ├── package.json               # NPM dependencies
│   ├── .env                        # Environment variables
│   ├── Dockerfile                  # Docker configuration
│   └── .gitignore
│
├── database/                         # Database files
│   └── schema.sql                  # Complete database schema
│
├── scripts/                          # Utility scripts
│   ├── init_db.py                  # Database initialization
│   ├── create_master_user.py       # Master user creation script
│   └── create_regular_user.py      # Regular user creation script
│
├── docker-compose.yml              # Multi-container orchestration
├── setup.sh / setup.bat            # Setup scripts (OS-specific)
├── start_all.sh / start_all.bat    # Start all services (OS-specific)
├── .gitignore                      # Git ignore file
├── README.md                       # Quick start guide
├── PROJECT_INFO.md                 # This file - Project overview
├── SETUP_GUIDE.md                  # Detailed setup instructions
└── LAUNCH_CHECKLIST.md             # Local launch verification steps
```

---

## Installation Overview

For full installation and configuration steps, refer to **SETUP_GUIDE.md**.

### Quick Start

1. Clone the repository and navigate to the project root.
2. Set up PostgreSQL with a `woodful_creations` database and a dedicated user.
3. Configure backend and frontend `.env` files from the provided `.env.example` templates.
4. Initialize the database schema and create master users using the scripts in `scripts/`.
5. Start the backend (`uvicorn`) and frontend (`npm start`) servers.
6. Access the application at http://localhost:3000.

---

## Accessing the Application

### Web Interface
- **URL**: http://localhost:3000
- **Default Master Users**: Nikhil (nikhils), Garima (garimas)
- **Responsive**: Desktop and mobile compatible

### Backend API
- **Base URL**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

### Desktop Application (Future)
- Launch directly from PyQt5 application

### Database
- **Host**: localhost
- **Port**: 5432
- **Database**: woodful_creations
- **User**: woodful_user

---

## Development Roadmap

### Phase 1: Foundation & Local Launch (Current)
- Database schema for all modules
- Core authentication system (JWT + OTP)
- Login interface and dashboard
- Role-based access control
- Master users setup
- Estimated Timeline: 2-3 weeks

### Phase 2: Stock Inventory Module (Priority 1)
- Real-time inventory tracking
- Product management
- Low stock alerts with email notifications
- Inventory reports
- Estimated Timeline: 3-4 weeks

### Phase 3: Cost Estimation Module (Priority 2)
- Material and labor cost calculator
- PDF estimate generation with product images
- Email delivery system
- Estimated Timeline: 3 weeks

### Phase 4: Client Management
- Client profiles with complete project history
- Multi-status tracking per product
- Payment tracking per client
- Communication timeline
- Estimated Timeline: 3 weeks

### Phase 5: Employee Management
- Attendance tracking
- Salary calculation (India-compliant)
- Salary slip generation
- Estimated Timeline: 3 weeks

### Phase 6: Interview Management
- Candidate database
- Interview scheduling
- Status tracking
- Estimated Timeline: 2 weeks

### Phase 7: Payment Management
- Payment tracking for clients
- Invoice generation
- Financial analytics (Nikhil & Garima only)
- Estimated Timeline: 2 weeks

### Phase 8: AI Chat Assistant
- Natural language query processing
- Business insights generation
- Estimated Timeline: 2 weeks

### Phase 9: Analytics Dashboard
- Real-time KPIs
- Revenue tracking
- Inventory analytics
- Estimated Timeline: 2 weeks

### Phase 10: Document Generation
- PDF, Excel, Word export
- Batch generation
- Email delivery
- Estimated Timeline: 2 weeks

### Phase 11: Notification System
- Low stock alerts
- ETA approaching alerts
- Payment due alerts
- Email and SMS notifications
- Estimated Timeline: 2 weeks

### Phase 12: Desktop Application (PyQt5)
- Feature parity with web version
- Offline mode support
- Sync mechanism
- Estimated Timeline: 3-4 weeks

### Phase 13: Testing & QA
- Unit testing
- Integration testing
- End-to-end testing
- User acceptance testing
- Estimated Timeline: 2-3 weeks

### Phase 14: Production Deployment
- Docker deployment
- CI/CD pipeline setup
- Monitoring and logging
- Estimated Timeline: 2 weeks

---

## Support & Documentation

### Key Documents
1. **SETUP_GUIDE.md** - Detailed installation and configuration with Python 3.14 support
2. **LAUNCH_CHECKLIST.md** - Step-by-step verification for local environment launch
3. **API_REFERENCE.md** - Backend API documentation (in development)
4. **PROJECT_REQUIREMENTS.md** - Detailed feature specifications (in development)

### Getting Help
- Check relevant module documentation
- Review FastAPI Swagger docs at http://localhost:8000/docs
- Contact the development team directly

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 2.0.0 | June 2026 | Foundation complete, Python 3.14 compatible, modules planned |
| 1.0.0 | June 2026 | Initial project structure and setup |

---

## Important Notes

- **No Data Redundancy**: All data stored in PostgreSQL as single source of truth
- **No Emojis**: All files and code follow professional standards without emojis
- **Python 3.14 Compatible**: All dependencies tested with Python 3.14
- **Local Launch Ready**: Follow SETUP_GUIDE.md and LAUNCH_CHECKLIST.md to launch

---

## License

Private Project - Woodful Creations

---

*Last Updated: June 2026*
*Maintained by: Woodful Creations Development Team*
