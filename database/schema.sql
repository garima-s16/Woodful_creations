-- WOODFUL CREATIONS - PostgreSQL Database Schema
-- Version 2.0 | All 10 Modules
-- Created: June 12, 2026

-- ============================================
-- USERS & AUTHENTICATION
-- ============================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user', -- 'master', 'hr', 'sales', 'delivery', 'user'
    is_active BOOLEAN DEFAULT TRUE,
    is_master BOOLEAN DEFAULT FALSE, -- TRUE for Nikhil & Garima
    phone VARCHAR(20),
    profile_image_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active' -- 'active', 'soft_deleted'
);

CREATE TABLE user_permissions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    module_name VARCHAR(100), -- 'inventory', 'estimates', 'attendance', 'interviews', 'clients', 'payments', 'chat', 'analytics', 'reports', 'alerts'
    permission_level VARCHAR(50), -- 'view', 'edit', 'delete', 'admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, module_name)
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    action VARCHAR(100),
    module_name VARCHAR(100),
    record_id INT,
    old_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- MODULE 1: STOCK INVENTORY
-- ============================================

CREATE TABLE inventory_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE inventory_items (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category_id INT REFERENCES inventory_categories(id),
    description TEXT,
    quantity INT NOT NULL DEFAULT 0,
    minimum_stock INT DEFAULT 10,
    reorder_quantity INT DEFAULT 50,
    unit_cost DECIMAL(12, 2),
    selling_price DECIMAL(12, 2),
    supplier_id INT,
    warehouse_location VARCHAR(100),
    image_url VARCHAR(500),
    barcode VARCHAR(100),
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE stock_movements (
    id SERIAL PRIMARY KEY,
    item_id INT REFERENCES inventory_items(id),
    movement_type VARCHAR(50), -- 'in', 'out', 'adjustment'
    quantity INT NOT NULL,
    reason VARCHAR(255),
    reference_id INT, -- Links to sales_order, purchase_order, etc.
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stock_alerts (
    id SERIAL PRIMARY KEY,
    item_id INT REFERENCES inventory_items(id),
    alert_type VARCHAR(50), -- 'low_stock', 'out_of_stock', 'overstock'
    quantity INT,
    alert_triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_by INT REFERENCES users(id),
    acknowledged_at TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    payment_terms VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

-- ============================================
-- MODULE 2: COST ESTIMATES & QUOTES
-- ============================================

CREATE TABLE estimates (
    id SERIAL PRIMARY KEY,
    estimate_number VARCHAR(50) UNIQUE NOT NULL,
    client_id INT REFERENCES users(id),
    created_by INT REFERENCES users(id),
    estimate_date DATE DEFAULT CURRENT_DATE,
    valid_until DATE,
    status VARCHAR(50) DEFAULT 'draft', -- 'draft', 'sent', 'approved', 'rejected', 'converted'
    total_amount DECIMAL(14, 2),
    discount_percent DECIMAL(5, 2) DEFAULT 0,
    discount_amount DECIMAL(14, 2) DEFAULT 0,
    tax_amount DECIMAL(14, 2) DEFAULT 0,
    final_amount DECIMAL(14, 2),
    notes TEXT,
    terms_conditions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    approved_at TIMESTAMP,
    deleted_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE estimate_items (
    id SERIAL PRIMARY KEY,
    estimate_id INT REFERENCES estimates(id) ON DELETE CASCADE,
    item_id INT REFERENCES inventory_items(id),
    quantity INT NOT NULL,
    unit_price DECIMAL(12, 2),
    customization_notes TEXT,
    line_total DECIMAL(14, 2),
    image_url VARCHAR(500)
);

CREATE TABLE estimate_versions (
    id SERIAL PRIMARY KEY,
    estimate_id INT REFERENCES estimates(id) ON DELETE CASCADE,
    version_number INT,
    created_by INT REFERENCES users(id),
    changes_description TEXT,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE estimate_approvals (
    id SERIAL PRIMARY KEY,
    estimate_id INT REFERENCES estimates(id) ON DELETE CASCADE,
    client_id INT REFERENCES users(id),
    status VARCHAR(50), -- 'pending', 'approved', 'rejected'
    approval_date TIMESTAMP,
    comments TEXT
);

-- ============================================
-- MODULE 3: EMPLOYEE ATTENDANCE & SALARY
-- ============================================

CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(20),
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    bank_account_number VARCHAR(50),
    bank_ifsc_code VARCHAR(20),
    pan_number VARCHAR(20),
    aadhar_number VARCHAR(20),
    uan_number VARCHAR(20), -- UAN for EPF
    esic_number VARCHAR(20),
    department VARCHAR(100),
    designation VARCHAR(100),
    joining_date DATE,
    employment_type VARCHAR(50), -- 'permanent', 'contract', 'temporary'
    salary_type VARCHAR(50), -- 'monthly', 'daily', 'hourly'
    ctc DECIMAL(14, 2),
    reporting_to INT REFERENCES employees(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id),
    attendance_date DATE NOT NULL,
    status VARCHAR(50), -- 'present', 'absent', 'leave', 'half-day', 'holiday', 'weekend'
    check_in_time TIME,
    check_out_time TIME,
    hours_worked DECIMAL(5, 2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, attendance_date)
);

CREATE TABLE leaves (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id),
    leave_type VARCHAR(50), -- 'casual', 'sick', 'earned', 'unpaid', 'maternity'
    from_date DATE NOT NULL,
    to_date DATE NOT NULL,
    number_of_days INT,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    approved_by INT REFERENCES users(id),
    approved_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE salary_structure (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id),
    basic_salary DECIMAL(12, 2),
    hra DECIMAL(12, 2) DEFAULT 0,
    dearness_allowance DECIMAL(12, 2) DEFAULT 0,
    other_allowances DECIMAL(12, 2) DEFAULT 0,
    pf_contribution DECIMAL(12, 2) DEFAULT 0, -- 12% of basic
    esi_contribution DECIMAL(12, 2) DEFAULT 0,
    professional_tax DECIMAL(12, 2) DEFAULT 0,
    income_tax DECIMAL(12, 2) DEFAULT 0,
    other_deductions DECIMAL(12, 2) DEFAULT 0,
    gross_salary DECIMAL(12, 2),
    net_salary DECIMAL(12, 2),
    effective_from DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, effective_from)
);

CREATE TABLE salary_slips (
    id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES employees(id),
    salary_month INT, -- 1-12
    salary_year INT,
    attendance_days INT,
    working_days INT,
    paid_days DECIMAL(6, 2),
    basic_paid DECIMAL(12, 2),
    hra_paid DECIMAL(12, 2),
    da_paid DECIMAL(12, 2),
    allowances_paid DECIMAL(12, 2),
    gross_earnings DECIMAL(12, 2),
    pf_deduction DECIMAL(12, 2),
    esi_deduction DECIMAL(12, 2),
    it_deduction DECIMAL(12, 2),
    pt_deduction DECIMAL(12, 2),
    other_deductions DECIMAL(12, 2),
    total_deductions DECIMAL(12, 2),
    net_pay DECIMAL(12, 2),
    payment_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processed', 'paid'
    payment_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, salary_month, salary_year)
);

CREATE TABLE payroll_records (
    id SERIAL PRIMARY KEY,
    salary_slip_id INT REFERENCES salary_slips(id),
    payment_mode VARCHAR(50), -- 'bank_transfer', 'cheque', 'cash'
    transaction_id VARCHAR(100),
    bank_reference VARCHAR(100),
    paid_amount DECIMAL(12, 2),
    paid_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- MODULE 4: INTERVIEW TRACKING
-- ============================================

CREATE TABLE job_positions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    department VARCHAR(100),
    required_skills TEXT,
    experience_required INT,
    salary_range_min DECIMAL(12, 2),
    salary_range_max DECIMAL(12, 2),
    status VARCHAR(50) DEFAULT 'open', -- 'open', 'closed', 'on_hold'
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE candidates (
    id SERIAL PRIMARY KEY,
    position_id INT REFERENCES job_positions(id),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    resume_url VARCHAR(500),
    skills TEXT,
    years_of_experience INT,
    current_company VARCHAR(255),
    current_designation VARCHAR(100),
    source VARCHAR(100), -- 'portal', 'referral', 'agency', 'direct'
    status VARCHAR(50) DEFAULT 'applied', -- 'applied', 'shortlisted', 'interview', 'offer', 'joined', 'rejected'
    rejection_reason TEXT,
    applied_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE interviews (
    id SERIAL PRIMARY KEY,
    candidate_id INT REFERENCES candidates(id),
    position_id INT REFERENCES job_positions(id),
    interview_type VARCHAR(50), -- 'phone', 'video', 'in_person'
    scheduled_date DATE,
    scheduled_time TIME,
    duration_minutes INT,
    interview_round INT DEFAULT 1,
    interview_by INT REFERENCES employees(id),
    meeting_link VARCHAR(500),
    location VARCHAR(255),
    status VARCHAR(50) DEFAULT 'scheduled', -- 'scheduled', 'completed', 'cancelled'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE interview_feedback (
    id SERIAL PRIMARY KEY,
    interview_id INT REFERENCES interviews(id),
    interviewer_id INT REFERENCES employees(id),
    rating INT CHECK (rating >= 1 AND rating <= 5),
    technical_score INT,
    communication_score INT,
    cultural_fit_score INT,
    feedback_notes TEXT,
    recommendation VARCHAR(50), -- 'proceed', 'reject', 'reconsider'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE offer_letters (
    id SERIAL PRIMARY KEY,
    candidate_id INT REFERENCES candidates(id),
    position_id INT REFERENCES job_positions(id),
    offered_salary DECIMAL(12, 2),
    offered_date DATE,
    valid_until DATE,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'accepted', 'rejected'
    response_date DATE,
    joining_date DATE,
    offer_document_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

-- ============================================
-- MODULE 5: CLIENT MANAGEMENT
-- ============================================

CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    client_name VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    alternate_phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    gst_number VARCHAR(50),
    pan_number VARCHAR(50),
    primary_contact_person VARCHAR(255),
    contact_designation VARCHAR(100),
    alternate_contact_person VARCHAR(255),
    credit_limit DECIMAL(14, 2) DEFAULT 0,
    payment_terms VARCHAR(100),
    preferred_communication VARCHAR(50), -- 'email', 'phone', 'whatsapp'
    client_category VARCHAR(50), -- 'vip', 'regular', 'new'
    notes TEXT,
    created_by INT REFERENCES users(id),
    assigned_to INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE client_products (
    id SERIAL PRIMARY KEY,
    client_id INT REFERENCES clients(id),
    product_name VARCHAR(255),
    quantity INT,
    specification TEXT,
    customization TEXT,
    priority VARCHAR(50), -- 'low', 'medium', 'high'
    requested_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE product_status_tracking (
    id SERIAL PRIMARY KEY,
    client_product_id INT REFERENCES client_products(id),
    design_status VARCHAR(50) DEFAULT 'not_started', -- 'not_started', 'in_progress', 'completed', 'approved'
    design_status_updated_at TIMESTAMP,
    execution_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'in_progress', 'quality_check', 'ready'
    execution_status_updated_at TIMESTAMP,
    delivery_status VARCHAR(50) DEFAULT 'not_shipped', -- 'not_shipped', 'in_transit', 'delivered'
    delivery_status_updated_at TIMESTAMP,
    estimated_delivery_date DATE,
    actual_delivery_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE client_payments (
    id SERIAL PRIMARY KEY,
    client_id INT REFERENCES clients(id),
    amount DECIMAL(14, 2),
    payment_date DATE,
    payment_mode VARCHAR(50), -- 'cash', 'cheque', 'bank_transfer', 'upi'
    reference_number VARCHAR(100),
    invoice_number VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE client_invoices (
    id SERIAL PRIMARY KEY,
    client_id INT REFERENCES clients(id),
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    invoice_date DATE,
    invoice_amount DECIMAL(14, 2),
    tax_amount DECIMAL(14, 2),
    total_amount DECIMAL(14, 2),
    due_date DATE,
    payment_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'partial', 'paid', 'overdue'
    amount_paid DECIMAL(14, 2) DEFAULT 0,
    outstanding_amount DECIMAL(14, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE client_design_approvals (
    id SERIAL PRIMARY KEY,
    client_product_id INT REFERENCES client_products(id),
    design_version INT,
    approval_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'changes_requested'
    design_file_url VARCHAR(500),
    design_image_urls TEXT, -- JSON array
    approved_by_client VARCHAR(255),
    approval_date TIMESTAMP,
    approval_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE client_change_requests (
    id SERIAL PRIMARY KEY,
    client_product_id INT REFERENCES client_products(id),
    change_request_number VARCHAR(50) UNIQUE NOT NULL,
    original_specification TEXT,
    requested_change TEXT,
    change_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'approved', 'implemented', 'rejected'
    requested_date DATE,
    implementation_deadline DATE,
    implemented_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE client_communications (
    id SERIAL PRIMARY KEY,
    client_id INT REFERENCES clients(id),
    communication_type VARCHAR(50), -- 'email', 'call', 'meeting', 'message'
    subject VARCHAR(255),
    details TEXT,
    communication_date TIMESTAMP,
    created_by INT REFERENCES users(id),
    attachment_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- MODULE 6: PAYMENT TRACKING (ADMIN ONLY)
-- ============================================

CREATE TABLE vendor_payments (
    id SERIAL PRIMARY KEY,
    vendor_id INT REFERENCES suppliers(id),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    invoice_amount DECIMAL(14, 2),
    payment_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'partial', 'paid'
    due_date DATE,
    payment_amount DECIMAL(14, 2),
    payment_date DATE,
    payment_mode VARCHAR(50), -- 'cash', 'cheque', 'bank_transfer'
    payment_reference VARCHAR(100),
    tds_applicable BOOLEAN DEFAULT FALSE,
    tds_amount DECIMAL(12, 2),
    gst_amount DECIMAL(12, 2),
    net_payment DECIMAL(14, 2),
    notes TEXT,
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE payment_proofs (
    id SERIAL PRIMARY KEY,
    vendor_payment_id INT REFERENCES vendor_payments(id),
    proof_type VARCHAR(50), -- 'receipt', 'bank_statement', 'cheque_image'
    file_url VARCHAR(500),
    uploaded_by INT REFERENCES users(id),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- MODULE 7: CHAT & NOTIFICATIONS
-- ============================================

CREATE TABLE chat_conversations (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    conversation_title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INT REFERENCES chat_conversations(id),
    sender_id INT REFERENCES users(id),
    message_type VARCHAR(50), -- 'user', 'assistant', 'system'
    content TEXT,
    file_attachments JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    recipient_id INT REFERENCES users(id),
    notification_type VARCHAR(100), -- 'low_stock', 'eta_alert', 'payment_due', 'interview_reminder'
    title VARCHAR(255),
    message TEXT,
    related_module VARCHAR(100),
    related_record_id INT,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    notification_channels JSONB, -- array of channels: 'email', 'sms', 'push', 'in_app'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE alert_settings (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    alert_type VARCHAR(100),
    is_enabled BOOLEAN DEFAULT TRUE,
    threshold_value DECIMAL(12, 2),
    frequency VARCHAR(50), -- 'immediate', 'daily', 'weekly'
    recipients JSONB, -- array of user IDs or emails
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, alert_type)
);

-- ============================================
-- MODULE 8: ANALYTICS & REPORTING
-- ============================================

CREATE TABLE analytics_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE DEFAULT CURRENT_DATE,
    total_inventory_value DECIMAL(14, 2),
    total_revenue DECIMAL(14, 2),
    total_outstanding_payments DECIMAL(14, 2),
    total_employees INT,
    attendance_percentage DECIMAL(5, 2),
    on_time_delivery_rate DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE custom_reports (
    id SERIAL PRIMARY KEY,
    report_name VARCHAR(255),
    report_type VARCHAR(100), -- 'inventory', 'sales', 'hr', 'finance'
    created_by INT REFERENCES users(id),
    report_config JSONB,
    generated_at TIMESTAMP,
    file_url VARCHAR(500),
    scheduled BOOLEAN DEFAULT FALSE,
    schedule_frequency VARCHAR(50), -- 'daily', 'weekly', 'monthly'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

-- ============================================
-- MODULE 9 & 10: DOCUMENT GENERATION & EXPORT
-- ============================================

CREATE TABLE generated_documents (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(50), -- 'estimate', 'invoice', 'salary_slip', 'offer_letter', 'report'
    related_id INT,
    file_format VARCHAR(20), -- 'pdf', 'docx', 'xlsx'
    file_url VARCHAR(500),
    file_size INT,
    generated_by INT REFERENCES users(id),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    downloaded_count INT DEFAULT 0,
    last_downloaded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deletion_status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE export_jobs (
    id SERIAL PRIMARY KEY,
    export_type VARCHAR(100), -- 'inventory_list', 'salary_register', 'client_list'
    export_format VARCHAR(20), -- 'excel', 'pdf', 'csv'
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    filters JSONB,
    file_url VARCHAR(500),
    requested_by INT REFERENCES users(id),
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_inventory_items_sku ON inventory_items(sku);
CREATE INDEX idx_inventory_items_category ON inventory_items(category_id);
CREATE INDEX idx_stock_movements_item_id ON stock_movements(item_id);
CREATE INDEX idx_stock_movements_created_at ON stock_movements(created_at);
CREATE INDEX idx_estimates_status ON estimates(status);
CREATE INDEX idx_estimates_created_at ON estimates(created_at);
CREATE INDEX idx_estimates_client_id ON estimates(client_id);
CREATE INDEX idx_attendance_employee_id ON attendance(employee_id);
CREATE INDEX idx_attendance_date ON attendance(attendance_date);
CREATE INDEX idx_salary_slips_employee_id ON salary_slips(employee_id);
CREATE INDEX idx_candidates_position_id ON candidates(position_id);
CREATE INDEX idx_candidates_status ON candidates(status);
CREATE INDEX idx_interviews_candidate_id ON interviews(candidate_id);
CREATE INDEX idx_interviews_scheduled_date ON interviews(scheduled_date);
CREATE INDEX idx_clients_category ON clients(client_category);
CREATE INDEX idx_clients_assigned_to ON clients(assigned_to);
CREATE INDEX idx_client_products_client_id ON client_products(client_id);
CREATE INDEX idx_product_status_delivery ON product_status_tracking(delivery_status);
CREATE INDEX idx_client_payments_client_id ON client_payments(client_id);
CREATE INDEX idx_vendor_payments_status ON vendor_payments(payment_status);
CREATE INDEX idx_notifications_recipient_id ON notifications(recipient_id);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_chat_messages_conversation_id ON chat_messages(conversation_id);
CREATE INDEX idx_documents_created_at ON generated_documents(generated_at);

-- ============================================
-- DATABASE SETUP COMPLETE
-- ============================================
-- This schema supports all 10 modules with comprehensive data tracking,
-- audit logging, soft deletes, and proper relationships.
-- Version: 2.0 | Production Ready