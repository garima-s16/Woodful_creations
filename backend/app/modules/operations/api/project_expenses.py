from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action, serializable_fields
from app.modules.operations.models import ProjectExpense
from app.modules.operations.schemas import ProjectExpenseCreate, ProjectExpenseUpdate, ProjectExpenseResponse
from app.platform.database.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/project-expenses", tags=["project-expenses"])


@router.get("/", response_model=List[ProjectExpenseResponse])
def list_project_expenses(order_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    query = db.query(ProjectExpense)
    if order_id:
        query = query.filter(ProjectExpense.order_id == order_id)
    return query.order_by(ProjectExpense.date.desc()).all()


@router.post("/", response_model=ProjectExpenseResponse, status_code=201)
def create_project_expense(data: ProjectExpenseCreate, request: Request, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"expense_code"})
    for _ in range(5):
        code = generate_unique_code(db, ProjectExpense, "expense_code", "EXP-")
        expense = ProjectExpense(**payload, expense_code=code, business_id=generate_business_id(db))
        db.add(expense)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(expense)
        log_action(db, request, user_id=auth.get("user_id"), action="create_project_expense",
                   module_name="project_expenses", record_id=expense.id, new_value={
                       "order_id": expense.order_id, "category": expense.category,
                       "amount": float(expense.amount or 0),
                   })
        return expense
    raise HTTPException(status_code=500, detail="Unable to generate a unique expense code, please try again")


@router.get("/{expense_id}", response_model=ProjectExpenseResponse)
def get_project_expense(expense_id: int, db: Session = Depends(get_db),
                         auth=Depends(require_role("master"))):
    expense = db.query(ProjectExpense).filter(ProjectExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.put("/{expense_id}", response_model=ProjectExpenseResponse)
def update_project_expense(expense_id: int, data: ProjectExpenseUpdate, request: Request, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    expense = db.query(ProjectExpense).filter(ProjectExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    updates = data.dict(exclude_unset=True)
    old_value = serializable_fields(expense, updates.keys())
    for field, value in updates.items():
        setattr(expense, field, value)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    log_action(db, request, user_id=auth.get("user_id"), action="update_project_expense",
               module_name="project_expenses", record_id=expense.id, old_value=old_value,
               new_value=serializable_fields(expense, updates.keys()))
    return expense
