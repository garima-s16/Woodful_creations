from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from sqlalchemy.orm import Session
from app.schemas.salary_slip import SalarySlipCreate, SalarySlipUpdate, SalarySlipResponse
from app.models.salary_slip import SalarySlip
from app.core.database import get_db
from app.core.security import verify_token
from typing import List

router = APIRouter(prefix="/api/salary-slips", tags=["salary"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[SalarySlipResponse])
def get_salary_slips(employee_id: int = Query(None), db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(SalarySlip)
    if employee_id:
        query = query.filter(SalarySlip.employee_id == employee_id)
    return query.all()

@router.post("/", response_model=SalarySlipResponse)
def create_salary_slip(slip: SalarySlipCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    net_salary = slip.basic_salary + slip.allowances - slip.deductions
    db_slip = SalarySlip(**slip.dict(), net_salary=net_salary)
    db.add(db_slip)
    db.commit()
    db.refresh(db_slip)
    return db_slip

@router.get("/{slip_id}", response_model=SalarySlipResponse)
def get_salary_slip(slip_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    return slip

@router.patch("/{slip_id}", response_model=SalarySlipResponse)
def update_salary_slip(slip_id: int, slip: SalarySlipUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_slip = db.query(SalarySlip).filter(SalarySlip.id == slip_id).first()
    if not db_slip:
        raise HTTPException(status_code=404, detail="Salary slip not found")
    
    update_data = slip.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_slip, key, value)
    
    db_slip.net_salary = db_slip.basic_salary + db_slip.allowances - db_slip.deductions
    
    db.add(db_slip)
    db.commit()
    db.refresh(db_slip)
    return db_slip