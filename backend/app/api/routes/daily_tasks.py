from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.daily_task import DailyTask
from app.schemas.daily_task import DailyTaskCreate, DailyTaskUpdate, DailyTaskResponse

router = APIRouter(prefix="/api/daily-tasks", tags=["daily-tasks"])


@router.get("/", response_model=List[DailyTaskResponse])
def list_daily_tasks(employee_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                      date: Optional[datetime] = Query(None), status: Optional[str] = Query(None),
                      db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(DailyTask)
    if employee_id:
        query = query.filter(DailyTask.employee_id == employee_id)
    if order_id:
        query = query.filter(DailyTask.order_id == order_id)
    if date:
        query = query.filter(DailyTask.date == date)
    if status:
        query = query.filter(DailyTask.status == status)
    return query.order_by(DailyTask.date.desc()).all()


@router.post("/", response_model=DailyTaskResponse, status_code=201)
def create_daily_task(data: DailyTaskCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if db.query(DailyTask).filter(DailyTask.task_code == data.task_code).first():
        raise HTTPException(status_code=400, detail="Task code already exists")
    task = DailyTask(**data.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=DailyTaskResponse)
def get_daily_task(task_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    task = db.query(DailyTask).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=DailyTaskResponse)
def update_daily_task(task_id: int, data: DailyTaskUpdate, db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    task = db.query(DailyTask).filter(DailyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(task, field, value)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
