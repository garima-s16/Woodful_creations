from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal


class ProductImportRowPreview(BaseModel):
    row_number: int
    name: Optional[str] = None
    sku: Optional[str] = None
    product_type: Optional[str] = None
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    subcategory_id: Optional[int] = None
    description: Optional[str] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: Optional[str] = None
    finish: Optional[str] = None
    unit: Optional[str] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    notes: Optional[str] = None
    errors: List[str] = []


class ProductImportPreviewResponse(BaseModel):
    total_rows: int
    valid_rows: int
    error_rows: int
    rows: List[ProductImportRowPreview]


class ProductImportCommitRow(BaseModel):
    """What the frontend sends back after the user reviews the preview -
    exactly the fields needed to create a Product, never an ID (the
    product_code/business_id are always server-generated on commit,
    same as every other creation path in this app)."""
    name: str
    sku: Optional[str] = None
    product_type: str = "standard"
    subcategory_id: Optional[int] = None
    description: Optional[str] = None
    length: Optional[Decimal] = None
    width: Optional[Decimal] = None
    height: Optional[Decimal] = None
    dimension_unit: str = "in"
    finish: Optional[str] = None
    unit: str = "Piece"
    cost_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    lead_time_days: Optional[int] = None
    notes: Optional[str] = None


class ProductImportCommitRequest(BaseModel):
    rows: List[ProductImportCommitRow]


class ProductImportCommitResult(BaseModel):
    created_products: int
    product_ids: List[int]
    error: Optional[str] = None
