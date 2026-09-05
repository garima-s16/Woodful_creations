from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import require_role
from app.platform.audit.audit import AuditLog, AuditLogResponse

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])


@router.get("/", response_model=List[AuditLogResponse])
def list_audit_logs(
    module_name: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    auth=Depends(require_role("master")),
):
    query = db.query(AuditLog)
    if module_name:
        query = query.filter(AuditLog.module_name == module_name)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
