from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.rate_limit import rate_limit
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.ai_layer import get_capabilities_report

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/capabilities")
def ai_capabilities(auth=Depends(get_current_user)):
    """Family 14's explicit honesty requirement: a plain classification
    of what this AI layer actually does right now (IMPLEMENTED),
    what depends on infrastructure not yet connected
    (EXTERNAL-SERVICE DEPENDENT), and what is not genuinely verified
    to exist (NOT VERIFIED). Open to any authenticated user - this is
    a description of the system, not business data."""
    return {"capabilities": get_capabilities_report()}


@router.post("/", response_model=ChatResponse, dependencies=[
    Depends(rate_limit("chat", settings.RATE_LIMIT_CHAT_PER_MINUTE))
])
def send_message(data: ChatRequest, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    response, suggestions, proposed_action, clarification, records = ChatService.process_message(
        data.message, db, user_role=auth.get("role", "user"), context=data.context,
        current_employee_id=auth.get("employee_id"),
    )
    # Whatever record (if any) this message was actually about - via
    # page context or a resolved deictic reference - carried forward
    # so a follow-up like "usme kya scene hai" can resolve next turn.
    last_entity = None
    if data.context:
        entity_type, entity_id = data.context.resolved_with_reference(data.message)
        if entity_type and entity_id:
            last_entity = {"type": entity_type, "id": entity_id}
    return ChatResponse(response=response, suggestions=suggestions, proposed_action=proposed_action,
                         clarification=clarification, records=records, last_entity=last_entity)
