from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class OrderImportItemPreview(BaseModel):
    row_number: int
    order_ref: Optional[int] = None
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    rate: Optional[Decimal] = None
    discount_percent: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    errors: List[str] = []


class OrderImportHeaderPreview(BaseModel):
    row_number: int
    raw_order_id: Optional[str] = None
    matched_order_id: Optional[int] = None
    matched_order_code: Optional[str] = None
    is_new_order: bool = True
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    matched_client_id: Optional[int] = None
    raw_estimate_id: Optional[str] = None
    matched_estimate_id: Optional[int] = None
    matched_estimate_code: Optional[str] = None
    order_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    discount: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    notes: Optional[str] = None
    errors: List[str] = []
    items: List[OrderImportItemPreview] = []
    computed_subtotal: Optional[Decimal] = None
    computed_tax_amount: Optional[Decimal] = None
    computed_total: Optional[Decimal] = None


class OrderImportPreviewResponse(BaseModel):
    total_orders: int
    valid_orders: int
    error_orders: int
    new_orders: int
    existing_orders: int
    orphan_item_rows: List[OrderImportItemPreview] = []
    orders: List[OrderImportHeaderPreview]


class OrderImportCommitItem(BaseModel):
    product_id: int
    description: str
    category: Optional[str] = None
    quantity: Decimal
    unit: str = "Nos"
    rate: Decimal
    discount_percent: Decimal = Decimal("0")
    tax_percent: Optional[Decimal] = None


class OrderImportCommitOrder(BaseModel):
    matched_order_id: Optional[int] = None  # None = create new
    client_id: int
    from_estimate_id: Optional[int] = None  # convert this estimate, copying its items - items below ignored if set
    order_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    discount: Decimal = Decimal("0")
    tax_percent: Decimal = Decimal("18")
    notes: Optional[str] = None
    items: List[OrderImportCommitItem] = []
    skip: bool = False


class OrderImportCommitRequest(BaseModel):
    orders: List[OrderImportCommitOrder]


class OrderImportCommitResultRow(BaseModel):
    order_id: Optional[int] = None
    order_code: Optional[str] = None
    created: bool = False
    updated: bool = False
    skipped: bool = False
    error: Optional[str] = None


class OrderImportCommitResult(BaseModel):
    created_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    results: List[OrderImportCommitResultRow]
