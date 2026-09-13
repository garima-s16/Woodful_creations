"""Audit log model, response schema, and the log_action write helper -
kept together since all three exist only to serve each other, and
splitting them into separate model/schema files added navigation
overhead without a real boundary."""
import logging
from decimal import Decimal
from typing import Optional, Any
from datetime import datetime

from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Session

from app.platform.database import Base

logger = logging.getLogger(__name__)


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
    """Writes one audit trail row.

    Defect repair (F138 P12): every call site across this codebase
    invokes log_action() AFTER its own business mutation has already
    committed (e.g. catalog/api.py's create_product: db.commit(),
    db.refresh(product), THEN log_action(...) - the same order repeats
    across sales/hr/auth/procurement/etc). This function used to raise
    straight through on any failure of its OWN db.commit() - a
    transient DB blip, a serialization edge case, anything - which the
    unhandled-exception handler (app/main.py) turns into a 500. From
    the caller's point of view the whole request looks like it failed,
    even though the real business data was already safely committed
    moments earlier - inviting a client retry that duplicates the
    already-committed mutation (a second product, a second payment,
    ...). The audit trail matters, but it must never be able to turn an
    already-successful mutation into an apparent failure: best-effort
    here means log and swallow, not raise. A caller that genuinely
    needs to know whether the audit write itself succeeded has no such
    caller today (log_action's return type has always been None) - if
    one is ever added, it should check a return value instead of
    catching an exception from this function.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        module_name=module_name,
        record_id=record_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=request.client.host if request.client else None,
    )
    try:
        db.add(entry)
        db.commit()
    except Exception:
        # Roll back so this session's transaction state is left clean
        # for whatever the caller does next (many call sites read
        # already-committed attributes right after this call, e.g. via
        # a response model) - rollback expires already-loaded objects,
        # which just means their next attribute access re-fetches from
        # the DB (a cheap extra query), not a correctness problem,
        # since the business row itself is already durably committed.
        db.rollback()
        logger.error(
            "Audit log write failed (best-effort, not raised): user_id=%s action=%s "
            "module=%s record_id=%s", user_id, action, module_name, record_id, exc_info=True,
        )
