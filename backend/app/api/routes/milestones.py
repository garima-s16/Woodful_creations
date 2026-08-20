from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.audit import log_action
from app.models.milestone import Milestone
from app.models.order import Order
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate, MilestoneResponse
from app.utils.id_generator import generate_short_id

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


@router.get("/", response_model=List[MilestoneResponse])
def list_milestones(order_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(get_current_user)):
    query = db.query(Milestone)
    if order_id:
        query = query.filter(Milestone.order_id == order_id)
    return query.order_by(Milestone.target_date.asc()).all()


@router.post("/", response_model=MilestoneResponse, status_code=201)
def create_milestone(data: MilestoneCreate, request: Request, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    milestone = Milestone(**data.dict(), business_id=generate_short_id(db))
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    log_action(db, request, user_id=auth.get("user_id"), action="create_milestone", module_name="milestones",
               record_id=milestone.id, new_value={"order_id": milestone.order_id, "name": milestone.name})
    return milestone


@router.put("/{milestone_id}", response_model=MilestoneResponse)
def update_milestone(milestone_id: int, data: MilestoneUpdate, request: Request,
                      db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    old_value = {"name": milestone.name, "completed_date": str(milestone.completed_date)}
    for field, value in data.dict(exclude_unset=True).items():
        setattr(milestone, field, value)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    log_action(db, request, user_id=auth.get("user_id"), action="update_milestone", module_name="milestones",
               record_id=milestone.id, old_value=old_value,
               new_value={"name": milestone.name, "completed_date": str(milestone.completed_date)})
    return milestone


@router.delete("/{milestone_id}", status_code=204)
def delete_milestone(milestone_id: int, request: Request, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    old_value = {"order_id": milestone.order_id, "name": milestone.name}
    db.delete(milestone)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_milestone", module_name="milestones",
               record_id=milestone_id, old_value=old_value)
