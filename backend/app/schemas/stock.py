"""
Stock module Pydantic schemas for validation and serialization
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class StockStatusEnum(str, Enum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    UNDER_REVIEW = "under_review"


class StockCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Category name")
    description: Optional[str] = Field(None, description="Category description")


class StockCategoryCreate(StockCategoryBase):
    pass


class StockCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class StockCategoryResponse(StockCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    category_id: int
    minimum_quantity: int = Field(default=10, ge=0)
    reorder_quantity: int = Field(default=50, ge=0)
    cost_price: float = Field(..., gt=0)
    selling_price: float = Field(..., gt=0)
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    barcode: Optional[str] = None
    
    @validator('selling_price')
    def validate_selling_price(cls, v, values):
        if 'cost_price' in values and v < values['cost_price']:
            raise ValueError('Selling price must be greater than or equal to cost price')
        return v


class ProductCreate(ProductBase):
    quantity_in_stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    minimum_quantity: Optional[int] = None
    reorder_quantity: Optional[int] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    location: Optional[str] = None
    supplier_id: Optional[int] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    quantity_in_stock: int
    status: StockStatusEnum
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_restocked: Optional[datetime]
    
    class Config:
        from_attributes = True


class ProductDetailResponse(ProductResponse):
    profit_margin: float = Field(..., description="Profit margin percentage")
    stock_value: float = Field(..., description="Total stock value (quantity * cost_price)")


class StockMovementBase(BaseModel):
    product_id: int
    movement_type: str = Field(..., description="in, out, or adjustment")
    quantity: int = Field(..., gt=0)
    reason: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class StockMovementCreate(StockMovementBase):
    updated_by: Optional[str] = None


class StockMovementResponse(StockMovementBase):
    id: int
    updated_by: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class BulkStockMovement(BaseModel):
    movements: List[StockMovementCreate] = Field(..., min_items=1)
    
    class Config:
        description = "Bulk stock movements for multiple products"


class StockAlertBase(BaseModel):
    product_id: int
    alert_type: str
    threshold: int = Field(..., ge=1)


class StockAlertCreate(StockAlertBase):
    pass


class StockAlertResponse(StockAlertBase):
    id: int
    current_quantity: int
    is_active: bool
    is_resolved: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class InventoryAuditBase(BaseModel):
    product_id: int
    physical_quantity: int = Field(..., ge=0)
    audited_by: str
    notes: Optional[str] = None


class InventoryAuditCreate(InventoryAuditBase):
    pass


class InventoryAuditResponse(InventoryAuditBase):
    id: int
    system_quantity: int
    variance: int
    variance_percentage: float
    created_at: datetime
    action_taken: Optional[str]
    
    class Config:
        from_attributes = True


class StockSummary(BaseModel):
    total_products: int
    total_quantity: int
    total_value: float
    low_stock_count: int
    out_of_stock_count: int
    active_alerts: int
    
    class Config:
        description = "Stock summary dashboard data"


class DashboardMetrics(BaseModel):
    total_products: int
    in_stock_products: int
    low_stock_products: int
    out_of_stock_products: int
    total_inventory_value: float
    average_stock_value: float
    recent_movements: List[StockMovementResponse]
    active_alerts: List[StockAlertResponse]
    
    class Config:
        description = "Stock dashboard metrics"
