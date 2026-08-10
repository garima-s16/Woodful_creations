from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.production_job import ProductionJob
from app.schemas.production_job import ProductionJobCreate, ProductionJobUpdate, ProductionJobResponse

router = APIRouter(prefix="/api/production-jobs", tags=["production-jobs"])


@router.get("/", response_model=List[ProductionJobResponse])
def list_production_jobs(order_id: Optional[int] = Query(None), machine: Optional[str] = Query(None),
                          date: Optional[datetime] = Query(None), db: Session = Depends(get_db),
                          auth=Depends(get_current_user)):
    query = db.query(ProductionJob)
    if order_id:
        query = query.filter(ProductionJob.order_id == order_id)
    if machine:
        query = query.filter(ProductionJob.machine == machine)
    if date:
        query = query.filter(ProductionJob.date == date)
    return query.order_by(ProductionJob.date.desc()).all()


@router.post("/", response_model=ProductionJobResponse, status_code=201)
def create_production_job(data: ProductionJobCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if db.query(ProductionJob).filter(ProductionJob.job_code == data.job_code).first():
        raise HTTPException(status_code=400, detail="Job code already exists")
    job = ProductionJob(**data.dict())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.put("/{job_id}", response_model=ProductionJobResponse)
def update_production_job(job_id: int, data: ProductionJobUpdate, db: Session = Depends(get_db),
                           auth=Depends(get_current_user)):
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(job, field, value)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
