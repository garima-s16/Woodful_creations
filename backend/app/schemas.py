from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    quantity: int = Field(default=0, ge=0)
    min_stock: int = Field(default=10, ge=0)
    unit_cost: float = Field(..., gt=0)
    selling_price: float = Field(..., gt=0)
    supplier: Optional[str] = None
    warehouse_location: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    min_stock: Optional[int] = None
    unit_cost: Optional[float] = None
    selling_price: Optional[float] = None
    supplier: Optional[str] = None
    warehouse_location: Optional[str] = None

class ProductResponse(BaseModel):
    id: str
    name: str
    sku: str
    category: str
    description: Optional[str]
    quantity: int
    min_stock: int
    unit_cost: float
    selling_price: float
    supplier: Optional[str]
    warehouse_location: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class StockUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=0)
    notes: Optional[str] = None

class StockMovementResponse(BaseModel):
    id: str
    product_id: str
    movement_type: str
    quantity: int
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class StockAlertResponse(BaseModel):
    id: str
    product_id: str
    alert_type: str
    message: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class LowStockResponse(BaseModel):
    items: List[ProductResponse]
    count: int
    alerts: List[StockAlertResponse]

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    role: str
    is_master: bool
    is_active: bool
    
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None