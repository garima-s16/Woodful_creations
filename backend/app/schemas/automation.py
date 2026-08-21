from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AutomationLogResponse(BaseModel):
    id: int
    rule_key: str
    trigger_event: str
    condition_summary: str
    action_taken: str
    status: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    notification_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AutomationRuleInfo(BaseModel):
    key: str
    event: str
    action: str


class AutomationRunResult(BaseModel):
    trigger_event: str
    logged: int
