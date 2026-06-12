from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import ChatMessage, User
from app.services.ai_chat import process_ai_message
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None

@router.post("/message")
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_message = ChatMessage(
        user_id=current_user.id,
        message=request.message,
        message_type="user"
    )
    db.add(user_message)
    db.commit()
    
    reply = await process_ai_message(
        request.message,
        current_user,
        request.context,
        db
    )
    
    user_message.response = reply.get("text", "")
    user_message.metadata = reply
    db.commit()
    
    return {
        "reply": reply.get("text", "I did not understand that request."),
        "action": reply.get("action")
    }

@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    messages = db.query(ChatMessage).filter(
        ChatMessage.user_id == current_user.id
    ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
    
    return {
        "messages": [
            {
                "id": msg.id,
                "text": msg.message,
                "sender": "user",
                "timestamp": msg.created_at,
            } for msg in reversed(messages)
        ]
    }

@router.delete("/history")
async def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Chat history cleared"}