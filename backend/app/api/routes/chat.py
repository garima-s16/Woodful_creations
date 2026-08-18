from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
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
