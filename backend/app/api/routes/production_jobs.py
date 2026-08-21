from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.production_job import ProductionJob
from app.schemas.production_job import ProductionJobCreate, ProductionJobUpdate, ProductionJobResponse
from app.utils.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/production-jobs", tags=["production-jobs"])

# Matching DailyTask's exact established pattern: any employee can
# update the direct work-progress fields on any job (jobs are visible
# to everyone, not restricted to the assigned operator) - but planning
# fields (stage, remarks, which employee/machine is assigned) remain
# master-only.
EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "completed_qty", "blocker_reason"}


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
        job = ProductionJob(**payload, job_code=code, business_id=generate_business_id(db))
        db.add(job)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(job)
        return job
    raise HTTPException(status_code=500, detail="Unable to generate a unique job code, please try again")


@router.get("/{job_id}", response_model=ProductionJobResponse)
def get_production_job(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")
    return job


@router.put("/{job_id}", response_model=ProductionJobResponse)
def update_production_job(job_id: int, data: ProductionJobUpdate, db: Session = Depends(get_db),
                           auth=Depends(get_current_user)):
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    role = auth.get("role", "user")
    update_data = data.dict(exclude_unset=True)

    if role not in ("master",):
        disallowed = set(update_data.keys()) - EMPLOYEE_SELF_SERVICE_FIELDS
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail=f"You can only update: {', '.join(sorted(EMPLOYEE_SELF_SERVICE_FIELDS))}. "
                       f"Not allowed to change: {', '.join(sorted(disallowed))}.",
            )

    if update_data.get("status") == "Completed" and job.status != "Completed":
        update_data["completion_date"] = datetime.utcnow()
    for field, value in update_data.items():
        setattr(job, field, value)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
