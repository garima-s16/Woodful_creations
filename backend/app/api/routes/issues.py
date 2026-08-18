from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.issue import Issue
from app.schemas.issue import IssueCreate, IssueResponse
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("/", response_model=List[IssueResponse])
def list_issues(order_id: Optional[int] = Query(None), material_id: Optional[int] = Query(None),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Issue)
    if order_id:
        query = query.filter(Issue.order_id == order_id)
    if material_id:
        query = query.filter(Issue.material_id == material_id)
    return query.order_by(Issue.date.desc()).all()


@router.post("/", response_model=IssueResponse, status_code=201)
def create_issue(data: IssueCreate, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    return StockService.record_issue(db, data)


@router.get("/{issue_id}", response_model=IssueResponse)
def get_issue(issue_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue
