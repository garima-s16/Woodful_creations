from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user as verify_auth
from app.schemas.chat import ChatMessage, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
def chat(request: ChatMessage, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    user_role = auth.get("role", "user")
    response_text, suggestions = ChatService.process_message(request.message, db, user_role)
    return ChatResponse(response=response_text, conversation_id=request.conversation_id, suggestions=suggestions)
