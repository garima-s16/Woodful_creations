from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.services.order_service import OrderService
from app.utils.id_generator import generate_unique_code
from datetime import datetime

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/", response_model=List[OrderResponse])
def list_orders(status: Optional[str] = Query(None), client_id: Optional[int] = Query(None),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Order)
    if status:
        query = query.filter(Order.project_status == status)
    if client_id:
        query = query.filter(Order.client_id == client_id)
    return query.order_by(Order.order_date.desc()).all()


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db),
                  auth=Depends(require_role("master", "manager"))):
    payload = data.dict(exclude={"order_code"})
    advance = payload.pop("advance")
    year = datetime.utcnow().year
    for _ in range(5):
        code = generate_unique_code(db, Order, "order_code", f"WC-{year}-")
        order = Order(**payload, order_code=code, advance=advance, total_received=advance, balance=data.order_value - advance)
        db.add(order)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(order)
        return order
    raise HTTPException(status_code=500, detail="Unable to generate a unique order code, please try again")


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(order_id: int, data: OrderUpdate, db: Session = Depends(get_db),
                  auth=Depends(require_role("master", "manager"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(order, field, value)
    if "order_value" in data.dict(exclude_unset=True):
        order.balance = (order.order_value or 0) - (order.total_received or 0)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}/profitability")
def get_order_profitability(order_id: int, db: Session = Depends(get_db),
                             auth=Depends(require_role("master", "manager"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderService.profitability(db, order)
