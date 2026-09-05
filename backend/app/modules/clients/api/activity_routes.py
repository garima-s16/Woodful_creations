from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload

from app.platform.audit.audit import log_action
from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.clients.models import Client, ClientActivity
from app.modules.clients.schemas import ClientActivityCreate, ClientActivityUpdate, ClientActivityResponse

router = APIRouter(prefix="/api/client-activities", tags=["client-activities"])


@router.get("/", response_model=List[ClientActivityResponse])
def list_client_activities(client_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                            auth=Depends(get_current_user)):
    query = db.query(ClientActivity)
    if client_id:
        query = query.filter(ClientActivity.client_id == client_id)
    return query.order_by(ClientActivity.date.desc()).all()


@router.get("/follow-ups")
def list_pending_follow_ups(
    within_days: int = Query(7, ge=0, le=365, description="Include follow-ups due within this many days (overdue always included)"),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Overdue-or-upcoming, not-yet-completed follow-ups, with the
    client name/code so a dashboard widget doesn't need a second
    round trip per row."""
    cutoff = datetime.utcnow() + timedelta(days=within_days)
    activities = (
        db.query(ClientActivity)
        .options(selectinload(ClientActivity.client))
        .filter(
            ClientActivity.follow_up_date.isnot(None),
            ClientActivity.follow_up_date <= cutoff,
            ClientActivity.follow_up_done.is_(False),
        )
        .order_by(ClientActivity.follow_up_date.asc())
        .all()
    )
    now = datetime.utcnow()
    return [
        {
            "id": a.id,
            "client_id": a.client_id,
            "client_name": a.client.name if a.client else None,
            "client_code": a.client.client_code if a.client else None,
            "activity_type": a.activity_type,
            "summary": a.summary,
            "follow_up_date": a.follow_up_date,
            "overdue": a.follow_up_date < now if a.follow_up_date else False,
        }
        for a in activities
    ]


@router.post("/", response_model=ClientActivityResponse, status_code=201)
def log_client_activity(data: ClientActivityCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(Client).filter(Client.id == data.client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")
    activity = ClientActivity(**data.dict())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.patch("/{activity_id}/complete-follow-up", response_model=ClientActivityResponse)
def complete_follow_up(activity_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.follow_up_date is None:
        raise HTTPException(status_code=400, detail="This activity has no follow-up to complete")
    activity.follow_up_done = True
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.get("/{activity_id}", response_model=ClientActivityResponse)
def get_client_activity(activity_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@router.put("/{activity_id}", response_model=ClientActivityResponse)
def update_client_activity(activity_id: int, data: ClientActivityUpdate, db: Session = Depends(get_db),
                            auth=Depends(get_current_user)):
    """A mis-logged call/meeting note (wrong date, typo'd summary) had
    no way to ever be corrected before this - only re-logged as a new,
    separate entry, leaving the wrong one sitting in the client's
    history permanently."""
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(activity, field, value)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=204)
def delete_client_activity(activity_id: int, request: Request, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    old_value = {"client_id": activity.client_id, "summary": activity.summary, "date": str(activity.date)}
    db.delete(activity)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_client_activity", module_name="clients",
               record_id=activity_id, old_value=old_value)
