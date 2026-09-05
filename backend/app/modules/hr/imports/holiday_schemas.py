from typing import List, Optional

from pydantic import BaseModel


class HolidayImportRowPreview(BaseModel):
    row_number: int
    date: Optional[str] = None
    name: Optional[str] = None
    is_working: Optional[bool] = None
    remarks: Optional[str] = None
    is_duplicate: bool = False
    errors: List[str] = []


class HolidayImportPreviewResponse(BaseModel):
    total_rows: int
    new_rows: int
    duplicate_rows: int
    error_rows: int
    rows: List[HolidayImportRowPreview]


class HolidayImportCommitRow(BaseModel):
    date: str
    name: str
    is_working: bool
    remarks: Optional[str] = None
    skip: bool = False
    # If true, an existing holiday on this date is updated (name/type/
    # remarks) rather than treated as an error - lets the same
    # export -> edit -> import round trip that other importers support
    # also work for holidays.
    overwrite_existing: bool = False


class HolidayImportCommitRequest(BaseModel):
    rows: List[HolidayImportCommitRow]


class HolidayImportCommitResult(BaseModel):
    created: int
    updated: int
    skipped: int
    error: Optional[str] = None
