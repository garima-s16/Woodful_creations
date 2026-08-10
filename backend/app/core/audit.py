"""Helper for writing to the audit_logs table."""
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


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
