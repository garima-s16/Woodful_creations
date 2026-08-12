from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("/", response_model=List[EmployeeResponse])
def list_employees(department: Optional[str] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(Employee)
    if department:
        query = query.filter(Employee.department == department)
    return query.order_by(Employee.name).all()


@router.post("/", response_model=EmployeeResponse, status_code=201)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    payload = data.dict(exclude={"employee_code"})
    for _ in range(5):
        code = generate_unique_code(db, Employee, "employee_code", "EMP-")
        employee = Employee(**payload, employee_code=code, business_id=generate_short_id())
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
    return employee


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
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
def delete_employee(employee_id: int, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(employee)
    db.commit()
