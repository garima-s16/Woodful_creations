from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.models.employee import Employee
from app.core.database import get_db
from app.core.security import verify_token
from typing import List

router = APIRouter(prefix="/api/employees", tags=["employees"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[EmployeeResponse])
def get_employees(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    return employees

@router.post("/", response_model=EmployeeResponse)
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_employee = Employee(**employee.model_dump())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, employee: EmployeeUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = employee.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_employee, key, value)
    
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.delete("/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee.is_active = False
    db.add(employee)
    db.commit()
    return {"message": "Employee deactivated"}