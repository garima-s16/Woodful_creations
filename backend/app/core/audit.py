"""Helper for writing to the audit_logs table."""
from decimal import Decimal
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


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
