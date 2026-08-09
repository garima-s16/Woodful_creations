from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.purchase import PurchaseOrder
from app.schemas.purchase import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderResponse
from app.services.purchase_service import PurchaseService
from app.services.stock_service import StockService
from typing import List

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])

@router.get("/", response_model=List[PurchaseOrderResponse])
async def get_purchases(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    supplier_id: int = Query(None),
    payment_status: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(PurchaseOrder)
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    if payment_status:
        query = query.filter(PurchaseOrder.payment_status == payment_status)
    purchases = query.offset(skip).limit(limit).all()
    return purchases

@router.post("/", response_model=PurchaseOrderResponse, status_code=201)
async def create_purchase(purchase: PurchaseOrderCreate, db: Session = Depends(get_db)):
    existing = db.query(PurchaseOrder).filter(PurchaseOrder.purchase_id == purchase.purchase_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Purchase ID already exists")
    
    purchase_data = purchase.dict()
    db_purchase = PurchaseService.create_purchase_with_calculations(db, purchase_data)
    
    StockService.update_stock_on_purchase(db, purchase.material_id, purchase.quantity)
    
    return db_purchase

@router.get("/{purchase_id}", response_model=PurchaseOrderResponse)
async def get_purchase(purchase_id: int, db: Session = Depends(get_db)):
    purchase = db.query(PurchaseOrder).filter(PurchaseOrder.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase

@router.put("/{purchase_id}", response_model=PurchaseOrderResponse)
async def update_purchase(purchase_id: int, purchase_update: PurchaseOrderUpdate, db: Session = Depends(get_db)):
    purchase = db.query(PurchaseOrder).filter(PurchaseOrder.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    
    update_data = purchase_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(purchase, field, value)
    
    if "quantity" in update_data or "rate" in update_data:
        purchase.calculate_amounts()
    
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase

@router.put("/{purchase_id}/payment-status")
async def update_payment_status(purchase_id: int, payment_status: str, db: Session = Depends(get_db)):
    purchase = PurchaseService.update_payment_status(db, purchase_id, payment_status)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase

@router.get("/supplier/{supplier_id}/purchases", response_model=List[PurchaseOrderResponse])
async def get_supplier_purchases(supplier_id: int, db: Session = Depends(get_db)):
    purchases = PurchaseService.get_supplier_purchases(db, supplier_id)
    return purchases

@router.get("/payment-status/unpaid")
async def get_unpaid_purchases(db: Session = Depends(get_db)):
    purchases = PurchaseService.get_unpaid_purchases(db)
    return purchases
