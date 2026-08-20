from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


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
    method: str  # always "rule_based_extractive" - see communication_ai_service.py
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
    method: str  # always "template" - not AI-generated, see communication_ai_service.py
    draft: str
    note: str
