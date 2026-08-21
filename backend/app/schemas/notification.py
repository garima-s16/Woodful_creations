from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificationResponse(BaseModel):
    id: int
    business_id: Optional[str] = None
    notification_type: str
    severity: str
    title: str
    message: str
    is_read: bool
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    action_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
