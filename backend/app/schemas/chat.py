from pydantic import BaseModel
from typing import Optional

class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_role: Optional[str] = "user"

class ChatResponse(BaseModel):
    response: str
    conversation_id: Optional[str] = None
    suggestions: Optional[list] = None