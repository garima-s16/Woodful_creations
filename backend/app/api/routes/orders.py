from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.order import Order, OrderExpense
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse, OrderProfitability
from app.services.order_service import OrderService
from typing import List

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("/", response_model=List[OrderResponse])
async def get_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str = Query(None),
    client_id: int = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if client_id:
        query = query.filter(Order.client_id == client_id)
    orders = query.offset(skip).limit(limit).all()
    return orders

@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    existing = db.query(Order).filter(Order.order_id == order.order_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Order ID already exists")
    
    db_order = Order(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(order_id: int, order_update: OrderUpdate, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    update_data = order_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)
    
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

@router.put("/{order_id}/status")
async def update_order_status(order_id: int, status: str, db: Session = Depends(get_db)):
    order = OrderService.update_order_status(db, order_id, status)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.get("/{order_id}/profitability", response_model=OrderProfitability)
async def get_order_profitability(order_id: int, db: Session = Depends(get_db)):
    try:
        profitability = OrderService.get_order_profitability(db, order_id)
        return profitability
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/status/{status}/list", response_model=List[OrderResponse])
async def get_orders_by_status(status: str, db: Session = Depends(get_db)):
    orders = OrderService.get_orders_by_status(db, status)
    return orders

@router.get("/active/list")
async def get_active_orders(db: Session = Depends(get_db)):
    orders = OrderService.get_active_orders(db)
    return orders

@router.post("/{order_id}/expenses")
async def add_order_expense(order_id: int, expense: dict, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db_expense = OrderExpense(
        order_id=order_id,
        **expense
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@router.get("/{order_id}/expenses")
async def get_order_expenses(order_id: int, db: Session = Depends(get_db)):
    expenses = db.query(OrderExpense).filter(OrderExpense.order_id == order_id).all()
    return expenses
