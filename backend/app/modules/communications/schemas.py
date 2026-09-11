"""Communications domain Pydantic schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.modules.communications.models import Notification, AutomationLog


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


class SearchResult(BaseModel):
    type: str
    id: int
    label: str
    snippet: str
    path: str
    date: Optional[datetime] = None


class CommunicationInsightsRequest(BaseModel):
    entity_type: str  # "order" or "client"
    entity_id: int


class CommunicationInsightsResponse(BaseModel):
    method: str  # always "rule_based_extractive" - see services/communication_ai_service.py
    summary: str
    action_items: List[str]
    unanswered_items: List[str]
    entry_count: int


class DraftMessageRequest(BaseModel):
    entity_type: str  # "order" or "client"
    entity_id: int
    purpose: str  # "follow_up" / "status_update" / "payment_reminder"
    detail: Optional[str] = None


class DraftMessageResponse(BaseModel):
    method: str  # always "template" - not AI-generated, see services/communication_ai_service.py
    draft: str
    note: str


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
