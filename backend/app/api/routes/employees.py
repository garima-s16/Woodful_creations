from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.core.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/employees", tags=["employees"])


def _serialize_employees(employees, role: str, own_employee_id):
    """monthly_salary/daily_wage/pan/uan/bank details are confidential
    HR/payroll data (the same category as salary slips), not general
    directory info - genuinely nulled for every record except the
    requester's own, for non-privileged roles. Master accounts see
    everyone's."""
    responses = [EmployeeResponse.model_validate(e) for e in employees]
    if role not in ("master",):
        for r in responses:
            if r.id != own_employee_id:
                r.monthly_salary = None
                r.daily_wage = None
                r.pan = None
                r.uan = None
                r.bank_name = None
                r.bank_account_number = None
    return responses


def _serialize_employee(employee, role: str, own_employee_id):
    return _serialize_employees([employee], role, own_employee_id)[0]


@router.get("/", response_model=List[EmployeeResponse])
def list_employees(department: Optional[str] = Query(None), status: Optional[str] = Query(None),
                    search: Optional[str] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(Employee)
    if department:
        query = query.filter(Employee.department == department)
    if status:
        query = query.filter(Employee.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Employee.name.ilike(like)) | (Employee.employee_code.ilike(like))
            | (Employee.designation.ilike(like)) | (Employee.phone.ilike(like)) | (Employee.email.ilike(like))
        )
    return _serialize_employees(query.order_by(Employee.name).all(), auth.get("role", "user"), auth.get("employee_id"))


@router.post("/", response_model=EmployeeResponse, status_code=201)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"employee_code"})
    for _ in range(5):
        code = generate_unique_code(db, Employee, "employee_code", "EMP-")
        employee = Employee(**payload, employee_code=code, business_id=generate_short_id(db))
        db.add(employee)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(employee)
        return employee
    raise HTTPException(status_code=500, detail="Unable to generate a unique employee code, please try again")


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _serialize_employee(employee, auth.get("role", "user"), auth.get("employee_id"))


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(employee, field, value)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee_name = employee.name
    db.delete(employee)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_employee", module_name="employees",
               record_id=employee_id, old_value={"name": employee_name})
