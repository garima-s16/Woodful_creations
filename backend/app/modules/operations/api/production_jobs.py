from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.operations.models import ProductionJob, WorkCentre
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


@router.get("/{job_id}/material-status")
def get_production_job_material_status(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Phase D dependency-aware planning: is this job blocked by a real
    material shortage? Reuses StockService.calculate_order_material_requirements
    for the job's own order (single authoritative shortage calculation,
    same one the Orders module uses) and looks up just this job's
    material_id in the result - no separate shortage logic here.

    A job with no order_id or no material_id has nothing to check
    (most production jobs - cutting/CNC/assembly - are tied to one
    specific material; a job that isn't returns has_shortage_data=False
    rather than a fabricated answer)."""
    from app.modules.inventory.stock_service import StockService

    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")

    if not job.order_id or not job.material_id:
        return {"job_id": job_id, "has_shortage_data": False, "material_id": job.material_id, "is_blocked_by_shortage": False}

    result = StockService.calculate_order_material_requirements(db, job.order_id)
    for row in result["materials"]:
        if row["material_id"] == job.material_id:
            return {
                "job_id": job_id, "has_shortage_data": True, "material_id": job.material_id,
                "material_name": row["material_name"], "required": row["required"], "available": row["available"],
                "shortage": row["shortage"], "is_blocked_by_shortage": row["shortage"] > 0,
                "recommended_purchase_quantity": row["recommended_purchase_quantity"],
                "supplier_options": row["supplier_options"],
            }
    # The job's material isn't in its own order's BOM shortage list at
    # all (e.g. the order's product has no BOM entry for it) - nothing
    # to report, not a fabricated zero.
    return {"job_id": job_id, "has_shortage_data": False, "material_id": job.material_id, "is_blocked_by_shortage": False}


def _determine_job_readiness(db: Session, job: ProductionJob) -> dict:
    """READY / PARTIALLY_READY / BLOCKED, with a real, explained reason -
    never a fabricated one. Deliberately does not produce an AT_RISK
    result here: that would require real capacity/schedule data (work
    centres, operation durations, existing scheduled load), which does
    not exist yet in this codebase - inventing a plausible-sounding
    "schedule risk" without that data would be exactly the fabricated
    readiness result section 2 explicitly forbids. AT_RISK becomes
    honest once capacity/scheduling is actually implemented."""
    if job.status == "Completed":
        return {"readiness": "READY", "reason": "This job is already completed."}

    if job.blocker_reason:
        return {"readiness": "BLOCKED", "reason": job.blocker_reason}

    if not job.order_id or not job.material_id:
        return {
            "readiness": "READY",
            "reason": "This job has no linked order/material to check readiness against.",
        }

    from app.modules.inventory.stock_service import StockService
    result = StockService.calculate_order_material_requirements(db, job.order_id)
    for row in result["materials"]:
        if row["material_id"] != job.material_id:
            continue
        if row["available"] >= row["required"]:
            return {
                "readiness": "READY",
                "reason": f"{row['material_name']} is fully available ({row['available']} {row['unit']} on hand).",
            }
        if row["shortage"] <= 0:
            # Physically short right now, but the gap is fully covered
            # by a purchase already placed - not yet in stock, so the
            # job cannot actually start cutting on it yet, even though
            # the shortage figure itself (correctly, for planning
            # purposes) already nets the incoming quantity out to zero.
            return {
                "readiness": "PARTIALLY_READY",
                "reason": (
                    f"{row['material_name']} is short by {row['gap_before_pending_supply']} {row['unit']} in "
                    f"physical stock right now, but {row['pending_purchase_quantity']} {row['unit']} is already "
                    f"on order and covers the gap once received."
                ),
            }
        top_supplier = row["supplier_options"][0]["supplier_name"] if row["supplier_options"] else None
        reason = (
            f"{row['material_name']} is short by {row['shortage']} {row['unit']} even after "
            f"{row['pending_purchase_quantity']} {row['unit']} already on order is accounted for."
        )
        if top_supplier:
            reason += f" {top_supplier} can supply this."
        return {"readiness": "BLOCKED", "reason": reason}

    # This job's material isn't in its own order's BOM shortage list at
    # all (e.g. the order's product has no BOM entry for it) - nothing
    # to check, not a fabricated READY.
    return {
        "readiness": "READY",
        "reason": "No material requirement is recorded against this job's order for its linked material.",
    }


@router.get("/{job_id}/readiness")
def get_production_job_readiness(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")
    return {"job_id": job_id, **_determine_job_readiness(db, job)}


@router.get("/{job_id}/variance")
def get_production_job_variance(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Planned vs Actual (P0.3 section 27/28) - never invents an actual
    value: duration variance is computed only from operations that
    actually have actual_duration_minutes recorded, and duration_complete
    tells the caller whether that covers every operation or only some
    of them, so a partial variance is never mistaken for the final one."""
    job = db.query(ProductionJob).options(joinedload(ProductionJob.operations)).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")

    quantity_variance = job.completed_qty - job.planned_qty
    quantity_variance_percent = round((quantity_variance / job.planned_qty) * 100, 1) if job.planned_qty else None

    operations_with_actual = [op for op in job.operations if op.actual_duration_minutes is not None]
    duration_planned_minutes = sum(op.estimated_duration_minutes or 0 for op in job.operations)
    duration_actual_minutes = sum(op.actual_duration_minutes for op in operations_with_actual)
    # Only meaningful once at least one operation actually has a real
    # actual_duration_minutes - with none, there is nothing to compare
    # against yet, not a variance of zero.
    duration_variance_minutes = (duration_actual_minutes - sum(
        op.estimated_duration_minutes or 0 for op in operations_with_actual
    )) if operations_with_actual else None

    return {
        "job_id": job_id,
        "quantity_planned": job.planned_qty, "quantity_completed": job.completed_qty,
        "quantity_variance": quantity_variance, "quantity_variance_percent": quantity_variance_percent,
        "duration_planned_minutes": duration_planned_minutes,
        "duration_actual_minutes": duration_actual_minutes if operations_with_actual else None,
        "duration_variance_minutes": duration_variance_minutes,
        "operations_total": len(job.operations), "operations_with_actual_duration": len(operations_with_actual),
        "duration_complete": len(operations_with_actual) == len(job.operations) and len(job.operations) > 0,
    }


@router.get("/{job_id}/risks")
def get_production_job_risks(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Production Risk (P0.3 section 29): a list of real, individually
    explained findings (type/what/why/impact), never a single opaque
    score. Only reports a risk where real data actually supports it -
    covers material shortage, dependency blockage, work-centre capacity
    overload, and order delivery-date risk. Deliberately does NOT claim
    procurement-delay/late-receipt or "overdue operation" risk:
    ProductionJob has no direct link to a ProcurementRequirement to
    check delay against, and ProductionOperation has no planned-end
    field to compare an actual against - inventing either would be
    exactly the fabricated risk this endpoint must not produce. An
    empty list is a real, honest "no risk found from the data this
    endpoint can check", not a claim that nothing could ever go wrong."""
    job = db.query(ProductionJob).options(joinedload(ProductionJob.operations), joinedload(ProductionJob.order)).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")

    risks = []
    if job.status != "Completed":
        readiness = _determine_job_readiness(db, job)
        if readiness["readiness"] != "READY":
            risks.append({
                "type": "material_shortage", "severity": "high" if readiness["readiness"] == "BLOCKED" else "medium",
                "what": f"Material readiness is {readiness['readiness']}.",
                "why": readiness["reason"],
                "impact": "This job cannot physically proceed on this material until the shortage is resolved."
                          if readiness["readiness"] == "BLOCKED" else
                          "This job cannot start yet - the covering stock has not physically arrived.",
            })

        blocked_ops = [op for op in job.operations if op.is_blocked_by_dependency]
        for op in blocked_ops:
            risks.append({
                "type": "dependency_blockage", "severity": "medium",
                "what": f'"{op.operation_name}" is waiting on a predecessor.',
                "why": f'Depends on "{op.depends_on.operation_name}", which is still {op.depends_on.status}.',
                "impact": f'"{op.operation_name}" cannot start until its predecessor completes.',
            })

        from app.modules.operations.models import ProductionOperation
        checked_centres = set()
        for op in job.operations:
            if not op.work_centre_id or not op.start_time or op.work_centre_id in checked_centres:
                continue
            checked_centres.add(op.work_centre_id)
            centre = db.query(WorkCentre).filter(WorkCentre.id == op.work_centre_id).first()
            if not centre or centre.capacity_hours_per_day is None:
                continue
            target_date = op.start_time.date()
            same_day_ops = db.query(ProductionOperation).filter(
                ProductionOperation.work_centre_id == op.work_centre_id,
                ProductionOperation.status != "Completed",
            ).all()
            scheduled_minutes = sum(
                (o.estimated_duration_minutes or 0) for o in same_day_ops
                if o.start_time and o.start_time.date() == target_date
            )
            capacity_minutes = float(centre.capacity_hours_per_day) * 60
            if scheduled_minutes > capacity_minutes:
                risks.append({
                    "type": "capacity_overload", "severity": "medium",
                    "what": f'"{centre.name}" is over capacity on {target_date.isoformat()}.',
                    "why": f"{scheduled_minutes} minutes of work scheduled against a {capacity_minutes:.0f}-minute daily capacity.",
                    "impact": "Some operations at this work centre on this date will not finish as planned.",
                    "when": target_date.isoformat(),
                })

        if job.order and job.order.delivery_date:
            from datetime import datetime as dt
            days_remaining = (job.order.delivery_date - dt.utcnow()).days
            if days_remaining < 0:
                risks.append({
                    "type": "schedule_risk", "severity": "high",
                    "what": f"{job.order.order_code}'s delivery date has already passed.",
                    "why": f"Delivery was due {job.order.delivery_date.date().isoformat()}, {abs(days_remaining)} day(s) ago, and this job is still {job.status}.",
                    "impact": "The client-facing delivery commitment is already missed.",
                    "when": job.order.delivery_date.date().isoformat(),
                })
            elif days_remaining <= 3:
                risks.append({
                    "type": "schedule_risk", "severity": "medium",
                    "what": f"{job.order.order_code}'s delivery date is imminent.",
                    "why": f"Delivery is due {job.order.delivery_date.date().isoformat()} ({days_remaining} day(s) away) and this job is still {job.status}.",
                    "impact": "There is little buffer left before the delivery commitment is missed.",
                    "when": job.order.delivery_date.date().isoformat(),
                })

    return {"job_id": job_id, "risks": risks}


@router.put("/{job_id}", response_model=ProductionJobResponse)
def update_production_job(job_id: int, data: ProductionJobUpdate, db: Session = Depends(get_db),
                           auth=Depends(get_current_user)):
    # Locked before checking/setting status - two simultaneous updates
    # to the same job (a double-tap marking it Completed, or two
    # operators both submitting a status change) must not both read
    # the same pre-update status and both think they were first.
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).with_for_update().first()
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
