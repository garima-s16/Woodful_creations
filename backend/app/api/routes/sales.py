from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import verify_token
from app.models.sales_order import SalesOrder, SalesOrderItem
from app.schemas.sales_order import (
    SalesOrderCreate,
    SalesOrderUpdate,
    SalesOrderResponse,
)

router = APIRouter(prefix="/api/sales", tags=["sales"])
security = HTTPBearer()


def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def _generate_order_number(db: Session) -> str:
    count = db.query(SalesOrder).count()
    return f"ORD-{datetime.utcnow().strftime('%Y%m')}-{count + 1:04d}"


@router.get("/", response_model=List[SalesOrderResponse])
def get_sales_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth),
):
    query = db.query(SalesOrder)
    if status:
        query = query.filter(SalesOrder.status == status)
    if search:
        query = query.filter(
            SalesOrder.client_name.ilike(f"%{search}%")
            | SalesOrder.order_number.ilike(f"%{search}%")
        )
    return query.order_by(SalesOrder.created_at.desc()).offset(skip).limit(limit).all()


@router.post("/", response_model=SalesOrderResponse, status_code=201)
def create_sales_order(
    payload: SalesOrderCreate,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth),
):
    order_number = _generate_order_number(db)
    total = sum(item.quantity * item.unit_price for item in payload.items)

    order = SalesOrder(
        order_number=order_number,
        client_name=payload.client_name,
        client_phone=payload.client_phone,
        client_email=payload.client_email,
        notes=payload.notes,
        total_amount=total,
        status="pending",
    )
    db.add(order)
    db.flush()

    for item in payload.items:
        db.add(
            SalesOrderItem(
                order_id=order.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.quantity * item.unit_price,
            )
        )

    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=SalesOrderResponse)
def get_sales_order(
    order_id: int,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth),
):
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=SalesOrderResponse)
def update_sales_order(
    order_id: int,
    payload: SalesOrderUpdate,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth),
):
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(order, field, value)

    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}", status_code=204)
def delete_sales_order(
    order_id: int,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth),
):
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
