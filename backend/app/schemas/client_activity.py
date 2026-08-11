from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ClientActivityBase(BaseModel):
    client_id: int
    activity_type: str
    date: datetime
    summary: str
    logged_by: Optional[str] = None


class ClientActivityCreate(ClientActivityBase):
    pass


class ClientActivityResponse(ClientActivityBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
