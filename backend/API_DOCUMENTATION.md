# WOODFUL CREATIONS - FastAPI Backend Documentation

## Overview
RESTful API built with FastAPI and Python 3.10+

## Authentication
- JWT token-based authentication
- Token expiry: 24 hours
- Refresh token: 7 days

## API Endpoints Structure

### 1. Authentication Endpoints
```
POST /api/auth/register - Create new account
POST /api/auth/login - User login
POST /api/auth/refresh - Refresh token
POST /api/auth/logout - User logout
GET /api/auth/profile - Get current user profile
PUT /api/auth/profile - Update profile
```

### 2. Inventory Management
```
GET /api/inventory/items - List all items
POST /api/inventory/items - Create item
GET /api/inventory/items/{id} - Get item details
PUT /api/inventory/items/{id} - Update item
DELETE /api/inventory/items/{id} - Delete item (soft delete)
GET /api/inventory/low-stock - Get low stock alerts
GET /api/inventory/movements - Stock movement history
POST /api/inventory/import - Bulk import from Excel
```

### 3. Cost Estimates
```
GET /api/estimates - List estimates
POST /api/estimates - Create estimate
GET /api/estimates/{id} - Get estimate details
PUT /api/estimates/{id} - Update estimate
POST /api/estimates/{id}/send - Send estimate to client
POST /api/estimates/{id}/approve - Approve estimate
GET /api/estimates/{id}/pdf - Generate PDF
```

### 4. Employee Management
```
GET /api/employees - List employees
POST /api/employees - Create employee
GET /api/employees/{id} - Get employee details
PUT /api/employees/{id} - Update employee
POST /api/attendance/mark - Mark attendance
GET /api/attendance/{employee_id} - Get attendance history
POST /api/salary/generate - Generate salary for month
GET /api/salary/slip/{id} - Get salary slip
```

### 5. Interviews
```
GET /api/interviews/positions - List job positions
GET /api/interviews/candidates - List candidates
POST /api/interviews/candidates - Add candidate
POST /api/interviews/schedule - Schedule interview
POST /api/interviews/{id}/feedback - Submit feedback
POST /api/interviews/{id}/offer - Generate offer letter
```

### 6. Client Management
```
GET /api/clients - List all clients
POST /api/clients - Create client
GET /api/clients/{id} - Get client profile
PUT /api/clients/{id} - Update client
GET /api/clients/{id}/products - Get client products
GET /api/clients/{id}/payments - Get payment history
GET /api/clients/{id}/invoices - Get invoices
PUT /api/clients/{id}/product-status - Update product status
```

### 7. Payments (Admin Only)
```
GET /api/payments/vendor - List vendor payments
POST /api/payments/vendor - Record payment
GET /api/payments/pending - Get pending payments
POST /api/payments/tds-calculation - Calculate TDS
```

### 8. Chat
```
POST /api/chat/message - Send message
GET /api/chat/history - Get chat history
GET /api/chat/suggestions - Get AI suggestions
```

### 9. Notifications & Alerts
```
GET /api/notifications - Get notifications
PUT /api/notifications/{id}/read - Mark as read
POST /api/alerts/settings - Configure alerts
GET /api/alerts/settings - Get alert settings
```

### 10. Analytics & Reports
```
GET /api/analytics/dashboard - Get dashboard metrics
GET /api/reports/inventory - Inventory report
GET /api/reports/sales - Sales report
GET /api/reports/hr - HR report
POST /api/reports/export - Export report
```

## Response Format
```json
{
  "success": true,
  "data": {},
  "message": "Success",
  "timestamp": "2026-06-12T10:00:00Z"
}
```

## Error Handling
```json
{
  "success": false,
  "error": "Error message",
  "status_code": 400,
  "timestamp": "2026-06-12T10:00:00Z"
}
```

## Status Codes
- 200: OK
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

## Rate Limiting
- 100 requests per minute per user
- 1000 requests per hour per IP

## Pagination
- Default limit: 20
- Max limit: 100
- Query: `?page=1&limit=20`

## Filtering
- Standard query parameters for filters
- Example: `/api/items?category=wood&status=active`

## Sorting
- Query: `?sort=created_at&order=desc`

Version: 2.0
Last Updated: June 12, 2026