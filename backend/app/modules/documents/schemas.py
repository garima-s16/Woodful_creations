from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class GenericDocumentResponse(BaseModel):
    id: int
    parent_type: str
    parent_id: int
    original_filename: str
    content_type: Optional[str] = None
    description: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
