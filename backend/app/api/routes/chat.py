from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.schemas.chat import ChatMessage, ChatResponse
from app.core.database import get_db
from app.core.security import verify_token
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.post("/", response_model=ChatResponse)
def chat(request: ChatMessage, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    user_role = auth.get("role", "user")
    response_text, suggestions = ChatService.process_message(request.message, db, user_role)
    return ChatResponse(
        response=response_text,
        conversation_id=request.conversation_id,
        suggestions=suggestions
    )