from pydantic import BaseModel
from datetime import datetime


class OrderCommentCreate(BaseModel):
    text: str


class OrderCommentResponse(BaseModel):
    id: int
    order_id: int
    author: str
    text: str
    date: datetime

    class Config:
        from_attributes = True
