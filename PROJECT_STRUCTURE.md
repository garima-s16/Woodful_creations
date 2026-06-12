# PROJECT STRUCTURE & ARCHITECTURE

## Directory Tree

```
Woodul_creations/
├── README.md
├── DOCUMENTATION.md          # Main documentation (4 MD files total)
├── SETUP_QUICK.md            # Quick setup
├── API_REFERENCE.md          # API documentation
├── PROJECT_STRUCTURE.md      # This file
│
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── requirements.txt      # Python dependencies
│   ├── .env                  # Environment variables
│   ├── .env.example          # Environment template
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app initialization
│   │   ├── config.py         # Configuration settings
│   │   ├── database.py       # Database connection & session
│   │   ├── schemas.py        # Pydantic models (request/response)
│   │   │
│   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py       # User & authentication models
│   │   │   ├── inventory.py  # Product, stock, alerts
│   │   │   ├── chat.py       # Chat messages
│   │   │   ├── client.py     # Client management
│   │   │   ├── estimate.py   # Cost estimates
│   │   │   ├── attendance.py # Employee attendance & salary
│   │   │   ├── interview.py  # Interview tracking
│   │   │   └── payment.py    # Payment tracking
│   │   │
│   │   ├── routes/           # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── auth.py       # Login, register, profile
│   │   │   ├── inventory.py  # Stock management
│   │   │   ├── chat.py       # AI chat
│   │   │   ├── clients.py    # Client management
│   │   │   ├── estimates.py  # Cost estimates
│   │   │   ├── attendance.py # Employee attendance
│   │   │   ├── interviews.py # Interview tracking
│   │   │   └── payments.py   # Payment management
│   │   │
│   │   ├── services/         # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── ai_chat.py    # AI message processing
│   │   │   ├── email.py      # Email service
│   │   │   ├── pdf.py        # PDF generation
│   │   │   ├── excel.py      # Excel export
│   │   │   ├── auth.py       # Authentication logic
│   │   │   └── alerts.py     # Notification system
│   │
│   └── scripts/              # Setup scripts
│       ├── init_db.py        # Database initialization
│       └── create_master_user.py
│
├── frontend/
│   ├── index.html            # HTML template
│   ├── package.json          # NPM dependencies
│   ├── .env.example          # Environment template
│   │
│   ├── public/               # Static assets
│   │   ├── assets/
│   │   │   └── logo/         # Woodful logo files
│   │   └── favicon.ico
│   │
│   └── src/
│       ├── index.jsx         # React entry point
│       ├── App.jsx           # Main app component
│       │
│       ├── pages/            # Page components
│       │   ├── LoginPage.jsx
│       │   ├── DashboardPage.jsx
│       │   ├── StockInventoryPage.jsx
│       │   ├── AIChatPage.jsx
│       │   ├── ClientsPage.jsx
│       │   ├── EstimatesPage.jsx
│       │   ├── AttendancePage.jsx
│       │   ├── InterviewsPage.jsx
│       │   ├── PaymentsPage.jsx
│       │   └── AnalyticsPage.jsx
│       │
│       ├── components/       # Reusable components
│       │   ├── Navbar.jsx
│       │   ├── Sidebar.jsx
│       │   ├── ProtectedRoute.jsx
│       │   │
│       │   ├── StockInventory/
│       │   │   ├── StockTable.jsx
│       │   │   ├── AddProductModal.jsx
│       │   │   ├── StockFilters.jsx
│       │   │   └── LowStockAlert.jsx
│       │   │
│       │   ├── AIChat/
│       │   │   ├── ChatMessageList.jsx
│       │   │   ├── ChatInputBox.jsx
│       │   │   └── ChatSuggestions.jsx
│       │   │
│       │   ├── Clients/
│       │   ├── Estimates/
│       │   ├── Attendance/
│       │   ├── Interviews/
│       │   ├── Payments/
│       │   └── Analytics/
│       │
│       ├── redux/            # State management
│       │   ├── store.js
│       │   └── slices/
│       │       ├── authSlice.js
│       │       ├── inventorySlice.js
│       │       ├── chatSlice.js
│       │       ├── clientSlice.js
│       │       ├── estimateSlice.js
│       │       ├── attendanceSlice.js
│       │       └── analyticsSlice.js
│       │
│       ├── services/         # API services
│       │   ├── api.js        # Axios configuration
│       │   ├── authService.js
│       │   ├── inventoryService.js
│       │   ├── chatService.js
│       │   ├── clientService.js
│       │   ├── estimateService.js
│       │   └── attendanceService.js
│       │
│       └── styles/           # CSS files
│           ├── index.css
│           ├── App.css
│           ├── LoginPage.css
│           ├── Dashboard.css
│           ├── StockInventory.css
│           ├── AIChat.css
│           └── components/   # Component styles
│               ├── Navbar.css
│               ├── Sidebar.css
│               ├── StockInventory/
│               │   ├── StockTable.css
│               │   ├── AddProductModal.css
│               │   ├── StockFilters.css
│               │   └── LowStockAlert.css
│               └── AIChat/
│                   ├── ChatMessageList.css
│                   ├── ChatInputBox.css
│                   └── ChatSuggestions.css
│
├── database/
│   ├── schema.sql           # PostgreSQL schema
│   └── migrations/          # Database migrations (Alembic)
│
└── scripts/                 # Setup scripts
    ├── setup.sh
    └── setup.bat
```

## Module Architecture

### Stock Inventory (Active)
```
User → Frontend (StockInventoryPage)
     → Redux (inventorySlice)
     → API Service (inventoryService)
     → Backend Route (inventory.py)
     → Business Logic (service layer)
     → Database (Product, StockMovement models)
```

### AI Chat (Active)
```
User → Frontend (AIChatPage)
     → Redux (chatSlice)
     → API Service (chatService)
     → Backend Route (chat.py)
     → AI Service (ai_chat.py - LangChain)
     → Database (ChatMessage model)
```

### Future Modules Pattern
Each module follows the same architecture:
- Page Component
- Redux Slice for state
- API Service
- Backend Route
- Database Models
- Business Logic

## Database Schema

### Users Table
- Authentication & role management
- Master/Regular user distinction

### Products Table
- Inventory items
- Stock levels
- Pricing information

### Stock Tables
- Movements (history)
- Alerts (low stock notifications)

### Chat Table
- Message history
- AI responses
- Context metadata

### Future Tables (Pre-designed)
- Clients & Client Products
- Cost Estimates
- Employees & Attendance
- Salary & Payroll
- Interviews & Candidates
- Payments & Transactions

## API Layer Structure

### Request Flow
```
Client Request
     ↓
Router (route decorator)
     ↓
Dependency Injection (auth, db session)
     ↓
Request Validation (Pydantic schema)
     ↓
Business Logic (service layer)
     ↓
Database Operation (ORM)
     ↓
Response Schema (Pydantic model)
     ↓
Client Response
```

## State Management (Redux)

### Slices (one per feature)
- authSlice: User & authentication state
- inventorySlice: Products, filters, search
- chatSlice: Messages, loading state
- Additional slices for each module

### Actions
- Load data from API
- Update local state
- Handle errors
- Reset state

## Development Workflow

1. **Create Database Model** (backend/app/models/)
2. **Create Request/Response Schemas** (backend/app/schemas.py)
3. **Create API Route** (backend/app/routes/)
4. **Create Redux Slice** (frontend/src/redux/slices/)
5. **Create API Service** (frontend/src/services/)
6. **Create UI Components** (frontend/src/components/)
7. **Create Page Component** (frontend/src/pages/)
8. **Add Styling** (frontend/src/styles/)

## File Naming Conventions

- Components: PascalCase (LoginPage.jsx)
- Utilities: camelCase (authService.js)
- Styles: match component name (LoginPage.css)
- Models: camelCase (user.py)
- Routes: camelCase (auth.py)

## Code Organization Principles

1. **Separation of Concerns**: Each file has single responsibility
2. **DRY**: Don't repeat code - use utilities & components
3. **KISS**: Keep it simple
4. **Scalability**: Add new features without modifying existing code
5. **Maintainability**: Clear naming & documentation

## Security Layers

1. **Frontend**: Route protection, JWT token handling
2. **API**: Request validation, authentication checks
3. **Database**: ORM prevents SQL injection, soft deletes
4. **Transport**: CORS, HTTPS ready
