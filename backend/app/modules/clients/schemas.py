"""Clients feature - request/response schemas.

Covers the core Client entity plus its tightly-coupled sub-records
(activities, documents, product rate overrides) and the Excel import
workflow - none of these was substantial enough alone to justify a
separate file, and all six are the same Clients responsibility."""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, field_validator, model_validator

from app.shared.validators import validate_phone, validate_email

# Controlled Client Type list, shared verbatim by the UI dropdown, the
# Excel dropdown/validation, and the importer - never a
# UI-only or Excel-only list.
CLIENT_TYPES = ("Individual", "Business")
CLIENT_STATUSES = ("Active", "Inactive")
ACTIVITY_TYPES = ("Call", "Meeting", "Email", "Site Visit", "Note")


# ---------------------------------------------------------------------------
# Core Client
# ---------------------------------------------------------------------------

class ClientBase(BaseModel):
    client_code: Optional[str] = None  # server-generated on create, ignored if supplied
    name: str
    # Mandatory in the Client form and Excel importer, which both
    # always supply it and never let a user skip past it. A default is
    # still kept here (rather than making this field itself required
    # with no default) so existing integrations/tests created before
    # this field existed keep working instead of failing with a hard
    # 422. Any value that IS supplied is still validated.
    client_type: str = "Individual"
    contact_person: Optional[str] = None
    alternate_phone: Optional[str] = None
    # Mandatory - a client record with no way to reach them isn't
    # usable. Must be EXACTLY 10 digits - no country code, no
    # separators. Every rejection reason (missing, wrong length,
    # non-numeric, formatted) uses the exact same message, by explicit
    # requirement: "Please enter valid mobile number".
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    status: str = "Active"
    lead_source: Optional[str] = None
    first_contact_date: Optional[datetime] = None
    remarks: Optional[str] = None


class ClientCreate(ClientBase):
    @field_validator("client_type")
    @classmethod
    def client_type_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in CLIENT_TYPES:
            raise ValueError(f"Client Type must be one of: {', '.join(CLIENT_TYPES)}")
        return v

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and not validate_email(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in CLIENT_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(CLIENT_STATUSES)}")
        return v


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    client_type: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    status: Optional[str] = None
    lead_source: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("client_type")
    @classmethod
    def client_type_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in CLIENT_TYPES:
            raise ValueError(f"Client Type must be one of: {', '.join(CLIENT_TYPES)}")
        return v

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        # Phone is mandatory on the entity - an update is allowed to
        # leave it unset (unchanged), but never to explicitly clear it
        # to empty, and any value supplied must still be exactly 10
        # digits. Same exact message for every rejection reason.
        if v is None:
            return v
        v = v.strip()
        if not validate_phone(v):
            raise ValueError("Please enter valid mobile number")
        return v

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and not validate_email(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("gstin")
    @classmethod
    def gstin_must_be_15_characters(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in CLIENT_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(CLIENT_STATUSES)}")
        return v


class ClientResponse(ClientBase):
    id: int
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientWithStats(ClientResponse):
    total_orders: int
    total_sales: Optional[float] = None


# ---------------------------------------------------------------------------
# Client Activities (call/meeting/email/site-visit log)
# ---------------------------------------------------------------------------

class ClientActivityBase(BaseModel):
    client_id: int
    activity_type: str
    date: datetime
    summary: str
    logged_by: Optional[str] = None
    follow_up_date: Optional[datetime] = None


class ClientActivityCreate(ClientActivityBase):
    @field_validator("activity_type")
    @classmethod
    def activity_type_must_be_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if v not in ACTIVITY_TYPES:
            raise ValueError(f"Activity Type must be one of: {', '.join(ACTIVITY_TYPES)}")
        return v


class ClientActivityUpdate(BaseModel):
    activity_type: Optional[str] = None
    date: Optional[datetime] = None
    summary: Optional[str] = None
    logged_by: Optional[str] = None
    follow_up_date: Optional[datetime] = None

    @field_validator("activity_type")
    @classmethod
    def activity_type_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v not in ACTIVITY_TYPES:
            raise ValueError(f"Activity Type must be one of: {', '.join(ACTIVITY_TYPES)}")
        return v


class ClientActivityResponse(ClientActivityBase):
    id: int
    created_at: datetime
    follow_up_done: bool = False

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Client Documents
# ---------------------------------------------------------------------------

class ClientDocumentResponse(BaseModel):
    id: int
    client_id: int
    original_filename: str
    content_type: Optional[str] = None
    description: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Client email (send estimate/order documents to a client by email)
# ---------------------------------------------------------------------------

class ClientEmailPreview(BaseModel):
    """What the frontend shows before sending - recipient/subject/body
    are all editable by the user before they confirm ("review
    recipient/subject/message before sending"). client_has_email
    distinguishes "no email on file, user must type one" from "client
    has an email, pre-filled and editable" - the frontend needs this
    to decide whether to show a warning."""
    recipient_email: Optional[str] = None
    client_has_email: bool
    subject: str
    body: str
    attachment_filename: str


class ClientEmailSendRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str


class ClientEmailSendResult(BaseModel):
    sent: bool
    message: str


# ---------------------------------------------------------------------------
# Client Product Rates (customer-specific pricing overrides)
# ---------------------------------------------------------------------------

class ClientProductRateBase(BaseModel):
    client_id: int
    product_id: Optional[int] = None  # None = client-wide default margin, applies to every product for this client
    margin_percent: Optional[Decimal] = None
    fixed_selling_price: Optional[Decimal] = None
    notes: Optional[str] = None


class ClientProductRateCreate(ClientProductRateBase):
    @model_validator(mode="after")
    def exactly_one_override_type(self):
        # A customer override is either a margin adjustment or a
        # direct negotiated price, never presented as both at once.
        if self.margin_percent is not None and self.fixed_selling_price is not None:
            raise ValueError("Set either margin_percent or fixed_selling_price, not both.")
        if self.margin_percent is None and self.fixed_selling_price is None:
            raise ValueError("Set either margin_percent or fixed_selling_price.")
        if self.margin_percent is not None and self.margin_percent >= 100:
            raise ValueError("Margin percent must be less than 100%.")
        if self.fixed_selling_price is not None and self.fixed_selling_price < 0:
            raise ValueError("Fixed selling price cannot be negative.")
        return self


class ClientProductRateUpdate(BaseModel):
    margin_percent: Optional[Decimal] = None
    fixed_selling_price: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("margin_percent")
    @classmethod
    def margin_percent_must_be_under_100(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v >= 100:
            raise ValueError("Margin percent must be less than 100%.")
        return v

    @field_validator("fixed_selling_price")
    @classmethod
    def fixed_selling_price_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Fixed selling price cannot be negative.")
        return v


class ClientProductRateResponse(ClientProductRateBase):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PricingResolveRequest(BaseModel):
    """Preview what rate would apply, and which rule would win, before
    actually saving a line item - lets the Estimate UI show "Calculated
    Price" vs "Manually Overridden Price" clearly."""
    product_id: Optional[int] = None
    client_id: Optional[int] = None
    estimate_id: Optional[int] = None
    explicit_override: Optional[Decimal] = None

    @field_validator("explicit_override")
    @classmethod
    def explicit_override_not_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Explicit override cannot be negative.")
        return v


class PricingResolveResponse(BaseModel):
    selling_rate: Decimal
    pricing_rule_applied: str
    margin_percent_used: Optional[Decimal] = None
    cost_used: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Client Excel import
# ---------------------------------------------------------------------------

class ClientImportRowPreview(BaseModel):
    row_number: int
    name: Optional[str] = None
    client_type: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    lead_source: Optional[str] = None
    remarks: Optional[str] = None
    matched_client_id: Optional[int] = None
    is_duplicate: bool = False
    # A name that closely resembles (but doesn't exactly match) an
    # existing client - never auto-resolved. The caller must show "Use
    # Existing" (set matched_client_id to this value on commit) /
    # "Create New" (leave as-is) / "Edit" to the user.
    possible_match_client_id: Optional[int] = None
    possible_match_name: Optional[str] = None
    errors: List[str] = []


class ClientImportPreviewResponse(BaseModel):
    total_rows: int
    new_rows: int
    duplicate_rows: int
    error_rows: int
    rows: List[ClientImportRowPreview]


class ClientImportCommitRow(BaseModel):
    """Echoes one reviewed row back for actual creation. matched_client_id
    (carried over from the preview response) means this row matched an
    existing client on BOTH name and phone - it is never re-created;
    it's counted as "existing client matched" and no new Client ID is
    generated, per the Client Recognition rule. A row without a match
    is only created if the caller explicitly leaves skip=False for it."""
    name: str
    client_type: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    site_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    lead_source: Optional[str] = None
    remarks: Optional[str] = None
    matched_client_id: Optional[int] = None
    skip: bool = False  # user chose not to import this row (e.g. unresolved duplicate)

    @model_validator(mode="after")
    def validate_when_not_skipped(self):
        # A row marked skip=True is never written to the database, so
        # it doesn't need to pass the same validity checks a real
        # client creation would - the person may be intentionally
        # leaving a broken/duplicate row behind unfixed. A matched row
        # is never written either (it reuses the existing client
        # as-is), so it doesn't need re-validation of fields that
        # already belong to a valid, existing record.
        if self.skip or self.matched_client_id:
            return self
        if not self.client_type or self.client_type not in CLIENT_TYPES:
            raise ValueError(f"Client Type must be one of: {', '.join(CLIENT_TYPES)}")
        phone = (self.phone or "").strip()
        if not phone or not validate_phone(phone):
            raise ValueError("Please enter valid mobile number")
        self.phone = phone
        if self.email and not validate_email(self.email):
            raise ValueError("Enter a valid email address.")
        if self.gstin and len(self.gstin) != 15:
            raise ValueError("GSTIN must contain 15 characters.")
        return self


class ClientImportCommitRequest(BaseModel):
    rows: List[ClientImportCommitRow]


class ClientImportCommitResult(BaseModel):
    created_clients: int
    matched_existing: int
    skipped: int
    client_ids: List[int]
    error: Optional[str] = None
