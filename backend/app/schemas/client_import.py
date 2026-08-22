from pydantic import BaseModel, model_validator
from typing import Optional, List

from app.utils.validators import validate_phone, validate_email


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
    # Family 103 section 8: a name that closely resembles (but doesn't
    # exactly match) an existing client - never auto-resolved. The caller
    # must show "Use Existing" (set matched_client_id to this value on
    # commit) / "Create New" (leave as-is) / "Edit" to the user.
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
        # A row marked skip=True is never written to the database, so it
        # doesn't need to pass the same validity checks a real client
        # creation would - the person may be intentionally leaving a
        # broken/duplicate row behind unfixed. A matched row is never
        # written either (it reuses the existing client as-is), so it
        # doesn't need re-validation of fields that already belong to
        # a valid, existing record.
        if self.skip or self.matched_client_id:
            return self
        from app.schemas.client import CLIENT_TYPES
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
