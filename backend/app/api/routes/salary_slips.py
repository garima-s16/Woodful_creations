from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import require_role
from app.models.salary_slip import SalarySlip
from app.schemas.salary_slip import SalarySlipCreate, SalarySlipUpdate, SalarySlipResponse
from app.utils.id_generator import generate_short_id

router = APIRouter(prefix="/api/salary-slips", tags=["salary-slips"])


def _compute_net(data) -> None:
    gross = data.basic + data.da + data.hra + data.overtime_amount
    deductions = data.pf_deduction + data.tds_deduction + data.other_deductions
    return gross - deductions


@router.get("/", response_model=List[SalarySlipResponse])
def list_salary_slips(employee_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                       auth=Depends(require_role("master", "manager"))):
    query = db.query(SalarySlip)
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
    return query.order_by(SalarySlip.year.desc(), SalarySlip.month.desc()).all()


@router.post("/", response_model=SalarySlipResponse, status_code=201)
def create_salary_slip(data: SalarySlipCreate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master", "manager"))):
    existing = db.query(SalarySlip).filter(
        SalarySlip.employee_id == data.employee_id, SalarySlip.month == data.month, SalarySlip.year == data.year,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Salary slip for this employee/month/year already exists")

    for _ in range(5):
        slip = SalarySlip(**data.dict(), net_salary=_compute_net(data), business_id=generate_short_id())
        db.add(slip)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(slip)
        return slip
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{slip_id}", response_model=SalarySlipResponse)
def get_salary_slip(slip_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master", "manager"))):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    return slip


@router.put("/{slip_id}", response_model=SalarySlipResponse)
def update_salary_slip(slip_id: int, data: SalarySlipUpdate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master", "manager"))):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")

    updates = data.dict(exclude_unset=True)
    new_working_days = updates.get("working_days", slip.working_days)
    new_paid_days = updates.get("paid_days", slip.paid_days)
    if new_paid_days > new_working_days:
        raise HTTPException(status_code=400, detail="paid_days cannot exceed working_days")

    for field, value in updates.items():
        setattr(slip, field, value)
    slip.net_salary = slip.basic + slip.da + slip.hra + slip.overtime_amount - slip.pf_deduction - slip.tds_deduction - slip.other_deductions
    db.add(slip)
    db.commit()
    db.refresh(slip)
    return slip
