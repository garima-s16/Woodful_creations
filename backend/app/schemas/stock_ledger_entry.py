from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


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
