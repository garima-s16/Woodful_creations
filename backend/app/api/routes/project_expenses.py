from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models.project_expense import ProjectExpense
from app.schemas.project_expense import ProjectExpenseCreate, ProjectExpenseResponse

router = APIRouter(prefix="/api/project-expenses", tags=["project-expenses"])


@router.get("/", response_model=List[ProjectExpenseResponse])
def list_project_expenses(order_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                           auth=Depends(require_role("master", "manager"))):
    query = db.query(ProjectExpense)
    if order_id:
        query = query.filter(ProjectExpense.order_id == order_id)
    return query.order_by(ProjectExpense.date.desc()).all()


@router.post("/", response_model=ProjectExpenseResponse, status_code=201)
def create_project_expense(data: ProjectExpenseCreate, db: Session = Depends(get_db),
                            auth=Depends(require_role("master", "manager"))):
    if db.query(ProjectExpense).filter(ProjectExpense.expense_code == data.expense_code).first():
        raise HTTPException(status_code=400, detail="Expense code already exists")
    expense = ProjectExpense(**data.dict())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/{expense_id}", response_model=ProjectExpenseResponse)
def get_project_expense(expense_id: int, db: Session = Depends(get_db),
                         auth=Depends(require_role("master", "manager"))):
    expense = db.query(ProjectExpense).filter(ProjectExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense
