from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.production_job import ProductionJob
from app.schemas.production_job import ProductionJobCreate, ProductionJobUpdate, ProductionJobResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

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
    payload = data.dict(exclude={"job_code"})
    for _ in range(5):
        code = generate_unique_code(db, ProductionJob, "job_code", "JOB-")
        job = ProductionJob(**payload, job_code=code, business_id=generate_short_id())
        db.add(job)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(job)
        return job
    raise HTTPException(status_code=500, detail="Unable to generate a unique job code, please try again")


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
