"""Family P0.44 - Salary Advance Management API. The complete workflow
(spec section 5): Employee/Master request -> Master approve/reject ->
recovery against real SalarySlips. Recovery reuses
salary_slips.py's own _compute_net (imported, not reimplemented) so
net_salary is never calculated two different ways."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.modules.hr.models import SalaryAdvance, Employee, SalarySlip
from app.modules.auth.models import User
from app.modules.hr.schemas import (
    SalaryAdvanceCreate, SalaryAdvanceApprove, SalaryAdvanceReject, SalaryAdvanceRecovery, SalaryAdvanceResponse,
)
from app.modules.hr.api.salary_slips import _compute_net
from app.modules.communications.services.notification_service import NotificationService
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/salary-advances", tags=["salary-advances"])


def _notify_advance_decision(db, advance: SalaryAdvance, decision: str) -> None:
    """One authoritative call into the same notify() every other
    module uses (in-app + email in one place, a failed email never
    corrupting the advance record itself - see notify()'s own
    docstring). Silently does nothing if this employee has no linked
    login account or no email on file - the decision itself is still
    saved regardless; this is a best-effort courtesy notification, not
    part of the approval/rejection's own correctness."""
    employee = advance.employee
    if not employee:
        return
    recipient = db.query(User).filter(User.employee_id == employee.id).first()
    if decision == "approved":
        title = "Salary advance approved"
        message = f"Your salary advance request has been approved for {advance.approved_amount}."
    else:
        title = "Salary advance rejected"
        message = "Your salary advance request has been rejected."
        if advance.rejection_reason:
            message += f" Reason: {advance.rejection_reason}"
    NotificationService.notify(
        db, notification_type="SALARY_ADVANCE_DECISION", severity="INFO" if decision == "approved" else "WARNING",
        title=title, message=message,
        recipient_user_id=recipient.id if recipient else None,
        related_entity_type="salary_advance", related_entity_id=advance.id,
        action_path="/salary-advances",
        recipient_email=employee.email if employee.email else None,
        email_subject=title, email_body=message,
    )


def _serialize(advance: SalaryAdvance) -> SalaryAdvanceResponse:
    response = SalaryAdvanceResponse.model_validate(advance)
    if advance.employee:
        response.employee_name = advance.employee.name
    return response


@router.get("/", response_model=List[SalaryAdvanceResponse])
def list_salary_advances(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                          db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Employee sees only their own (spec section 6) - identical IDOR
    pattern to leaves.py/attendance.py: a non-master querying someone
    else's employee_id is rejected outright, not silently redirected
    to their own, so a probing request gets a clear 403 rather than a
    misleadingly-successful-looking empty/own result."""
    if auth.get("role", "user") not in ("master",):
        own_employee_id = auth.get("employee_id")
        if employee_id and employee_id != own_employee_id:
            raise HTTPException(status_code=403, detail="You can only view your own salary advance requests.")
        if not own_employee_id:
            return []
        employee_id = own_employee_id
    query = db.query(SalaryAdvance).options(selectinload(SalaryAdvance.employee))
    if employee_id:
        query = query.filter(SalaryAdvance.employee_id == employee_id)
    if status:
        query = query.filter(SalaryAdvance.status == status)
    rows = query.order_by(SalaryAdvance.request_date.desc()).all()
    return [_serialize(r) for r in rows]


@router.post("/", response_model=SalaryAdvanceResponse, status_code=201)
def request_salary_advance(data: SalaryAdvanceCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Covers both the employee's own request and the Master
    direct-advance workflow (spec section 8) - an employee requesting
    for anyone but themselves is rejected exactly like leaves.py's
    equivalent check; a Master may create one for any valid employee."""
    is_master = auth.get("role", "user") in ("master",)
    if not is_master and data.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only request a salary advance for yourself.")

    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    creator = auth.get("username") or str(auth.get("user_id"))
    for _ in range(5):
        advance = SalaryAdvance(
            business_id=generate_business_id(db), employee_id=data.employee_id,
            requested_amount=data.requested_amount, request_date=data.request_date,
            reason=data.reason, remarks=data.remarks, status="Pending", recovered_amount=0,
            created_by=creator,
        )
        db.add(advance)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(advance)
        return _serialize(advance)
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{advance_id}", response_model=SalaryAdvanceResponse)
def get_salary_advance(advance_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    advance = db.query(SalaryAdvance).options(selectinload(SalaryAdvance.employee)).filter(SalaryAdvance.id == advance_id).first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if auth.get("role", "user") not in ("master",) and advance.employee_id != auth.get("employee_id"):
        raise HTTPException(status_code=403, detail="You can only view your own salary advance requests.")
    return _serialize(advance)


@router.put("/{advance_id}/approve", response_model=SalaryAdvanceResponse)
def approve_salary_advance(advance_id: int, data: SalaryAdvanceApprove,
                            db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Only MASTER (spec section 7). approved_amount defaults to the
    requested amount if not given; requested_amount itself is never
    touched (spec: "Requested Amount remains historical")."""
    advance = db.query(SalaryAdvance).filter(SalaryAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if advance.status != "Pending":
        raise HTTPException(status_code=409, detail=f"This advance is already {advance.status.lower()} - cannot approve it again.")

    advance.approved_amount = data.approved_amount if data.approved_amount is not None else advance.requested_amount
    advance.approved_by = auth.get("username") or str(auth.get("user_id"))
    from datetime import datetime
    advance.approval_date = datetime.utcnow()
    advance.recovery_month = data.recovery_month
    advance.recovery_year = data.recovery_year
    advance.status = "Approved"
    if data.remarks:
        advance.remarks = data.remarks
    db.add(advance)
    db.commit()
    db.refresh(advance)
    _notify_advance_decision(db, advance, decision="approved")
    return _serialize(advance)


@router.put("/{advance_id}/reject", response_model=SalaryAdvanceResponse)
def reject_salary_advance(advance_id: int, data: SalaryAdvanceReject,
                           db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    advance = db.query(SalaryAdvance).filter(SalaryAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if advance.status != "Pending":
        raise HTTPException(status_code=409, detail=f"This advance is already {advance.status.lower()} - cannot reject it again.")

    advance.status = "Rejected"
    advance.rejection_reason = data.rejection_reason
    db.add(advance)
    db.commit()
    db.refresh(advance)
    _notify_advance_decision(db, advance, decision="rejected")
    return _serialize(advance)


@router.post("/{advance_id}/recover", response_model=SalaryAdvanceResponse)
def record_salary_advance_recovery(advance_id: int, data: SalaryAdvanceRecovery,
                                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Recovery against one real, existing SalarySlip for this
    employee/month - never a bare number typed here with nothing
    behind it (spec section 10's "must use the authoritative payroll
    calculation"). Row-locks both the advance and the slip to prevent
    a concurrent double-recovery from either passing its own
    outstanding-balance check against stale data."""
    advance = db.query(SalaryAdvance).filter(SalaryAdvance.id == advance_id).with_for_update().first()
    if not advance:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    if advance.status != "Approved":
        raise HTTPException(status_code=409, detail="Only an approved advance can have recovery recorded against it.")

    outstanding = advance.outstanding_amount
    if data.amount > outstanding:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot recover {data.amount} - only {outstanding} remains outstanding on this advance.",
        )

    slip = (
        db.query(SalarySlip)
        .filter(SalarySlip.employee_id == advance.employee_id, SalarySlip.month == data.month, SalarySlip.year == data.year)
        .with_for_update().first()
    )
    if not slip:
        raise HTTPException(
            status_code=404,
            detail=f"No salary slip exists for this employee for {data.month} {data.year} - create it before recording recovery against it.",
        )

    advance.recovered_amount = (advance.recovered_amount or 0) + data.amount
    slip.advance_deduction = (slip.advance_deduction or 0) + data.amount
    slip.net_salary = _compute_net(slip)
    db.add(advance)
    db.add(slip)
    db.commit()
    db.refresh(advance)
    return _serialize(advance)
