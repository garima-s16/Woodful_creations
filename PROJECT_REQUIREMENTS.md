# WOODFUL CREATIONS - COMPLETE PROJECT REQUIREMENTS

## PROJECT OVERVIEW
**Application Name:** WOODFUL CREATIONS  
**Version:** 2.0  
**Type:** Multi-Module Business Management System  
**Platforms:** Desktop (React + PyQt5), Web (React), Mobile (React Native)  
**Database:** PostgreSQL  
**Backend:** FastAPI + Python  

---

## EXECUTIVE SUMMARY

WOODFUL CREATIONS is a comprehensive business management platform for wood and creative products with multiple integrated modules. It serves two categories of users:
- **Master Users (Nikhil & Garima)**: Full access to all data and features
- **Regular Users**: Limited access to specific sections (inventory, status updates)

---

## CORE MODULES (10 SECTIONS)

### 1. STOCK INVENTORY MANAGEMENT
**Purpose:** Manage product stock with AI features and alerts

**Features:**
- Real-time inventory tracking
- Add/Edit/Delete products with categories
- Stock quantity monitoring
- Minimum stock level alerts
- AI-powered stock forecasting
- Low stock notifications (email + push + SMS)
- Barcode/QR code scanning
- Bulk import/export (Excel, CSV)
- Stock history and audit logs
- Reorder recommendations
- Supplier management
- Batch/lot tracking
- Warehouse location mapping

**Data Points:**
- Product ID, SKU, Name, Category
- Quantity, Min Stock, Reorder Qty
- Unit Cost, Selling Price
- Supplier Info, Warehouse Location
- Stock Movement History
- Last Updated Timestamp

**User Permissions:**
- Master: Full CRUD, View All
- Regular: View Stock, Update Status, Request Reorder

**AI Features:**
- Demand prediction
- Smart reorder suggestions
- Anomaly detection
- Trend analysis

---

### 2. COST ESTIMATES & PDF GENERATION
**Purpose:** Create professional cost estimates and share with clients

**Features:**
- Template-based estimate creation
- Client selection with auto-fill
- Add products from inventory
- Dynamic cost calculation
- Discount/Tax handling
- Beautiful PDF generation with:
  - Product images
  - Item details & pricing
  - Client information
  - Company logo and branding
  - Terms & Conditions
  - Payment terms
- Email sharing with clients
- Version history and tracking
- Status tracking (Draft → Sent → Approved → Rejected)
- Client approval workflow
- Electronic signature support
- Currency/Language options

**PDF Components:**
- Header with Woodful logo
- Estimate number and date
- Client details
- Itemized product list with images
- Cost breakdown
- Payment terms
- Notes and terms
- Footer with company info

**User Permissions:**
- Master: Create, Edit, Delete, Send, View All
- Regular: Create Drafts, View Own Estimates

---

### 3. EMPLOYEE ATTENDANCE & SALARY MANAGEMENT
**Purpose:** Track attendance and generate salary slips compliant with Indian law

**Features:**
- Employee master database
- Daily attendance marking (Present/Absent/Leave/Half-day)
- Shift management
- Leave management (Casual, Sick, Earned, Unpaid)
- Overtime tracking
- Salary structure configuration:
  - Basic Salary
  - HRA, DA, Allowances
  - Deductions (PF, ESI, IT)
  - Incentives/Bonuses
- Monthly salary calculation
- Salary slip generation (PDF)
- Bank details management
- PF and ESI tracking
- Income Tax calculation (Indian norms)
- Compliance reports:
  - Monthly salary register
  - Attendance summary
  - PF/ESI deposits
- Payroll reports (Master, Detail, Summary)
- Payment history
- Advance salary tracking

**Salary Slip Features:**
- Employee details
- Month and year
- Attendance summary
- Earnings breakdown
- Deductions breakdown
- Net pay calculation
- Bank details
- Company stamp and signature

**Indian Law Compliance:**
- EPF calculation (12% employee + 12% employer)
- ESI eligibility and calculation
- Income Tax slab calculation
- Labor law wage codes
- Weekly off and holiday tracking
- Gratuity calculation (on exit)

**User Permissions:**
- Master: Full access, View all salaries, Process payroll
- HR User: Mark attendance, View team salaries
- Employee: View own attendance and salary slip

---

### 4. INTERVIEW TRACKING SYSTEM
**Purpose:** Track recruitment and interview progress

**Features:**
- Job posting management
- Candidate database
- Interview scheduling
- Interview types (Phone, Video, In-person)
- Interview panel assignment
- Scoring and feedback
- Status tracking:
  - Applied → Shortlisted → Interview → Offer → Joined → Rejected
- Interview feedback forms
- Offer letter generation
- Joining documents
- Background verification tracking
- Interview notes and recordings links
- Communication history with candidates
- Bulk candidate operations
- Reports and analytics

**Data Points:**
- Position, Candidate Name, Contact
- Interview Date, Time, Type, Panel
- Score, Feedback, Status
- Offer Details, Joining Date
- Rejection Reason (if applicable)

**User Permissions:**
- Master: Full access, View all interviews, Generate offers
- HR User: Schedule interviews, Take feedback, Update status
- Interview Panel: Provide feedback, Score candidates

---

### 5. CLIENT MANAGEMENT
**Purpose:** Comprehensive client profile and relationship management

**Features:**
- Client master database
- Client profile with:
  - Basic info (Name, Email, Phone, Address)
  - Company details
  - Contact person(s)
  - Payment terms
  - Credit limit
  - Preferred communication method

**Sub-sections for Each Client:**

**5.1 Products Requested**
- List of all products client has requested
- Request date and quantity
- Specifications and customization
- Priority level

**5.2 Product Status Tracking**
- Design Status (Not Started → In Progress → Completed → Approved)
- Execution Status (Pending → In Progress → Quality Check → Ready)
- Delivery Status (Not Shipped → In Transit → Delivered)
- Status update timeline with dates
- Current stage indicators

**5.3 Cost & Pricing**
- Estimate generated
- Final cost
- Quoted cost vs Actual cost
- Price breakdown

**5.4 Payments**
- Payments received (Amount, Date, Mode, Reference)
- Payments pending
- Payment history
- Invoice links
- Payment reminders
- Overdue payment alerts
- Payment terms and due dates

**5.5 Design Approvals**
- Design version tracking
- Approval status (Pending → Approved → Changes Requested)
- Approval date
- Approved by (client name)
- Design files (images/PDFs)
- Revision history

**5.6 Change Requests**
- List of changes requested by client
- Original vs Requested specifications
- Status of implementation
- Change request date
- Implementation deadline
- Approval on modified design

**5.7 Delivery ETA**
- Individual product ETAs
- Current status
- Days remaining
- Status indicators (On Track/At Risk/Delayed)
- Revision history (original vs updated)
- Estimated delivery date for complete order

**Additional Features:**
- Communication history (Emails, Calls, Meetings)
- Attachments and file storage
- Client notes
- Client classification (VIP, Regular, New)
- Performance metrics
- Repeat order tracking
- Satisfaction feedback

**User Permissions:**
- Master: Full access to all client data
- Regular Sales User: View own clients, Update limited fields
- Delivery Team: View delivery status only

---

### 6. PAYMENT TRACKING (ADMIN ONLY)
**Purpose:** Track payments owed by Woodful Creations

**Features:**
- Vendor/Supplier management
- Payment schedule
- Payments pending
- Payments made
- Payment history
- Invoices and bills
- Payment modes (Cash, Cheque, Bank Transfer, UPI)
- Payment proof attachments
- Maturity date tracking
- Reminders for upcoming payments
- Payment reports
- Compliance tracking (TDS, GST)

**User Permissions:**
- Master (Nikhil & Garima): Full access
- All others: No access

---

### 7. AI CHAT INTERFACE
**Purpose:** Natural language interaction for system management

**Features:**
- Chat interface with AI assistant
- Commands understanding:
  - "Show low stock items"
  - "Generate salary report"
  - "Track client orders"
  - "Add 50 units of [product]"
  - "Email salary slips to everyone"
  - "Schedule interview for [candidate]"
  - etc.
- Context-aware responses
- Multi-turn conversations
- Chat history
- Exportable chat transcripts
- File uploads in chat
- Scheduled chat reminders
- Integration with all modules

**AI Models:**
- OpenAI GPT for natural language processing
- Local models for privacy-sensitive operations
- Fine-tuned for Woodful-specific commands

---

### 8. ADVANCED ANALYTICS & REPORTING
**Purpose:** Business intelligence and data-driven insights

**Features:**

**8.1 Inventory Analytics**
- Stock turnover rates
- Slow-moving items
- Fast-moving items
- Revenue by category
- Inventory valuation
- Stock vs Sales correlation

**8.2 Client Analytics**
- Revenue by client
- Top clients (by value)
- Client acquisition trends
- Repeat order rate
- Average order value
- Client satisfaction metrics

**8.3 Payment Analytics**
- Revenue trends
- Outstanding receivables
- Payment delays
- Client payment reliability
- Cash flow projections

**8.4 Employee Analytics**
- Attendance trends
- Leave utilization
- Salary expenditure
- Productivity metrics
- Attendance patterns

**8.5 Operational Analytics**
- Production timelines
- On-time delivery rate
- Quality metrics
- Cost analysis

**Dashboards:**
- Executive dashboard (Key metrics overview)
- Sales dashboard
- Inventory dashboard
- HR dashboard
- Finance dashboard
- Operations dashboard

**Reports:**
- Monthly/Quarterly/Annual reports
- Customizable filters
- Comparative analysis
- Trend visualization
- Forecasting

---

### 9. FILE GENERATION & EXPORT
**Purpose:** Generate documents in multiple formats

**Features:**
- Excel Export:
  - Inventory lists
  - Salary registers
  - Attendance reports
  - Client lists
  - Payment history
  - Custom reports

- Word Export:
  - Estimates
  - Invoices
  - Reports
  - Letters (Job offer, Termination, etc.)
  - Salary certificates

- PDF Export:
  - All of above
  - Salary slips
  - Estimates
  - Invoices
  - Delivery notes
  - Receipt documents
  - Reports

- Features:
  - Batch generation
  - Email delivery
  - Scheduled generation
  - Template customization
  - Logo and branding
  - Multi-language support
  - Digital signatures

---

### 10. ALERT SYSTEM
**Purpose:** Proactive notifications for critical events

**Features:**

**Alert Types:**
- Low stock alerts
- ETA nearing (1 week before)
- Payment due alerts
- Overdue payment alerts
- Attendance alerts (absent employees)
- Interview reminders
- Salary processing reminders
- Client communication reminders

**Notification Channels:**
- Email notifications
- Mobile push notifications
- SMS notifications
- In-app notifications
- Desktop notifications (for PyQt5 app)

**Alert Configuration:**
- Master controls alert settings
- Recipient configuration
- Threshold settings
- Frequency control
- Snooze options
- Alert history

**Recipients:**
- Alert to Nikhil & Garima (configurable)
- Role-based alerts
- Specific user alerts
- Team alerts

---

## ROLE-BASED ACCESS CONTROL

### Master Users (Nikhil & Garima)
- Full CRUD access to all modules
- View all data across all sections
- Update any record
- Configure system settings
- Manage user roles
- Access all reports
- Control alert settings
- Manage payments (Section 6)
- Archive/Delete data (with audit trail)
- View audit logs
- Generate compliance reports

### Regular Users
**Limited Access:**
- Stock Inventory: View and update status only
- Cost Estimates: Create drafts, view own estimates
- Attendance: Mark own attendance (employees), manage team (HR)
- Interview Tracking: Access assigned interviews only
- Client Management: View assigned clients, update status
- Payment Tracking: No access
- Analytics: View limited reports
- Chat: Access permitted
- File Export: Limited to own data

---

## TECHNICAL REQUIREMENTS

### Frontend Stack
- **Desktop:** React + Tailwind CSS
- **Mobile:** React Native
- **Web:** Next.js 15+

### Backend Stack
- **Framework:** FastAPI (Python 3.10+)
- **Authentication:** JWT tokens
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **File Generation:** ReportLab, python-docx, openpyxl
- **AI Integration:** LangChain, OpenAI API
- **Email:** SMTP, SendGrid
- **Real-time:** WebSockets

### Desktop App
- **Framework:** PyQt5
- **Packaging:** PyInstaller
- **Updates:** Auto-update mechanism

### Security Requirements
- HTTPS/SSL encryption
- JWT authentication
- Password hashing (bcrypt)
- SQL injection prevention (ORM)
- CORS protection
- Rate limiting
- Audit logging
- Data backup
- No random data deletion (soft deletes)

### Performance Requirements
- App size: < 200MB
- Load time: < 2 seconds
- API response: < 500ms
- Database query: < 100ms
- Concurrent users: 100+

### Data Security
- Encrypted password storage
- Encrypted sensitive data (API keys, PII)
- Database backups (daily)
- Audit trail for all changes
- Soft deletes (never permanently delete)
- Access logs
- Session management
- Two-factor authentication (optional)

---

## DEPLOYMENT & INFRASTRUCTURE

### Frontend Deployment
- Vercel (for Next.js web)
- App stores (for mobile)

### Backend Deployment
- AWS EC2 / Heroku / DigitalOcean
- Docker containerization
- Environment variables management

### Database
- PostgreSQL on AWS RDS / DigitalOcean
- Regular automated backups
- Disaster recovery plan

### File Storage
- AWS S3 (for PDFs, exports, images)
- CDN integration

---

## BRANDING & UI/UX

### Logo Integration
- Woodful logo on all pages
- Logo in:
  - Navigation bar
  - Estimate PDFs
  - Salary slips
  - Reports
  - Login page

### UI Design
- Responsive design (Mobile first)
- Dark/Light mode support
- Consistent color scheme aligned with logo
- Accessibility (WCAG 2.1)
- Mobile-optimized layouts
- Desktop-optimized layouts
- Intuitive navigation
- Real-time feedback
- Loading states
- Error handling UI

### UX Principles
- Minimal clicks to complete tasks
- Clear call-to-action buttons
- Confirmation dialogs for critical actions
- Undo functionality where possible
- Search and filter capabilities
- Keyboard shortcuts
- Help tooltips
- Context-sensitive help

---

## TIMELINE & MILESTONES

### Phase 1 (Week 1-2): Foundation
- [ ] Database schema design
- [ ] User authentication system
- [ ] Role-based access control
- [ ] Basic UI framework
- [ ] API structure setup

### Phase 2 (Week 3-5): Core Modules
- [ ] Stock Inventory module
- [ ] Client Management module
- [ ] Cost Estimates module
- [ ] PDF generation

### Phase 3 (Week 6-8): HR & Finance
- [ ] Employee Attendance module
- [ ] Salary Management module
- [ ] Payment Tracking module
- [ ] Indian law compliance

### Phase 4 (Week 9-10): Advanced Features
- [ ] Interview Tracking module
- [ ] AI Chat integration
- [ ] Alert system
- [ ] Analytics & Reporting

### Phase 5 (Week 11-12): Polish & Deploy
- [ ] Testing & QA
- [ ] Performance optimization
- [ ] Security audit
- [ ] Deployment setup
- [ ] Production launch

---

## SUCCESS CRITERIA

- ✅ All 10 modules fully functional
- ✅ Master users can view/update all data
- ✅ Regular users have limited access as specified
- ✅ No random data deletion (only soft deletes)
- ✅ Secure data storage and transmission
- ✅ All PDFs/Reports generation working
- ✅ Alert system functioning (Email + Mobile)
- ✅ Indian law compliant salary slips
- ✅ Mobile and desktop responsive
- ✅ App size < 200MB
- ✅ Load time < 2 seconds
- ✅ 99.9% uptime
- ✅ All tests passing
- ✅ Security audit passed
- ✅ User documentation complete
- ✅ Training materials ready

---

## NEXT STEPS

1. Review and approve requirements
2. Create database schema
3. Set up development environment
4. Begin Phase 1 development
5. Weekly progress reviews

---

*Document Version: 2.0*  
*Last Updated: June 12, 2026*  
*Status: In Development*
