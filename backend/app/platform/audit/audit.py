"""Audit log model, response schema, and the log_action write helper -
kept together since all three exist only to serve each other, and
splitting them into separate model/schema files added navigation
overhead without a real boundary."""
from decimal import Decimal
from typing import Optional, Any
from datetime import datetime

from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Session

from app.platform.database.database import Base


class AuditLog(Base):
    """Audit log model for tracking all changes"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    module_name = Column(String(100), nullable=False, index=True)
    record_id = Column(Integer, nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    module_name: str
    record_id: Optional[int]
    old_value: Optional[Any]
    new_value: Optional[Any]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


def serializable_fields(obj, field_names) -> dict:
    """Snapshot of the given attributes on a SQLAlchemy model, safe to
    store in the audit log's JSON columns. Numeric columns return
    Decimal, which json.dumps cannot serialize on its own (it's not a
    subclass of int/float) - every caller needing an old/new value
    snapshot for a mutation should use this rather than reimplement
    the same conversion."""
    result = {}
    for name in field_names:
        value = getattr(obj, name)
        result[name] = float(value) if isinstance(value, Decimal) else value
    return result


def log_action(
    db: Session,
    request: Request,
    user_id: Optional[int],
    action: str,
    module_name: str,
    record_id: Optional[int] = None,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        module_name=module_name,
        record_id=record_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=request.client.host if request.client else None,
    )
    db.add(entry)
    db.commit()
