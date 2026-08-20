from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SyncTriggerRequest(BaseModel):
    force: bool = False


class IntegrationSyncLogResponse(BaseModel):
    id: int
    external_system: str
    entity_type: str
    entity_id: int
    external_id: Optional[str] = None
    operation: str
    status: str
    attempt_number: int
    error_message: Optional[str] = None
    synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
