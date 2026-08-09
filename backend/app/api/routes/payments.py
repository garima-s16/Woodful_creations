from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.services.payment_service import PaymentService
from typing import List

router = APIRouter(prefix="/api/payments", tags=["Payments"])

@router.get("/", response_model=List[PaymentResponse])
async def get_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    order_id: int = Query(None),
    client_id: int = Query(None),
    payment_mode: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    if client_id:
        query = query.filter(Payment.client_id == client_id)
    if payment_mode:
        query = query.filter(Payment.payment_mode == payment_mode)
    payments = query.offset(skip).limit(limit).all()
    return payments

@router.post("/", response_model=PaymentResponse, status_code=201)
async def create_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    existing = db.query(Payment).filter(Payment.receipt_id == payment.receipt_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Receipt ID already exists")
    
    db_payment = Payment(**payment.dict())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@router.put("/{payment_id}", response_model=PaymentResponse)
async def update_payment(payment_id: int, payment_update: PaymentUpdate, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    update_data = payment_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(payment, field, value)
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment

@router.get("/order/{order_id}/summary")
async def get_order_payment_summary(order_id: int, db: Session = Depends(get_db)):
    try:
        summary = PaymentService.get_order_payment_summary(db, order_id)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/client/{client_id}/summary")
async def get_client_payment_summary(
    client_id: int,
    days: int = Query(30, ge=1),
    db: Session = Depends(get_db)
):
    summary = PaymentService.get_client_payment_summary(db, client_id, days)
    return summary

@router.get("/mode/{payment_mode}/list", response_model=List[PaymentResponse])
async def get_payments_by_mode(payment_mode: str, db: Session = Depends(get_db)):
    payments = PaymentService.get_payments_by_mode(db, payment_mode)
    return payments

@router.get("/type/{payment_type}/list", response_model=List[PaymentResponse])
async def get_payments_by_type(payment_type: str, db: Session = Depends(get_db)):
    payments = PaymentService.get_payments_by_type(db, payment_type)
    return payments

@router.get("/overdue/list")
async def get_overdue_payments(
    days: int = Query(30, ge=1),
    db: Session = Depends(get_db)
):
    overdue = PaymentService.get_overdue_payments(db, days)
    return overdue
