from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.services.order_service import OrderService
from app.utils.id_generator import generate_unique_code, generate_short_id
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/", response_model=List[OrderResponse])
def list_orders(response: Response, status: Optional[str] = Query(None), client_id: Optional[int] = Query(None),
                 overdue_only: bool = Query(False),
                 limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Order)
    if status:
        query = query.filter(Order.project_status == status)
    if client_id:
        query = query.filter(Order.client_id == client_id)
    if overdue_only:
        # Same rule the frontend used to apply client-side: balance still
        # outstanding and the order was placed more than 30 days ago.
        # There is no due-date field on Order, so this is a stated
        # approximation, not a precise "overdue" status - kept in SQL now
        # so it composes correctly with pagination below.
        cutoff = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Order.balance > 0, Order.order_date < cutoff)

    query = query.order_by(Order.order_date.desc())
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if limit is not None:
        query = query.offset(offset).limit(limit)
    return query.all()


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db),
                  auth=Depends(require_role("master", "manager"))):
    payload = data.dict(exclude={"order_code"})
    advance = payload.pop("advance")
    year = datetime.utcnow().year
    for _ in range(5):
        code = generate_unique_code(db, Order, "order_code", f"WC-{year}-")
        order = Order(**payload, order_code=code, business_id=generate_short_id(), advance=advance, total_received=advance, balance=data.order_value - advance)
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
