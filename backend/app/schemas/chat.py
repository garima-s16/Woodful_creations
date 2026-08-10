from pydantic import BaseModel
from typing import List, Optional


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    suggestions: List[str] = []
