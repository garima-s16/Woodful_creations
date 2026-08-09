from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.issue import MaterialIssue
from app.schemas.issue import MaterialIssueCreate, MaterialIssueUpdate, MaterialIssueResponse
from app.services.stock_service import StockService
from typing import List

router = APIRouter(prefix="/api/issues", tags=["Material Issues"])

@router.get("/", response_model=List[MaterialIssueResponse])
async def get_issues(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    project_id: int = Query(None),
    department: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(MaterialIssue)
    if project_id:
        query = query.filter(MaterialIssue.project_id == project_id)
    if department:
        query = query.filter(MaterialIssue.department == department)
    issues = query.offset(skip).limit(limit).all()
    return issues

@router.post("/", response_model=MaterialIssueResponse, status_code=201)
async def create_issue(issue: MaterialIssueCreate, db: Session = Depends(get_db)):
    existing = db.query(MaterialIssue).filter(MaterialIssue.issue_id == issue.issue_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Issue ID already exists")
    
    try:
        StockService.update_stock_on_issue(db, issue.material_id, issue.quantity_issued)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    db_issue = MaterialIssue(**issue.dict())
    db.add(db_issue)
    db.commit()
    db.refresh(db_issue)
    return db_issue

@router.get("/{issue_id}", response_model=MaterialIssueResponse)
async def get_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(MaterialIssue).filter(MaterialIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Material issue not found")
    return issue

@router.put("/{issue_id}", response_model=MaterialIssueResponse)
async def update_issue(issue_id: int, issue_update: MaterialIssueUpdate, db: Session = Depends(get_db)):
    issue = db.query(MaterialIssue).filter(MaterialIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Material issue not found")
    
    update_data = issue_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(issue, field, value)
    
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue

@router.get("/project/{project_id}/issues", response_model=List[MaterialIssueResponse])
async def get_project_issues(project_id: int, db: Session = Depends(get_db)):
    issues = db.query(MaterialIssue).filter(MaterialIssue.project_id == project_id).all()
    return issues

@router.delete("/{issue_id}")
async def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(MaterialIssue).filter(MaterialIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Material issue not found")
    
    db.delete(issue)
    db.commit()
    return {"message": "Material issue deleted successfully"}
