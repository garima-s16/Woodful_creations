from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.purchase import Purchase
from app.schemas.purchase import PurchaseCreate, PurchaseUpdate, PurchaseResponse
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.get("/", response_model=List[PurchaseResponse])
def list_purchases(supplier_id: Optional[int] = Query(None), material_id: Optional[int] = Query(None),
                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Purchase)
    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)
    if material_id:
        query = query.filter(Purchase.material_id == material_id)
    return query.order_by(Purchase.date.desc()).all()


@router.post("/", response_model=PurchaseResponse, status_code=201)
def create_purchase(data: PurchaseCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    return StockService.record_purchase(db, data)


@router.get("/{purchase_id}", response_model=PurchaseResponse)
def get_purchase(purchase_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@router.put("/{purchase_id}", response_model=PurchaseResponse)
def update_purchase(purchase_id: int, data: PurchaseUpdate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    """Only payment_status can be edited after the fact - quantity/rate
    changes must go through a fresh purchase entry so stock stays auditable."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(purchase, field, value)
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase
