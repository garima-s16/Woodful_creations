from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.models.payment import Payment
from app.core.database import get_db
from app.core.security import verify_token
from typing import List

router = APIRouter(prefix="/api/payments", tags=["payments"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[PaymentResponse])
def get_payments(payment_type: str = Query(None), status: str = Query(None), db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(Payment)
    if payment_type:
        query = query.filter(Payment.payment_type == payment_type)
    if status:
        query = query.filter(Payment.status == status)
    return query.all()

@router.post("/", response_model=PaymentResponse)
def record_payment(payment: PaymentCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_payment = Payment(**payment.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@router.patch("/{payment_id}", response_model=PaymentResponse)
def update_payment(payment_id: int, payment: PaymentUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    update_data = payment.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_payment, key, value)
    
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

@router.delete("/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    db.delete(payment)
    db.commit()
    return {"message": "Payment deleted"}