from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


StockStatus = Literal["OUT OF STOCK", "LOW STOCK", "STOCK OK"]


class SupplierBase(BaseModel):
    name: str = Field(min_length=1)
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class SupplierCreate(SupplierBase):
    pass


class SupplierRead(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class MaterialBase(BaseModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    unit: str = Field(default="unit", min_length=1)
    opening_stock: float = Field(default=0, ge=0)
    minimum_stock: float = Field(default=0, ge=0)
    unit_price: float = Field(default=0, ge=0)
    supplier_id: int | None = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1)
    unit: str | None = Field(default=None, min_length=1)
    opening_stock: float | None = Field(default=None, ge=0)
    minimum_stock: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    supplier_id: int | None = None


class MaterialRead(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    current_stock: float
    status: StockStatus
    suggested_reorder_quantity: float


class StockInBase(BaseModel):
    material_id: int
    quantity: float = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)
    invoice_number: str | None = None
    purchased_at: datetime | None = None
    notes: str | None = None


class StockInCreate(StockInBase):
    pass


class StockInRead(StockInBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purchased_at: datetime


class StockOutBase(BaseModel):
    material_id: int
    quantity: float = Field(gt=0)
    issued_to: str | None = None
    issued_at: datetime | None = None
    notes: str | None = None


class StockOutCreate(StockOutBase):
    pass


class StockOutRead(StockOutBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issued_at: datetime


class SettingsUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1)
    currency: str | None = Field(default=None, min_length=1)
    reorder_buffer: float | None = Field(default=None, ge=1)


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    currency: str
    reorder_buffer: float


class DashboardSummary(BaseModel):
    total_stock_value: float
    low_stock_items: int
    out_of_stock_items: int
    purchase_value: float
    category_summary: list[dict]
    low_stock_action_list: list[dict]
