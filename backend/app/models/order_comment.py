from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class OrderComment(BaseModel):
    """Project-level communication tied to an Order - the same simple
    practical pattern as TaskComment (app/models/task_comment.py), just
    scoped to the whole project rather than one task. Deliberately not a
    generic/parent-type comment table: an Order-level thread and a
    task-level thread serve different audiences (project-wide context
    vs. one specific job), so keeping them as separate, purpose-built
    tables - matching how TaskComment was already built - is clearer
    than a single polymorphic comments table would be."""
    __tablename__ = "order_comments"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    date = Column(DateTime, nullable=False, default=datetime.utcnow)

    order = relationship("Order")
