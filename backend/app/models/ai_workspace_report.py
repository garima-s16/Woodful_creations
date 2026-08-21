from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AIWorkspaceReport(BaseModel):
    """A persisted multi-step AI analysis result (e.g. "what's blocking
    this order") - a real, viewable Woodful artifact connected to real
    data, not a one-off chat message that disappears. findings is a
    JSON-encoded string of the structured result (risk_level, reasons,
    per-dimension detail) so it can be redisplayed without recomputing,
    and so a master/employee viewing it later sees exactly what was
    found, not a live re-query that could drift."""
    __tablename__ = "ai_workspace_reports"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    risk_level = Column(String(20), nullable=False)  # ON_TRACK / AT_RISK
    findings = Column(Text, nullable=False)  # JSON-encoded structured result
    requested_by = Column(String(255), nullable=True)

    order = relationship("Order")
