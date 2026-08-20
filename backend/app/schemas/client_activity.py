from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ClientActivityBase(BaseModel):
    client_id: int
    activity_type: str
    date: datetime
    summary: str
    logged_by: Optional[str] = None
    follow_up_date: Optional[datetime] = None


class ClientActivityCreate(ClientActivityBase):
    pass


class ClientActivityUpdate(BaseModel):
    activity_type: Optional[str] = None
    date: Optional[datetime] = None
    summary: Optional[str] = None
    logged_by: Optional[str] = None
    follow_up_date: Optional[datetime] = None


class ClientActivityResponse(ClientActivityBase):
    id: int
    created_at: datetime
    follow_up_done: bool = False

    class Config:
        from_attributes = True
