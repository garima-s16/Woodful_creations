"""Operations domain API routes (production): production jobs,
production operations, and cutting requirements. Combines the former
production_jobs.py, production_operations.py, and
cutting_requirements.py."""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.modules.operations.models import ProductionJob, WorkCentre, CuttingRequirement
from app.modules.operations.schemas import ProductionJobCreate, ProductionJobUpdate, ProductionJobResponse
from app.modules.operations.services import shelf_nest
from app.platform.ids import generate_unique_code, generate_business_id
from app.modules.operations.models import ProductionOperation, ProductionJob
from app.modules.operations.schemas import ProductionOperationCreate, ProductionOperationUpdate, ProductionOperationResponse
from app.platform.ids import generate_business_id
from sqlalchemy.orm import Session
from app.modules.operations.models import CuttingRequirement, ProductionJob
from app.modules.operations.schemas import CuttingRequirementCreate, CuttingRequirementUpdate, CuttingRequirementResponse


# --- production_jobs.py ---
production_jobs_router = APIRouter(prefix="/api/production-jobs", tags=["production-jobs"])


EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "completed_qty", "blocker_reason"}


@production_jobs_router.get("/", response_model=List[ProductionJobResponse])
def list_production_jobs(order_id: Optional[int] = Query(None), machine: Optional[str] = Query(None),
                          employee_id: Optional[int] = Query(None),
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
    if employee_id:
        # Defect repair (P1-7) - Employee Detail's Production tab used
        # to fetch productionJobsAPI.list() with NO filter at all (the
        # entire, ever-growing production_jobs table) and filter down
        # to one employee's jobs in React, because this server-side
        # filter did not exist yet (see WorkforcePages.jsx). Same
        # pattern as order_id/machine above.
        query = query.filter(ProductionJob.employee_id == employee_id)
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


@production_jobs_router.post("/", response_model=ProductionJobResponse, status_code=201)
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


@production_jobs_router.get("/{job_id}", response_model=ProductionJobResponse)
def get_production_job(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")
    return job


@production_jobs_router.get("/{job_id}/material-status")
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
    from app.modules.inventory.services import StockService

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

    from app.modules.inventory.services import StockService
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


@production_jobs_router.get("/{job_id}/readiness")
def get_production_job_readiness(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")
    return {"job_id": job_id, **_determine_job_readiness(db, job)}


@production_jobs_router.get("/{job_id}/variance")
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


@production_jobs_router.get("/{job_id}/risks")
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


@production_jobs_router.put("/{job_id}", response_model=ProductionJobResponse)
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


@production_jobs_router.get("/{job_id}/cut-list")
def get_cut_list(job_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Family 131 section 12 - Cut List. Groups this job's real
    CuttingRequirement rows by material/thickness for a printable
    view - never a second, invented data source; every row here is
    the exact same data entered against this job via
    cutting_requirements.py. Grouping only, no fabricated totals."""
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")

    requirements = (
        db.query(CuttingRequirement)
        .options(joinedload(CuttingRequirement.material), joinedload(CuttingRequirement.product))
        .filter(CuttingRequirement.production_job_id == job_id)
        .all()
    )
    groups = {}
    for r in requirements:
        key = (r.material_id, r.thickness_mm)
        if key not in groups:
            groups[key] = {
                "material_id": r.material_id,
                "material_name": r.material.name if r.material else None,
                "thickness_mm": float(r.thickness_mm) if r.thickness_mm is not None else None,
                "parts": [],
            }
        groups[key]["parts"].append({
            "id": r.id, "part_name": r.part_name, "product_name": r.product.name if r.product else None,
            "quantity": r.quantity, "length_mm": float(r.length_mm), "width_mm": float(r.width_mm),
            "grain_direction": r.grain_direction, "rotation_allowed": r.rotation_allowed,
            "kerf_mm": float(r.kerf_mm) if r.kerf_mm is not None else None, "notes": r.notes,
        })
    return {
        "production_job_id": job_id, "job_code": job.job_code,
        "material_groups": list(groups.values()),
        "total_parts": sum(r.quantity for r in requirements),
    }


@production_jobs_router.get("/{job_id}/nesting")
def get_nesting(job_id: int,
                 sheet_length_mm: float = Query(2440, gt=0, description="Standard 8ft sheet length by default"),
                 sheet_width_mm: float = Query(1220, gt=0, description="Standard 4ft sheet width by default"),
                 kerf_mm: float = Query(3, ge=0, description="Saw blade width lost per cut"),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Family 131 section 13 - Nesting. Runs the real, deterministic
    shelf_nest heuristic (see nesting_service.py - verified with
    standalone test cases, not a fake "AI optimizer") against this
    job's actual CuttingRequirement rows, one calculation per material
    (different materials cannot share a physical sheet). Sheet
    dimensions are a required input, not inferred - Material has no
    stored sheet-size field, so a sensible standard-sheet default is
    offered but the real, honest size must come from the caller."""
    job = db.query(ProductionJob).filter(ProductionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")

    requirements = (
        db.query(CuttingRequirement)
        .options(joinedload(CuttingRequirement.material))
        .filter(CuttingRequirement.production_job_id == job_id)
        .all()
    )
    if not requirements:
        return {"production_job_id": job_id, "job_code": job.job_code, "material_results": []}

    by_material = {}
    for r in requirements:
        by_material.setdefault(r.material_id, []).append(r)

    results = []
    for material_id, reqs in by_material.items():
        parts = [(r.length_mm, r.width_mm, r.quantity, r.rotation_allowed) for r in reqs]
        nest_result = shelf_nest(parts, sheet_length_mm, sheet_width_mm, kerf=kerf_mm)
        results.append({
            "material_id": material_id, "material_name": reqs[0].material.name if reqs[0].material else None,
            "sheet_length_mm": sheet_length_mm, "sheet_width_mm": sheet_width_mm, "kerf_mm": kerf_mm,
            **nest_result,
        })
    return {"production_job_id": job_id, "job_code": job.job_code, "material_results": results}


# --- production_operations.py ---
production_operations_router = APIRouter(prefix="/api/production-operations", tags=["production-operations"])


EMPLOYEE_SELF_SERVICE_FIELDS = {"status", "actual_duration_minutes", "start_time", "end_time"}


@production_operations_router.get("/", response_model=List[ProductionOperationResponse])
def list_production_operations(production_job_id: Optional[int] = Query(None),
                                db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(ProductionOperation).options(joinedload(ProductionOperation.depends_on))
    if production_job_id:
        query = query.filter(ProductionOperation.production_job_id == production_job_id)
    return query.order_by(ProductionOperation.production_job_id, ProductionOperation.sequence).all()


@production_operations_router.post("/", response_model=ProductionOperationResponse, status_code=201)
def create_production_operation(data: ProductionOperationCreate, db: Session = Depends(get_db),
                                 auth=Depends(require_role("master"))):
    job = db.query(ProductionJob).filter(ProductionJob.id == data.production_job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")
    if data.depends_on_operation_id:
        predecessor = db.query(ProductionOperation).filter(
            ProductionOperation.id == data.depends_on_operation_id,
        ).first()
        if not predecessor:
            raise HTTPException(status_code=404, detail="Dependency operation not found")
        if predecessor.production_job_id != data.production_job_id:
            raise HTTPException(status_code=400, detail="An operation can only depend on another operation within the same production job")

    for _ in range(5):
        operation = ProductionOperation(**data.dict(), business_id=generate_business_id(db))
        db.add(operation)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(operation)
        return operation
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@production_operations_router.get("/{operation_id}", response_model=ProductionOperationResponse)
def get_production_operation(operation_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    operation = db.query(ProductionOperation).options(joinedload(ProductionOperation.depends_on)).filter(
        ProductionOperation.id == operation_id,
    ).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Production operation not found")
    return operation


@production_operations_router.put("/{operation_id}", response_model=ProductionOperationResponse)
def update_production_operation(operation_id: int, data: ProductionOperationUpdate,
                                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    # Locked before checking/setting status - same reasoning as
    # ProductionJob's update: two simultaneous updates to the same
    # operation must not both read the same pre-update state.
    operation = db.query(ProductionOperation).options(joinedload(ProductionOperation.depends_on)).filter(
        ProductionOperation.id == operation_id,
    ).with_for_update().first()
    if not operation:
        raise HTTPException(status_code=404, detail="Production operation not found")

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

    # Real enforcement, not just informational display (P0.3.4): a
    # dependent operation cannot actually be started or completed while
    # its declared predecessor is still incomplete.
    if update_data.get("status") in ("In Progress", "Completed") and operation.is_blocked_by_dependency:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This operation depends on \"{operation.depends_on.operation_name}\", which is still "
                f"{operation.depends_on.status}. Complete it first."
            ),
        )

    for field, value in update_data.items():
        setattr(operation, field, value)
    db.add(operation)
    db.commit()
    db.refresh(operation)
    return operation


# --- cutting_requirements.py ---
cutting_requirements_router = APIRouter(prefix="/api/cutting-requirements", tags=["cutting-requirements"])


def _serialize(requirement: CuttingRequirement) -> CuttingRequirementResponse:
    response = CuttingRequirementResponse.model_validate(requirement)
    if requirement.material:
        response.material_name = requirement.material.name
    if requirement.product:
        response.product_name = requirement.product.name
    return response


@cutting_requirements_router.get("/", response_model=List[CuttingRequirementResponse])
def list_cutting_requirements(production_job_id: Optional[int] = Query(None),
                               db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(CuttingRequirement)
    if production_job_id:
        query = query.filter(CuttingRequirement.production_job_id == production_job_id)
    rows = query.order_by(CuttingRequirement.id).all()
    return [_serialize(r) for r in rows]


@cutting_requirements_router.post("/", response_model=CuttingRequirementResponse, status_code=201)
def create_cutting_requirement(data: CuttingRequirementCreate, db: Session = Depends(get_db),
                                auth=Depends(require_role("master"))):
    """Creating this record is planning only - it never touches
    Material.current_stock. Actual consumption still goes through
    Issue/StockService.record_issue exactly as before; this table has
    no write path into inventory at all."""
    job = db.query(ProductionJob).filter(ProductionJob.id == data.production_job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Production job not found")

    for _ in range(5):
        requirement = CuttingRequirement(**data.dict(), business_id=generate_business_id(db))
        db.add(requirement)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(requirement)
        return _serialize(requirement)
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@cutting_requirements_router.get("/{requirement_id}", response_model=CuttingRequirementResponse)
def get_cutting_requirement(requirement_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    requirement = db.query(CuttingRequirement).filter(CuttingRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Cutting requirement not found")
    return _serialize(requirement)


@cutting_requirements_router.put("/{requirement_id}", response_model=CuttingRequirementResponse)
def update_cutting_requirement(requirement_id: int, data: CuttingRequirementUpdate,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(CuttingRequirement).filter(CuttingRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Cutting requirement not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(requirement, field, value)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return _serialize(requirement)


@cutting_requirements_router.delete("/{requirement_id}", status_code=204)
def delete_cutting_requirement(requirement_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(CuttingRequirement).filter(CuttingRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Cutting requirement not found")
    db.delete(requirement)
    db.commit()
