from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import require_role
from app.models.project_expense import ProjectExpense
from app.schemas.project_expense import ProjectExpenseCreate, ProjectExpenseUpdate, ProjectExpenseResponse
from app.utils.id_generator import generate_unique_code

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
    payload = data.dict(exclude={"expense_code"})
    for _ in range(5):
        code = generate_unique_code(db, ProjectExpense, "expense_code", "EXP-")
        expense = ProjectExpense(**payload, expense_code=code)
        db.add(expense)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(expense)
        return expense
    raise HTTPException(status_code=500, detail="Unable to generate a unique expense code, please try again")


@router.get("/{expense_id}", response_model=ProjectExpenseResponse)
def get_project_expense(expense_id: int, db: Session = Depends(get_db),
                         auth=Depends(require_role("master", "manager"))):
    expense = db.query(ProjectExpense).filter(ProjectExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.put("/{expense_id}", response_model=ProjectExpenseResponse)
def update_project_expense(expense_id: int, data: ProjectExpenseUpdate, db: Session = Depends(get_db),
                            auth=Depends(require_role("master", "manager"))):
    expense = db.query(ProjectExpense).filter(ProjectExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(expense, field, value)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense
