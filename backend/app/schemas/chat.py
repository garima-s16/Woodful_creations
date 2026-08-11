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
    # Carries a partially-collected action across turns. There is no
    # server-side conversation table - the frontend simply echoes back
    # whatever `clarification` the previous response contained, so a
    # multi-turn "what payment mode?" exchange works statelessly.
    pending: Optional[dict] = None


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
    # What to remember for the next turn if the assistant is still
    # collecting information (e.g. has an amount, still needs a payment
    # mode). The frontend must send this back as context.pending on the
    # user's next message - it is never persisted server-side.
    clarification: Optional[dict] = None
