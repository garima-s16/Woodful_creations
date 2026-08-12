from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.estimate import Estimate
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


def _build_order_items(items_data, order_id: int = None):
    """Computes amount = quantity * rate server-side for each item -
    never trusted from client input directly, matching the estimate
    line items pattern (including ROUND_HALF_UP - Python's default
    quantize rounding is banker's rounding, which would silently
    disagree with how estimate amounts are computed for the exact same
    calculation)."""
    from decimal import Decimal, ROUND_HALF_UP
    result = []
    for idx, item in enumerate(items_data):
        amount = (item.quantity * item.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.append(OrderItem(
            order_id=order_id, description=item.description, category=item.category,
            quantity=item.quantity, unit=item.unit, rate=item.rate, amount=amount, sort_order=idx,
        ))
    return result


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db),
                  auth=Depends(require_role("master", "manager"))):
    from decimal import Decimal

    payload = data.dict(exclude={"order_code", "advance", "items", "from_estimate_id"})
    advance = data.advance

    source_estimate = None
    if data.from_estimate_id:
        source_estimate = db.query(Estimate).filter(Estimate.id == data.from_estimate_id).first()
        if not source_estimate:
            raise HTTPException(status_code=404, detail="Source estimate not found")

    if source_estimate and source_estimate.line_items:
        # Copy items from the estimate's line items rather than re-enter
        # them - each new OrderItem stays traceable back to the
        # estimate line it came from via source_estimate_item_id.
        order_items = [
            OrderItem(
                description=li.description, category=li.category, quantity=li.quantity,
                unit=li.unit, rate=li.rate, amount=li.amount,
                source_estimate_item_id=li.id, sort_order=idx,
            )
            for idx, li in enumerate(source_estimate.line_items)
        ]
    elif data.items:
        order_items = _build_order_items(data.items)
    else:
        order_items = []

    if order_items:
        items_total = sum((i.amount for i in order_items), Decimal("0"))
        payload["order_value"] = items_total

    year = datetime.utcnow().year
    for _ in range(5):
        code = generate_unique_code(db, Order, "order_code", f"WC-{year}-")
        order = Order(**payload, order_code=code, business_id=generate_short_id(),
                      advance=advance, total_received=advance, balance=payload["order_value"] - advance)
        db.add(order)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        for item in order_items:
            item.order_id = order.id
            db.add(item)
        if source_estimate:
            source_estimate.order_id = order.id
            db.add(source_estimate)
        db.commit()
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
    from decimal import Decimal

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    update_fields = data.dict(exclude_unset=True, exclude={"items"})
    for field, value in update_fields.items():
        setattr(order, field, value)

    if data.items is not None:
        for existing in list(order.items):
            db.delete(existing)
        db.flush()
        new_items = _build_order_items(data.items, order_id=order.id)
        for item in new_items:
            db.add(item)
        db.flush()
        order.order_value = sum((i.amount for i in new_items), Decimal("0"))

    if "order_value" in update_fields or data.items is not None:
        order.balance = (order.order_value or Decimal("0")) - (order.total_received or Decimal("0"))

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
