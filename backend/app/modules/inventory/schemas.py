"""Inventory domain schemas - materials, material categories/attributes,
purchases, locations, stock ledger entries, stock transactions
(transfers/adjustments), suppliers, and supplier-material relationships.
Consolidated from eight separate modules that are all genuinely part of
the same inventory feature area - material.py already directly imported
from material_category.py before this consolidation.

material_import.py and purchase_import.py are deliberately NOT included
here - they're bulk-import infrastructure, a different concern from
this module's core CRUD schemas."""
from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.shared.validators import validate_phone

# --- Material Category (attributes/subcategories) -------------------------

ATTRIBUTE_DATA_TYPES = ["text", "number", "select"]


class MaterialCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class MaterialCategoryResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialAttributeDefinitionCreate(BaseModel):
    name: str
    data_type: str = "text"
    unit_label: Optional[str] = None
    select_options: Optional[str] = None  # comma-separated, only meaningful when data_type="select"
    is_required: bool = False
    sort_order: int = 0

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v):
        if v not in ATTRIBUTE_DATA_TYPES:
            raise ValueError(f"data_type must be one of: {', '.join(ATTRIBUTE_DATA_TYPES)}")
        return v


class MaterialAttributeDefinitionResponse(BaseModel):
    id: int
    subcategory_id: int
    name: str
    data_type: str
    unit_label: Optional[str] = None
    select_options: Optional[str] = None
    is_required: bool
    sort_order: int

    class Config:
        from_attributes = True


class MaterialSubcategoryCreate(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None


class MaterialSubcategoryResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    category_id: int
    name: str
    description: Optional[str] = None
    attribute_definitions: List[MaterialAttributeDefinitionResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialCategoryWithSubcategories(MaterialCategoryResponse):
    subcategories: List[MaterialSubcategoryResponse] = []


class MaterialAttributeValueInput(BaseModel):
    """What the frontend sends when setting a material's attribute
    values - keyed by attribute_definition_id since the frontend already
    has the subcategory's attribute definitions loaded to render the
    right form fields."""
    attribute_definition_id: int
    value_text: Optional[str] = None
    value_number: Optional[Decimal] = None


class MaterialAttributeValueResponse(BaseModel):
    id: int
    attribute_definition_id: int
    attribute_name: str
    value_text: Optional[str] = None
    value_number: Optional[Decimal] = None
    display_value: str

    class Config:
        from_attributes = True


# --- Material -----------------------------------------------------------


class MaterialBase(BaseModel):
    material_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    # Kept for backward compatibility - existing consumers read this
    # directly. When subcategory_id is set, this is derived server-side
    # from the subcategory's category name, not taken from client input.
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: str
    # Decimal, not int - a material measured in kg/litres/metres needs
    # real decimal precision (e.g. a 2.5 kg reorder threshold).
    minimum_stock: Decimal = Decimal("0")
    average_rate: Decimal = Decimal("0")
    is_active: bool = True
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    location_id: Optional[int] = None


class MaterialCreate(MaterialBase):
    opening_stock: Decimal = Decimal("0")

    @field_validator("opening_stock")
    @classmethod
    def opening_stock_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Opening stock cannot be negative")
        return v

    @field_validator("minimum_stock")
    @classmethod
    def minimum_stock_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Minimum stock cannot be negative")
        return v

    @field_validator("average_rate")
    @classmethod
    def average_rate_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Average rate cannot be negative")
        return v


class MaterialNameInterpretResponse(BaseModel):
    """The material creation form's "intelligent defaults" - typing a
    name like "HDHMR 6mm" suggests thickness_size/subcategory_id, but
    never overwrites anything the user already picked (confidence
    "none" means show nothing)."""
    thickness_size: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    subcategory_id: Optional[int] = None
    subcategory_name: Optional[str] = None
    confidence: str  # "high" | "medium" | "none"
    matched_on: str
    attribute_values: List[MaterialAttributeValueInput] = []


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    subcategory_id: Optional[int] = None
    brand_grade: Optional[str] = None
    thickness_size: Optional[str] = None
    unit: Optional[str] = None
    minimum_stock: Optional[Decimal] = None
    average_rate: Optional[Decimal] = None
    is_active: Optional[bool] = None
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    location_id: Optional[int] = None
    attribute_values: Optional[List[MaterialAttributeValueInput]] = None

    @field_validator("minimum_stock")
    @classmethod
    def minimum_stock_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Minimum stock cannot be negative")
        return v

    @field_validator("average_rate")
    @classmethod
    def average_rate_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Average rate cannot be negative")
        return v


class MaterialResponse(MaterialBase):
    id: int
    business_id: Optional[str] = None
    opening_stock: Decimal
    total_purchased: Decimal
    total_issued: Decimal
    current_stock: Decimal
    stock_status: str
    # Optional, not the base Decimal/float - an employee's response has
    # these set to None server-side (see materials.py's _scrub_financial_fields),
    # a genuine redaction, not a value the frontend merely chooses not to show.
    average_rate: Optional[Decimal] = None
    stock_value: Optional[float] = None
    attribute_values: List[MaterialAttributeValueResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Purchase -----------------------------------------------------------

# The only receipt statuses stock_service.py's own logic recognizes
# (confirmed by reading record_purchase and mark_purchase_received
# directly, not invented here) - any other string must be rejected,
# since stock_service.py currently treats "anything not Ordered" as
# fully received, which an unrecognized/mistyped status could trigger
# accidentally.
PURCHASE_RECEIPT_STATUSES = {"Ordered", "Received", "Partially Received"}

# Creation only ever supports these two - a purchase cannot be created
# already "Partially Received" with no way to specify how much of it
# was actually received, which would produce quantity_received equal
# to the full order quantity while claiming a partial state (an
# internally contradictory record). A genuine partial receipt is
# only ever reached through mark_purchase_received, which tracks an
# explicit received quantity and derives the correct status from it.
# Matches the frontend's own creation form, which has never offered
# "Partially Received" as a creation-time option.
PURCHASE_CREATE_RECEIPT_STATUSES = {"Ordered", "Received"}


class PurchaseBase(BaseModel):
    purchase_code: Optional[str] = None  # server-generated on create, ignored if supplied
    date: datetime
    expected_delivery_date: Optional[datetime] = None
    supplier_id: int
    material_id: int
    quantity: Decimal
    unit: str
    rate: Decimal
    gst_percent: Decimal = Decimal("0")
    payment_status: str = "Paid"
    receipt_status: str = "Received"  # "Ordered" = not yet received, stock untouched until marked received
    location_id: Optional[int] = None  # which location receives the stock; falls back to the material's primary location if omitted


class PurchaseCreate(PurchaseBase):
    """taxable_value, gst_amount, invoice_total are computed server-side
    from quantity * rate and gst_percent - never trust client-sent totals."""
    @field_validator("receipt_status")
    @classmethod
    def receipt_status_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in PURCHASE_CREATE_RECEIPT_STATUSES:
            raise ValueError(f"Receipt Status must be one of: {', '.join(sorted(PURCHASE_CREATE_RECEIPT_STATUSES))}")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

    @field_validator("rate")
    @classmethod
    def rate_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Rate cannot be negative")
        return v

    @field_validator("gst_percent")
    @classmethod
    def gst_percent_in_range(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("GST percent must be between 0 and 100")
        return v


class PurchaseUpdate(BaseModel):
    payment_status: Optional[str] = None


class PurchaseReceiveRequest(BaseModel):
    """Optional - if quantity is omitted, receives everything still
    outstanding (the original all-or-nothing behavior)."""
    quantity: Optional[Decimal] = None
    location_id: Optional[int] = None  # which location receives this delivery; falls back to the purchase's own location_id, then the material's primary location

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive_if_given(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v


class PurchaseResponse(PurchaseBase):
    id: int
    business_id: Optional[str] = None
    taxable_value: Decimal
    gst_amount: Decimal
    invoice_total: Decimal
    quantity_received: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Location -----------------------------------------------------------


class LocationCreate(BaseModel):
    name: str
    location_type: Optional[str] = None
    parent_id: Optional[int] = None


class LocationResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    name: str
    location_type: Optional[str] = None
    parent_id: Optional[int] = None
    full_path: str

    class Config:
        from_attributes = True


class LocationTreeResponse(LocationResponse):
    children: List["LocationTreeResponse"] = []


LocationTreeResponse.model_rebuild()


# --- Stock Ledger Entry -----------------------------------------------------------


class StockLedgerEntryResponse(BaseModel):
    id: int
    material_id: int
    entry_type: str
    quantity_delta: Decimal
    balance_after: Decimal
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    location_id: Optional[int] = None
    remarks: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Stock Transactions (transfers/adjustments) -------------------------

ADJUSTMENT_TYPES = [
    "Physical Count Increase", "Physical Count Decrease", "Damage", "Wastage", "Theft/Loss",
    "Correction", "Return from Issue",
]


class StockTransferCreate(BaseModel):
    material_id: int
    quantity: Decimal
    to_location_id: int
    from_location_id: Optional[int] = None
    transferred_by: Optional[str] = None
    remarks: Optional[str] = None


class StockTransferResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    material_id: int
    quantity: Decimal
    from_location_id: Optional[int] = None
    to_location_id: int
    transferred_by: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StockAdjustmentCreate(BaseModel):
    material_id: int
    adjustment_type: str
    quantity_delta: Decimal
    reason: str
    related_issue_id: Optional[int] = None
    adjusted_by: Optional[str] = None
    location_id: Optional[int] = None  # which location this adjustment applies to; falls back to the material's primary location if omitted

    @field_validator("adjustment_type")
    @classmethod
    def adjustment_type_must_be_known(cls, v: str) -> str:
        if v not in ADJUSTMENT_TYPES:
            raise ValueError(f"'{v}' is not a recognized adjustment type. Valid values: {', '.join(ADJUSTMENT_TYPES)}")
        return v


class StockAdjustmentResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    material_id: int
    adjustment_type: str
    quantity_delta: Decimal
    stock_before: Decimal
    stock_after: Decimal
    reason: str
    related_issue_id: Optional[int] = None
    adjusted_by: Optional[str] = None
    location_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LocationBalance(BaseModel):
    """One location's share of a material's total stock, derived from
    the ledger - never an independently stored number."""
    location_id: Optional[int] = None  # None = movements recorded before multi-location existed, with no location on the material either
    location_name: str
    quantity: Decimal


class MaterialLocationStockResponse(BaseModel):
    material_id: int
    material_name: str
    unit: str
    total: Decimal  # must always equal Material.current_stock and the sum of `locations` below
    locations: list[LocationBalance]


# --- Supplier -----------------------------------------------------------


class SupplierBase(BaseModel):
    supplier_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    category: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    payment_terms: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        # Phone stays optional for a supplier (unlike Client Master,
        # where it's mandatory) - but IF one is given, it must be
        # exactly 10 digits, same rule and same exact message as
        # Client Master.
        if v is None or v == "":
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    payment_terms: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v


class SupplierResponse(SupplierBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Supplier Material -----------------------------------------------------------


class SupplierMaterialCreate(BaseModel):
    supplier_id: int
    material_id: int
    supplier_sku: Optional[str] = None
    supplier_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None
    is_preferred: bool = False
    notes: Optional[str] = None

    @field_validator("supplier_price")
    @classmethod
    def supplier_price_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Supplier price cannot be negative")
        return v

    @field_validator("moq")
    @classmethod
    def moq_not_negative(cls, v: Optional[int]) -> Optional[int]:
        # 0 is a legitimate MOQ (no minimum order quantity) - only a
        # negative quantity is impossible.
        if v is not None and v < 0:
            raise ValueError("MOQ cannot be negative")
        return v

    @field_validator("lead_time_days")
    @classmethod
    def lead_time_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Lead time days cannot be negative")
        return v


class SupplierMaterialUpdate(BaseModel):
    supplier_sku: Optional[str] = None
    supplier_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None
    is_preferred: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("supplier_price")
    @classmethod
    def supplier_price_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Supplier price cannot be negative")
        return v

    @field_validator("moq")
    @classmethod
    def moq_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("MOQ cannot be negative")
        return v

    @field_validator("lead_time_days")
    @classmethod
    def lead_time_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Lead time days cannot be negative")
        return v


class SupplierMaterialResponse(BaseModel):
    id: int
    supplier_id: int
    material_id: int
    supplier_sku: Optional[str] = None
    supplier_price: Optional[Decimal] = None
    last_purchase_price: Optional[Decimal] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None
    is_preferred: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierMaterialWithSupplierName(SupplierMaterialResponse):
    """Used when listing a material's suppliers - the supplier's name is
    what the UI actually needs to display, not just its ID."""
    supplier_name: str


class SupplierMaterialWithMaterialName(SupplierMaterialResponse):
    """Used when listing a supplier's materials."""
    material_name: str
