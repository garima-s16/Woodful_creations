from pydantic import BaseModel
from typing import List, Optional


class ChatContext(BaseModel):
    """What the user is currently looking at, so the assistant can answer
    "summarize this order" style questions without the user needing to
    name the record explicitly. All optional - a chat message sent from
    the dashboard or a list page simply omits these."""
    order_id: Optional[int] = None
    client_id: Optional[int] = None
    material_id: Optional[int] = None
    employee_id: Optional[int] = None


class ChatRequest(BaseModel):
    message: str
    context: Optional[ChatContext] = None


class ProposedAction(BaseModel):
    """A structured, high-impact action the assistant has parsed from the
    conversation but has NOT executed. The frontend shows this for
    explicit user confirmation before calling the real endpoint - the
    assistant never modifies business data on its own. `action_type`
    tells the frontend which confirmation UI/endpoint to use; `payload`
    is the exact request body that endpoint expects."""
    action_type: str
    summary: str
    payload: dict


class ChatResponse(BaseModel):
    response: str
    suggestions: List[str] = []
    proposed_action: Optional[ProposedAction] = None
