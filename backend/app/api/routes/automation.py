from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models.automation_log import AutomationLog
from app.schemas.automation import AutomationLogResponse, AutomationRuleInfo, AutomationRunResult
from app.services.automation_service import AutomationService

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("/rules", response_model=List[AutomationRuleInfo])
def list_rules(auth=Depends(require_role("master"))):
    """The EVENT -> ACTION registry itself - static, not a DB query, so
    the frontend can show what automation exists without needing a log
    entry to have fired yet."""
    return AutomationService.RULES


@router.get("/logs", response_model=List[AutomationLogResponse])
def list_logs(rule_key: Optional[str] = Query(None), status: Optional[str] = Query(None),
              related_entity_type: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=500),
              db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Master-only, same as audit-logs - this is an internal operations
    trail, not a user-facing feed (that's Notification, already visible
    per its own RBAC in notifications.py)."""
    query = db.query(AutomationLog)
    if rule_key:
        query = query.filter(AutomationLog.rule_key == rule_key)
    if status:
        query = query.filter(AutomationLog.status == status)
    if related_entity_type:
        query = query.filter(AutomationLog.related_entity_type == related_entity_type)
    return query.order_by(AutomationLog.created_at.desc()).limit(limit).all()


@router.post("/run", response_model=AutomationRunResult)
def run_automation(source: str = Query("scheduled_job", pattern="^(scheduled_job|manual_trigger)$"),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Evaluates every rule right now. This app has no in-process
    background scheduler (see AutomationService's module docstring), so
    this is the endpoint a real external scheduler (cron, a hosting
    platform's scheduled task) should call periodically - source defaults
    to "scheduled_job" for that case; the frontend can pass
    source=manual_trigger for an explicit "Run now" button. Idempotent:
    calling this twice in a row with nothing new in between logs 0 the
    second time."""
    before_count = db.query(AutomationLog).count()
    AutomationService.run_all(db, trigger_event=source)
    after_count = db.query(AutomationLog).count()
    return AutomationRunResult(trigger_event=source, logged=after_count - before_count)
