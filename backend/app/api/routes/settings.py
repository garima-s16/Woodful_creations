from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.setting import ProjectStatus, Priority, PaymentMode, LeadSource, ProjectType, ExpenseCategory
from app.schemas.setting import (
    ProjectStatusCreate, ProjectStatusResponse,
    PriorityCreate, PriorityResponse,
    PaymentModeCreate, PaymentModeResponse,
    LeadSourceCreate, LeadSourceResponse,
    ProjectTypeCreate, ProjectTypeResponse,
    ExpenseCategoryCreate, ExpenseCategoryResponse
)
from typing import List

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("/project-statuses", response_model=List[ProjectStatusResponse])
async def get_project_statuses(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    statuses = db.query(ProjectStatus).all()
    return statuses

@router.post("/project-statuses", response_model=ProjectStatusResponse)
async def create_project_status(status: ProjectStatusCreate, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    db_status = ProjectStatus(**status.dict())
    db.add(db_status)
    db.commit()
    db.refresh(db_status)
    return db_status

@router.get("/priorities", response_model=List[PriorityResponse])
async def get_priorities(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    priorities = db.query(Priority).all()
    return priorities

@router.post("/priorities", response_model=PriorityResponse)
async def create_priority(priority: PriorityCreate, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    db_priority = Priority(**priority.dict())
    db.add(db_priority)
    db.commit()
    db.refresh(db_priority)
    return db_priority

@router.get("/payment-modes", response_model=List[PaymentModeResponse])
async def get_payment_modes(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    modes = db.query(PaymentMode).all()
    return modes

@router.post("/payment-modes", response_model=PaymentModeResponse)
async def create_payment_mode(mode: PaymentModeCreate, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    db_mode = PaymentMode(**mode.dict())
    db.add(db_mode)
    db.commit()
    db.refresh(db_mode)
    return db_mode

@router.get("/lead-sources", response_model=List[LeadSourceResponse])
async def get_lead_sources(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    sources = db.query(LeadSource).all()
    return sources

@router.post("/lead-sources", response_model=LeadSourceResponse)
async def create_lead_source(source: LeadSourceCreate, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    db_source = LeadSource(**source.dict())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source

@router.get("/project-types", response_model=List[ProjectTypeResponse])
async def get_project_types(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    types = db.query(ProjectType).all()
    return types

@router.post("/project-types", response_model=ProjectTypeResponse)
async def create_project_type(ptype: ProjectTypeCreate, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    db_type = ProjectType(**ptype.dict())
    db.add(db_type)
    db.commit()
    db.refresh(db_type)
    return db_type

@router.get("/expense-categories", response_model=List[ExpenseCategoryResponse])
async def get_expense_categories(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    categories = db.query(ExpenseCategory).all()
    return categories

@router.post("/expense-categories", response_model=ExpenseCategoryResponse)
async def create_expense_category(category: ExpenseCategoryCreate, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    db_category = ExpenseCategory(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.delete("/project-statuses/{status_id}")
async def delete_project_status(status_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    status = db.query(ProjectStatus).filter(ProjectStatus.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Project status not found")
    db.delete(status)
    db.commit()
    return {"message": "Project status deleted successfully"}

@router.delete("/priorities/{priority_id}")
async def delete_priority(priority_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    priority = db.query(Priority).filter(Priority.id == priority_id).first()
    if not priority:
        raise HTTPException(status_code=404, detail="Priority not found")
    db.delete(priority)
    db.commit()
    return {"message": "Priority deleted successfully"}
