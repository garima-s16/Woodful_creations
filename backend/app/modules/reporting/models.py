"""Reporting domain models: AIWorkspaceReport (persisted AI analysis
artifacts) and ReportHistory (report-generation event metadata,
15-day retention)."""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from app.platform.database.base import BaseModel


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


class ReportHistory(BaseModel):
    """Lightweight metadata recording that a
    report was generated, kept for the existing 15-day retention
    requirement. This table holds only metadata about the report
    generation event itself (report_date, generated_at, report_type,
    storage_identity) - never the report's own content, and never any
    underlying business record (tasks, orders, etc - those are
    untouched by this table's retention). Rows older than 15 days are
    safe to expire since they are history-of-a-generation-event, not a
    business record in their own right."""
    __tablename__ = "report_history"

    report_type = Column(String(50), nullable=False, index=True)  # e.g. "daily_status_report"
    report_date = Column(DateTime, nullable=False)  # the date the report covers
    generated_at = Column(DateTime, nullable=False)  # when this generation event happened
    # Where the generated artifact was delivered/would be found - e.g.
    # "email:master@example.com,other@example.com" or "download" for an
    # on-demand Excel response that was streamed and never persisted to
    # storage. Not a StorageReference - no report artifact is currently
    # persisted to disk/Drive by this app (Excel is generated and
    # streamed in-memory), so this column records the delivery identity
    # actually available today rather than inventing a storage path
    # nothing writes to.
    storage_identity = Column(String(255), nullable=True)
