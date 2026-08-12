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
        data.message, db, user_role=auth.get("role", "user"), context=data.context
    )
    return ChatResponse(response=response, suggestions=suggestions, proposed_action=proposed_action,
                         clarification=clarification, records=records)
