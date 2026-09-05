from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.operations.models import ProductionJob
from app.modules.operations.schemas import ProductionJobCreate, ProductionJobUpdate, ProductionJobResponse
from app.platform.database.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/production-jobs", tags=["production-jobs"])

# Matching DailyTask's exact established pattern: any employee can
# update the direct work-progress fields on any job (jobs are visible
# to everyone, not restricted to the assigned operator) - but planning
# fields (stage, remarks, which employee/machine is assigned) remain
# master-only.
EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "completed_qty", "blocker_reason"}


@router.get("/", response_model=List[ProductionJobResponse])
def list_production_jobs(order_id: Optional[int] = Query(None), machine: Optional[str] = Query(None),
                          date: Optional[datetime] = Query(None),
                          open_longer_than_days: Optional[int] = Query(None, ge=1, le=365),
                          limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                          db: Session = Depends(get_db),
                          auth=Depends(get_current_user)):
    query = db.query(ProductionJob)
    if order_id:
        query = query.filter(ProductionJob.order_id == order_id)
    if machine:
        query = query.filter(ProductionJob.machine == machine)
    if date:
        query = query.filter(ProductionJob.date == date)
    if open_longer_than_days is not None:
        # Dashboard "delayed production" widget - was previously
        # productionJobsAPI.list() with NO filter (the entire table)
        # filtered client-side in React. There is no
        # planned-completion-date field on ProductionJob, so "open 7+
        # days" is the same stated approximation the frontend used,
        # just moved into SQL so it composes with limit/offset below.
        cutoff = datetime.utcnow() - timedelta(days=open_longer_than_days)
        query = query.filter(ProductionJob.status != "Completed", ProductionJob.date < cutoff)
    query = query.order_by(ProductionJob.date.desc())
    if limit is not None:
        # Optional and unbounded by default on purpose -
        # ProductionJobsPage renders the full list with no client-side
        # pagination of its own, so a default limit here would silently
        # truncate that page. Only callers that explicitly ask (the
        # dashboard) get a bounded result.
        query = query.offset(offset).limit(limit)
    return query.all()


@router.post("/", response_model=ProductionJobResponse, status_code=201)
def create_production_job(data: ProductionJobCreate, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
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

    if data.completed_qty is not None and data.completed_qty > job.planned_qty:
        raise HTTPException(
            status_code=400,
            detail=f"Completed quantity ({data.completed_qty}) cannot exceed this job's planned quantity ({job.planned_qty})",
        )

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
