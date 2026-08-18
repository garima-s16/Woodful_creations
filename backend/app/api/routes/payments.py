from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.core.audit import log_action, serializable_fields
from fastapi import Request
from app.models.payment import Payment
from app.models.order import Order
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/", response_model=List[PaymentResponse])
def list_payments(order_id: Optional[int] = Query(None), client_id: Optional[int] = Query(None),
                   db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    if client_id:
        # One join instead of the caller fetching per-order and merging -
        # a client with many orders would otherwise mean many round trips.
        query = query.join(Order, Payment.order_id == Order.id).filter(Order.client_id == client_id)
    return query.order_by(Payment.date.desc()).all()


@router.post("/", response_model=PaymentResponse, status_code=201)
def create_payment(data: PaymentCreate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payment = OrderService.record_payment(db, data)
    log_action(db, request, user_id=auth.get("user_id"), action="create_payment",
               module_name="payments", record_id=payment.id, new_value={"amount": str(payment.amount)})
    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: int, db: Session = Depends(get_db),
                 auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(payment_id: int, data: PaymentUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    updates = data.dict(exclude_unset=True)
    old_value = serializable_fields(payment, updates.keys())
    for field, value in updates.items():
        setattr(payment, field, value)
    db.add(payment)
    payment.order.recompute_totals()
    db.add(payment.order)
    db.commit()
    db.refresh(payment)
    log_action(db, request, user_id=auth.get("user_id"), action="update_payment", module_name="payments",
               record_id=payment.id, old_value=old_value, new_value=serializable_fields(payment, updates.keys()))
    return payment
