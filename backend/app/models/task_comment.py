from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class TaskComment(BaseModel):
    """Simple comment on a task - practical shop-floor communication
    ("Laminate received, ready for cutting"), not a full collaboration
    platform."""
    __tablename__ = "task_comments"

    task_id = Column(Integer, ForeignKey("daily_tasks.id"), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    date = Column(DateTime, nullable=False)

    task = relationship("DailyTask")
