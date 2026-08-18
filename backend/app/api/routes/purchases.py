from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.core.audit import log_action, serializable_fields
from app.models.purchase import Purchase
from app.schemas.purchase import PurchaseCreate, PurchaseUpdate, PurchaseResponse
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.get("/", response_model=List[PurchaseResponse])
def list_purchases(supplier_id: Optional[int] = Query(None), material_id: Optional[int] = Query(None),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(Purchase)
    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)
    if material_id:
        query = query.filter(Purchase.material_id == material_id)
    return query.order_by(Purchase.date.desc()).all()


@router.post("/", response_model=PurchaseResponse, status_code=201)
def create_purchase(data: PurchaseCreate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    purchase = StockService.record_purchase(db, data)
    log_action(db, request, user_id=auth.get("user_id"), action="create_purchase", module_name="purchases",
               record_id=purchase.id, new_value={
                   "supplier_id": purchase.supplier_id, "material_id": purchase.material_id,
                   "quantity": float(purchase.quantity or 0), "invoice_total": float(purchase.invoice_total or 0),
               })
    return purchase


@router.get("/{purchase_id}", response_model=PurchaseResponse)
def get_purchase(purchase_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@router.put("/{purchase_id}", response_model=PurchaseResponse)
def update_purchase(purchase_id: int, data: PurchaseUpdate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    """Only payment_status can be edited after the fact - quantity/rate
    changes must go through a fresh purchase entry so stock stays auditable."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    updates = data.dict(exclude_unset=True)
    old_value = serializable_fields(purchase, updates.keys())
    for field, value in updates.items():
        setattr(purchase, field, value)
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    log_action(db, request, user_id=auth.get("user_id"), action="update_purchase", module_name="purchases",
               record_id=purchase.id, old_value=old_value, new_value=serializable_fields(purchase, updates.keys()))
    return purchase


@router.post("/{purchase_id}/receive", response_model=PurchaseResponse)
def receive_purchase(purchase_id: int, request: Request, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    """Marks an Ordered purchase as Received - the point stock actually
    increases. A purchase created as Received already has its stock
    applied, so this only does anything for the Ordered case."""
    purchase = StockService.mark_purchase_received(db, purchase_id)
    log_action(db, request, user_id=auth.get("user_id"), action="receive_purchase", module_name="purchases",
               record_id=purchase.id, new_value={"material_id": purchase.material_id, "receipt_status": purchase.receipt_status})
    return purchase
