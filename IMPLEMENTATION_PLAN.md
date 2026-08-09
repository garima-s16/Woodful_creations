# Woodful Creations - Orders & Sales Management Implementation Plan

## Project Overview
Building an integrated Order & Sales Management system with Stock Control for a furniture/woodcraft business. Multi-platform (iOS, Android, Windows, macOS) with clean architecture and no data redundancies.

## Phase Architecture

### Phase 1: Database Schema & Backend Infrastructure
**Goal:** Establish data models and API foundation
**Timeline:** Week 1

#### 1.1 Database Schema (PostgreSQL)
**Tables to create:**
- Settings (enums/master data)
- Suppliers
- Materials (Stock Master)
- Purchase Orders (Stock In)
- Material Issues (Stock Out)
- Orders (Projects)
- Order Line Items
- Order Expenses
- Payments
- Payment Receipts

#### 1.2 Backend APIs (Python/Flask)
**Modules:**
- settings_api.py - CRUD for master data
- suppliers_api.py - Supplier management
- materials_api.py - Material master & stock calculations
- purchases_api.py - Stock inbound (Purchase Register)
- issues_api.py - Stock outbound (Material Issues)
- orders_api.py - Order management
- payments_api.py - Payment tracking
- reports_api.py - Profitability & analytics

### Phase 2: Frontend Components & State Management
**Goal:** Build React UI for all modules
**Timeline:** Week 2

#### 2.1 Redux Store Structure
```
store/
  slices/
    settingsSlice.js - Master data (statuses, priorities, etc.)
    suppliersSlice.js
    materialsSlice.js
    purchasesSlice.js
    issuesSlice.js
    ordersSlice.js
    paymentsSlice.js
```

#### 2.2 React Components
**Pages:**
- SettingsPage (Order & Sales Settings)
- SuppliersPage (Supplier Master)
- MaterialsPage (Live Material Stock Master)
- PurchasesPage (Stock In - Purchase Register)
- IssuesPage (Stock Out - Material Issue Register)
- OrdersPage (Order Management Dashboard)
- OrderDetailPage (Order profitability view)
- PaymentsPage (Client Payment Register)

**Reusable Components:**
- FormModal (for create/edit)
- DataTable (filterable, sortable)
- StockAlert (low stock warnings)
- ProfitabilityChart (order P&L visualization)

### Phase 3: Integration & Validation
**Goal:** Connect all modules, add business logic
**Timeline:** Week 3

#### 3.1 Business Logic
- Auto-calculate stock from Purchase - Issue
- Auto-calculate profitability (Order Value - Expenses - Received)
- Order status pipeline enforcement
- Payment tracking linked to orders
- Low stock alerts

#### 3.2 Data Validation
- No redundancies (single source of truth)
- Referential integrity (supplier → material → purchase → issue)
- Transaction consistency

### Phase 4: Mobile Responsiveness & PWA
**Goal:** Ensure cross-platform usability
**Timeline:** Week 4

- Responsive design for all components
- Mobile-first data tables
- Touch-friendly forms
- PWA testing on iOS/Android

## Implementation Constraints
✓ No emojis in any code file
✓ Clean architecture (no data redundancy)
✓ Cross-platform compatible (React handles this)
✓ Reusable components across pages

## File Structure

```
backend/
  app/
    models/
      settings.py
      supplier.py
      material.py
      purchase.py
      issue.py
      order.py
      payment.py
    routes/
      settings.py
      suppliers.py
      materials.py
      purchases.py
      issues.py
      orders.py
      payments.py
    services/
      stock_service.py (calculations)
      order_service.py (order logic)
      profitability_service.py (P&L)

frontend/
  src/
    pages/
      SettingsPage.js
      SuppliersPage.js
      MaterialsPage.js
      PurchasesPage.js
      IssuesPage.js
      OrdersPage.js
      OrderDetailPage.js
      PaymentsPage.js
    components/
      FormModal.js
      DataTable.js
      StockAlert.js
      ProfitabilityChart.js
    redux/
      slices/
        settingsSlice.js
        suppliersSlice.js
        materialsSlice.js
        purchasesSlice.js
        issuesSlice.js
        ordersSlice.js
        paymentsSlice.js
    services/
      api.js (axios config)
      calculations.js (client-side helpers)
```

## Data Model Relationships

```
Supplier (1) ---- (*) Material
  |
  +---- (*) Purchase Order
         |
         +---- (*) Material Issue ---- (*) Order (Project)
                        |
                        +---- (*) Order Expense
         |
         +---- (*) Stock Ledger
         |
Supplier ---- (*) Payment (payment_terms)

Order (1) ---- (*) Payment Receipt
         (1) ---- (*) Order Expense
         (1) ---- (*) Order Line Item
```

## Key Calculations

### Stock Level
```
Current Stock = Opening Stock + Total Purchased - Total Issued
Stock Status = IF(Current Stock >= Minimum Stock, "STOCK OK", "LOW STOCK")
```

### Order Profitability
```
Total Received = SUM(Payment Receipts for order)
Pending Payment = Order Value - Total Received
Total Expenses = SUM(Order Expenses) + SUM(Material Issue Value)
Gross Profit = Order Value - Total Expenses
Margin % = (Gross Profit / Order Value) * 100
```

### Purchase Costing
```
Taxable Value = Rate * Quantity
GST Amount = Taxable Value * (GST % / 100)  [18% standard]
Invoice Total = Taxable Value + GST Amount
```

## API Endpoints Summary

### Settings
- GET /api/settings/project-status
- GET /api/settings/priorities
- GET /api/settings/payment-modes
- GET /api/settings/lead-sources
- GET /api/settings/project-types
- GET /api/settings/expense-categories
- POST/PUT/DELETE /api/settings/{type}/{id}

### Suppliers
- GET /api/suppliers (with filtering)
- POST /api/suppliers
- PUT /api/suppliers/{id}
- DELETE /api/suppliers/{id}

### Materials
- GET /api/materials (with stock calculations)
- POST /api/materials
- PUT /api/materials/{id}
- GET /api/materials/stock-status (low stock alerts)

### Purchases
- GET /api/purchases
- POST /api/purchases (auto-calc GST)
- PUT /api/purchases/{id}
- PUT /api/purchases/{id}/payment-status

### Issues
- GET /api/issues
- POST /api/issues (decrement stock)
- PUT /api/issues/{id}

### Orders
- GET /api/orders
- POST /api/orders
- PUT /api/orders/{id}
- PUT /api/orders/{id}/status
- GET /api/orders/{id}/profitability

### Payments
- GET /api/payments
- POST /api/payments (receipt)
- GET /api/payments/by-order/{orderId}

### Reports
- GET /api/reports/order-profitability
- GET /api/reports/stock-summary
- GET /api/reports/supplier-performance

## Success Criteria
1. All CRUD operations working for each module
2. Stock calculations auto-update on purchase/issue
3. Order profitability auto-calculates
4. No data redundancies (normalized schema)
5. All pages responsive on mobile/tablet/desktop
6. No emojis in any code files
7. All APIs properly validated and error-handled
8. Cross-platform PWA working on iOS/Android

## Testing Strategy
- Unit tests for calculations (stock, profitability)
- Integration tests for API endpoints
- E2E tests for order creation → payment → profitability
- Mobile responsiveness testing
- PWA installation testing on actual devices

---

**Start Date:** [Date]
**Expected Completion:** [Date + 4 weeks]
**Status:** In Progress
