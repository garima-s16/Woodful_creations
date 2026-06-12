"""
Stock module Pydantic schemas for validation and serialization
Enhanced with material types and variants
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


class MaterialTypeEnum(str, Enum):
    PLYWOOD_COMMERCIAL = "plywood_commercial"
    BWP_PLYWOOD = "bwp_plywood"
    MARINE_PLYWOOD = "marine_plywood"
    MDF = "mdf"
    PRELAMINATED_MDF = "prelaminated_mdf"
    HDHMR = "hdhmr"
    HDF = "hdf"
    PARTICLE_BOARD = "particle_board"
    PRELAMINATED_PARTICLE = "prelaminated_particle"
    BLOCK_BOARD = "block_board"
    FLUSH_DOOR_BOARD = "flush_door_board"
    WPC_BOARD = "wpc_board"
    PVC_BOARD = "pvc_board"
    ACRYLIC_SHEET = "acrylic_sheet"
    VENEER_MDF_PLYWOOD = "veneer_mdf_plywood"
    FLEXI_PLYWOOD = "flexi_plywood"


# Material display names
MATERIAL_DISPLAY_NAMES = {
    "plywood_commercial": "Plywood (Commercial/MR)",
    "bwp_plywood": "BWP/BWR Plywood",
    "marine_plywood": "Marine Plywood",
    "mdf": "MDF",
    "prelaminated_mdf": "Pre-Laminated MDF",
    "hdhmr": "HDHMR",
    "hdf": "HDF",
    "particle_board": "Particle Board",
    "prelaminated_particle": "Pre-Laminated Particle Board",
    "block_board": "Block Board",
    "flush_door_board": "Flush Door Board",
    "wpc_board": "WPC Board",
    "pvc_board": "PVC Board",
    "acrylic_sheet": "Acrylic Sheet",
    "veneer_mdf_plywood": "Veneer MDF/Plywood",
    "flexi_plywood": "Flexi Plywood",
}


class StockCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class StockCategoryCreate(StockCategoryBase):
    pass


class StockCategoryResponse(StockCategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku_prefix: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    category_id: int
    material_type: MaterialTypeEnum


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    material_type: Optional[MaterialTypeEnum] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProductVariantBase(BaseModel):
    product_id: int
    thickness: float = Field(..., gt=0, description="Thickness in mm")
    unit: str = Field(default="sheet")
    minimum_quantity: int = Field(default=10, ge=1)
    reorder_quantity: int = Field(default=50, ge=1)
    cost_price: float = Field(..., gt=0)
    selling_price: float = Field(..., gt=0)
    standard_width: Optional[float] = None
    standard_length: Optional[float] = None
    supplier_name: Optional[str] = None
    grade: Optional[str] = None
    finish: Optional[str] = None
    location: Optional[str] = None
    
    @validator('selling_price')
    def validate_selling_price(cls, v, values):
        if 'cost_price' in values and v < values['cost_price']:
            raise ValueError('Selling price must be >= cost price')
        return v


class ProductVariantCreate(ProductVariantBase):
    quantity_in_stock: int = Field(default=0, ge=0)
    sku: Optional[str] = None  # Auto-generated if not provided
    barcode: Optional[str] = None


class ProductVariantUpdate(BaseModel):
    thickness: Optional[float] = None
    minimum_quantity: Optional[int] = None
    reorder_quantity: Optional[int] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    supplier_name: Optional[str] = None
    grade: Optional[str] = None
    finish: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


class ProductVariantResponse(ProductVariantBase):
    id: int
    sku: str
    barcode: Optional[str]
    quantity_in_stock: int
    status: StockStatusEnum
    standard_area: Optional[float]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_restocked: Optional[datetime]
    
    class Config:
        from_attributes = True


class ProductVariantDetailResponse(ProductVariantResponse):
    profit_margin: float = Field(..., description="Profit margin percentage")
    stock_value: float = Field(..., description="Total stock value")


class StockMovementBase(BaseModel):
    variant_id: int
    product_id: int
    movement_type: str = Field(..., description="in, out, adjustment, return")
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


class StockAlertResponse(BaseModel):
    id: int
    variant_id: int
    product_id: int
    alert_type: str
    threshold: int
    current_quantity: int
    is_active: bool
    is_resolved: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class InventoryAuditCreate(BaseModel):
    variant_id: int
    product_id: int
    physical_quantity: int = Field(..., ge=0)
    audited_by: str
    notes: Optional[str] = None


class InventoryAuditResponse(InventoryAuditCreate):
    id: int
    system_quantity: int
    variance: int
    variance_percentage: float
    created_at: datetime
    action_taken: Optional[str]
    
    class Config:
        from_attributes = True


class MaterialStockResponse(BaseModel):
    """Response for a complete material with all variants"""
    product: ProductResponse
    variants: List[ProductVariantResponse]
    total_stock_quantity: int
    total_stock_value: float
    low_stock_variants: List[ProductVariantResponse]
    out_of_stock_variants: List[ProductVariantResponse]


class StockSummary(BaseModel):
    total_products: int
    total_variants: int
    total_quantity: int
    total_value: float
    low_stock_count: int
    out_of_stock_count: int
    active_alerts: int
    material_breakdown: dict  # Material type -> quantity


class DashboardMetrics(BaseModel):
    total_materials: int
    total_variants: int
    in_stock_variants: int
    low_stock_variants: int
    out_of_stock_variants: int
    total_inventory_value: float
    recent_movements: List[StockMovementResponse]
    active_alerts: List[StockAlertResponse]
    low_stock_variants_list: List[ProductVariantDetailResponse]
