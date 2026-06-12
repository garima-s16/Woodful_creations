# API REFERENCE - WOODFUL CREATIONS

## Base URL
```
http://localhost:8000/api
```

## Authentication
All endpoints require JWT token in header:
```
Authorization: Bearer {token}
```

## Stock Inventory Endpoints

### Create Product
```
POST /inventory/products
Content-Type: application/json

{
  "name": "Wooden Chair",
  "sku": "WC-001",
  "category": "Furniture",
  "quantity": 50,
  "min_stock": 10,
  "unit_cost": 500.00,
  "selling_price": 1200.00,
  "supplier": "Supplier Name",
  "warehouse_location": "A1-Shelf-01"
}

Response: 201 Created
{
  "id": "uuid",
  "name": "Wooden Chair",
  "sku": "WC-001",
  ...
}
```

### Get All Products
```
GET /inventory/products?skip=0&limit=100&category=Furniture

Response: 200 OK
{
  "products": [...],
  "total": 100
}
```

### Get Product by ID
```
GET /inventory/products/{id}

Response: 200 OK
{
  "id": "uuid",
  "name": "Wooden Chair",
  ...
}
```

### Update Product
```
PUT /inventory/products/{id}

{
  "name": "Wooden Chair Updated",
  "quantity": 45
}

Response: 200 OK
```

### Delete Product (Soft Delete)
```
DELETE /inventory/products/{id}

Response: 200 OK
{
  "message": "Product deleted successfully"
}
```

### Update Stock
```
PATCH /inventory/products/{id}/stock

{
  "quantity": 40
}

Response: 200 OK
```

### Get Low Stock Items
```
GET /inventory/low-stock?threshold=10

Response: 200 OK
{
  "items": [
    {
      "id": "uuid",
      "name": "Product",
      "quantity": 5,
      "min_stock": 10
    }
  ]
}
```

### Get Categories
```
GET /inventory/categories

Response: 200 OK
{
  "categories": ["Furniture", "Hardware", "Materials"]
}
```

## AI Chat Endpoints

### Send Message
```
POST /chat/message

{
  "message": "Show low stock items",
  "context": {}
}

Response: 200 OK
{
  "reply": "You have 3 items below minimum stock level...",
  "action": "show_low_stock"
}
```

### Get Chat History
```
GET /chat/history?limit=50

Response: 200 OK
{
  "messages": [
    {
      "id": "uuid",
      "text": "User message",
      "sender": "user",
      "timestamp": "2026-06-12T10:00:00Z"
    }
  ]
}
```

### Clear Chat History
```
DELETE /chat/history

Response: 200 OK
{
  "message": "Chat history cleared"
}
```

## Authentication Endpoints

### Login
```
POST /auth/login

{
  "email": "nikhil@woodful.com",
  "password": "Welcome@123"
}

Response: 200 OK
{
  "access_token": "eyJ0...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "nikhil@woodful.com",
    "full_name": "Nikhil",
    "role": "master",
    "is_master": true
  }
}
```

### Get Current User
```
GET /auth/me

Response: 200 OK
{
  "id": "uuid",
  "email": "nikhil@woodful.com",
  "full_name": "Nikhil",
  "role": "master",
  "is_master": true
}
```

## Error Responses

### 400 Bad Request
```json
{
  "status": "error",
  "status_code": 400,
  "message": "Invalid input data",
  "timestamp": "2026-06-12T10:00:00Z"
}
```

### 401 Unauthorized
```json
{
  "status": "error",
  "status_code": 401,
  "message": "Invalid credentials",
  "timestamp": "2026-06-12T10:00:00Z"
}
```

### 403 Forbidden
```json
{
  "status": "error",
  "status_code": 403,
  "message": "Access denied - Master user only",
  "timestamp": "2026-06-12T10:00:00Z"
}
```

### 404 Not Found
```json
{
  "status": "error",
  "status_code": 404,
  "message": "Product not found",
  "timestamp": "2026-06-12T10:00:00Z"
}
```

## Rate Limiting
- 1000 requests per hour per user
- 10 requests per second per IP

## Pagination
All list endpoints support:
- `skip`: Number of items to skip (default: 0)
- `limit`: Number of items to return (default: 100, max: 1000)

## Timestamps
All timestamps are in UTC ISO 8601 format: `2026-06-12T10:00:00Z`

## Status Codes
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Server Error
