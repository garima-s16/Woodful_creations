"""Pydantic schemas for request/response validation"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from app.models.user import UserRole
from app.models.inventory import MovementType, AlertType

# ============================================
# USER SCHEMAS
# ============================================

class UserRegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=12)  # 12+ characters required
    phone: Optional[str] = None
    
    class Config:
        from_attributes = True

class UserLoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    """User response"""
    id: int
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    is_master: bool
    phone: Optional[str]
    profile_image_url: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True

# ============================================
# INVENTORY SCHEMAS
# ============================================

class InventoryCategoryCreate(BaseModel):
    """Create inventory category"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class InventoryCategoryResponse(BaseModel):
    """Inventory category response"""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class InventoryItemCreate(BaseModel):
    """Create inventory item"""
    sku: str = Field(..., max_length=50)
    product_name: str = Field(..., max_length=255)
    category_id: Optional[int] = None
    description: Optional[str] = None
    quantity: int = Field(default=0, ge=0)
    minimum_stock: int = Field(default=10, ge=0)
    reorder_quantity: int = Field(default=50, ge=0)
    unit_cost: Optional[float] = None
    selling_price: Optional[float] = None
    supplier_id: Optional[int] = None
    warehouse_location: Optional[str] = None
    image_url: Optional[str] = None
    barcode: Optional[str] = None
    
    class Config:
        from_attributes = True

class InventoryItemUpdate(BaseModel):
    """Update inventory item"""
    product_name: Optional[str] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    minimum_stock: Optional[int] = None
    reorder_quantity: Optional[int] = None
    unit_cost: Optional[float] = None
    selling_price: Optional[float] = None
    supplier_id: Optional[int] = None
    warehouse_location: Optional[str] = None
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True

class InventoryItemResponse(BaseModel):
    """Inventory item response"""
    id: int
    sku: str
    product_name: str
    category_id: Optional[int]
    description: Optional[str]
    quantity: int
    minimum_stock: int
    reorder_quantity: int
    unit_cost: Optional[float]
    selling_price: Optional[float]
    supplier_id: Optional[int]
    warehouse_location: Optional[str]
    image_url: Optional[str]
    barcode: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class StockMovementCreate(BaseModel):
    """Create stock movement"""
    item_id: int
    movement_type: MovementType
    quantity: int = Field(..., gt=0)
    reason: Optional[str] = None
    reference_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class StockMovementResponse(BaseModel):
    """Stock movement response"""
    id: int
    item_id: int
    movement_type: MovementType
    quantity: int
    reason: Optional[str]
    reference_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

class StockAlertResponse(BaseModel):
    """Stock alert response"""
    id: int
    item_id: int
    alert_type: AlertType
    quantity: Optional[int]
    alert_triggered_at: datetime
    acknowledged_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class SupplierCreate(BaseModel):
    """Create supplier"""
    company_name: str = Field(..., max_length=255)
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    payment_terms: Optional[str] = None
    
    class Config:
        from_attributes = True

class SupplierResponse(BaseModel):
    """Supplier response"""
    id: int
    company_name: str
    contact_person: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]
    payment_terms: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================
# GENERIC RESPONSE SCHEMAS
# ============================================

class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True

class ErrorResponse(BaseModel):
    """Generic error response"""
    success: bool = False
    error: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel):
    """Paginated response"""
    success: bool = True
    data: List[dict]
    total: int
    page: int
    limit: int
    total_pages: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
