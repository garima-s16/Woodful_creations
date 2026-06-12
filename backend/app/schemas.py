"""
Pydantic Schemas for Request/Response Validation
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime

# ===================== AUTHENTICATION SCHEMAS =====================

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=12)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===================== INVENTORY SCHEMAS =====================

class InventoryItemCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(default=0, ge=0)
    min_stock: int = Field(default=10, ge=0)
    max_stock: int = Field(default=500, ge=0)
    reorder_quantity: int = Field(default=50, ge=0)
    unit_cost: float = Field(..., gt=0)
    selling_price: float = Field(..., gt=0)
    warehouse_location: Optional[str] = None
    supplier_id: Optional[str] = None

class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    reorder_quantity: Optional[int] = None
    unit_cost: Optional[float] = None
    selling_price: Optional[float] = None

class InventoryItemResponse(BaseModel):
    id: int
    sku: str
    name: str
    description: Optional[str]
    category: str
    quantity: int
    min_stock: int
    max_stock: int
    reorder_quantity: int
    unit_cost: float
    selling_price: float
    warehouse_location: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class StockMovementResponse(BaseModel):
    id: int
    item_id: int
    movement_type: str
    quantity_change: int
    previous_quantity: int
    new_quantity: int
    reason: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===================== CLIENT SCHEMAS =====================

class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone_number: str
    company_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    payment_terms: Optional[str] = None
    credit_limit: float = Field(default=0, ge=0)

class ClientResponse(BaseModel):
    id: int
    name: str
    email: str
    phone_number: str
    company_name: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]
    client_type: str
    credit_limit: float
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ClientProductResponse(BaseModel):
    id: int
    client_id: int
    quantity: int
    specifications: Optional[str]
    priority: str
    design_status: str
    execution_status: str
    delivery_status: str
    estimated_delivery: Optional[datetime]
    quoted_cost: Optional[float]
    actual_cost: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===================== CHAT SCHEMAS =====================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    user_message: str
    assistant_response: str
    action_type: Optional[str] = None
    action_result: Optional[Any] = None
    tokens_used: dict

class ChatHistoryResponse(BaseModel):
    id: int
    message_type: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===================== PAYMENT SCHEMAS =====================

class ClientPaymentCreate(BaseModel):
    client_id: int
    product_id: Optional[int] = None
    amount: float = Field(..., gt=0)
    payment_mode: str
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class ClientPaymentResponse(BaseModel):
    id: int
    client_id: int
    product_id: Optional[int]
    amount: float
    payment_mode: str
    payment_date: datetime
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True