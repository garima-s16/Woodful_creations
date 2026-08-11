from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.client_activity import ClientActivity
from app.schemas.client_activity import ClientActivityCreate, ClientActivityResponse

router = APIRouter(prefix="/api/client-activities", tags=["client-activities"])


@router.get("/", response_model=List[ClientActivityResponse])
def list_client_activities(client_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                            auth=Depends(get_current_user)):
    query = db.query(ClientActivity)
    if client_id:
        query = query.filter(ClientActivity.client_id == client_id)
    return query.order_by(ClientActivity.date.desc()).all()


@router.post("/", response_model=ClientActivityResponse, status_code=201)
def log_client_activity(data: ClientActivityCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    activity = ClientActivity(**data.dict())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity
