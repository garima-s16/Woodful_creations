from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.core.rate_limit import rate_limit
from app.core.config import settings
from app.models.integration_sync_log import IntegrationSyncLog, EXTERNAL_SYSTEMS, SYNCABLE_ENTITY_TYPES
from app.schemas.integration_sync_log import IntegrationSyncLogResponse, SyncTriggerRequest
from app.services.integration_service import IntegrationService, ADAPTERS

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/status")
def integration_status(auth=Depends(require_role("master"))):
    """Honest, per-system configuration status - never a credential
    value, just whether one is present. Lets a master account confirm
    at a glance that nothing is (or is not) wired up, without ever
    exposing what the actual key is."""
    return {
        system: {"configured": adapter.is_configured(), "external_system": system}
        for system, adapter in ADAPTERS.items()
    }


@router.post("/{external_system}/{entity_type}/{entity_id}/sync", response_model=IntegrationSyncLogResponse,
             dependencies=[Depends(rate_limit("chat", settings.RATE_LIMIT_CHAT_PER_MINUTE))])
def trigger_sync(external_system: str, entity_type: str, entity_id: int, data: Optional[SyncTriggerRequest] = None,
                  db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    if external_system not in EXTERNAL_SYSTEMS:
        raise HTTPException(status_code=400, detail=f"Unknown system '{external_system}'. Must be one of: {sorted(EXTERNAL_SYSTEMS)}")
    if entity_type not in SYNCABLE_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"'{entity_type}' is not syncable. Must be one of: {sorted(SYNCABLE_ENTITY_TYPES)}")
    try:
        return IntegrationService.sync_entity(
            db, external_system, entity_type, entity_id,
            triggered_by_user_id=auth.get("user_id"), force=(data.force if data else False),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/logs", response_model=List[IntegrationSyncLogResponse])
def list_sync_logs(external_system: Optional[str] = Query(None), entity_type: Optional[str] = Query(None),
                    entity_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Master-only, matching how audit logs are already master-only
    throughout this app - this is a similarly sensitive operational log."""
    query = db.query(IntegrationSyncLog)
    if external_system:
        query = query.filter(IntegrationSyncLog.external_system == external_system)
    if entity_type:
        query = query.filter(IntegrationSyncLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(IntegrationSyncLog.entity_id == entity_id)
    if status:
        query = query.filter(IntegrationSyncLog.status == status)
    return query.order_by(IntegrationSyncLog.created_at.desc()).limit(200).all()
