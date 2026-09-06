from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action, serializable_fields
from app.modules.procurement.models import Purchase
from app.modules.inventory.schemas import PurchaseCreate, PurchaseUpdate, PurchaseResponse, PurchaseReceiveRequest
from app.modules.procurement.services import ProcurementService

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.get("/", response_model=List[PurchaseResponse])
def list_purchases(response: Response, supplier_id: Optional[int] = Query(None), material_id: Optional[int] = Query(None),
                    pending_payment_only: bool = Query(False),
                    limit: int = Query(500, ge=1, le=500), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(Purchase)
    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)
    if material_id:
        query = query.filter(Purchase.material_id == material_id)
    if pending_payment_only:
        # Dashboard "pending purchases" widget - was previously derived
        # client-side from the same unbounded purchasesAPI.list() call
        # used for the recent-activity feed. A direct field filter.
        query = query.filter(Purchase.payment_status != "Paid")
    total = query.count()
    response.headers["X-Total-Count"] = str(total)
    return query.order_by(Purchase.date.desc()).offset(offset).limit(limit).all()


@router.post("/", response_model=PurchaseResponse, status_code=201)
def create_purchase(data: PurchaseCreate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    purchase = ProcurementService.record_purchase(db, data)
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
def receive_purchase(purchase_id: int, data: Optional[PurchaseReceiveRequest] = None,
                      request: Request = None, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    """Marks an Ordered/Partially Received purchase toward Received -
    the point stock actually increases. With no body (or an omitted
    quantity), receives everything still outstanding, exactly as
    before. A quantity can be passed to receive only part of the
    order, moving it to "Partially Received" until the rest arrives."""
    quantity_to_receive = data.quantity if data else None
    receive_location_id = data.location_id if data else None
    purchase = ProcurementService.mark_purchase_received(db, purchase_id, quantity_to_receive, receive_location_id)
    log_action(db, request, user_id=auth.get("user_id"), action="receive_purchase", module_name="purchases",
               record_id=purchase.id, new_value={
                   "material_id": purchase.material_id, "receipt_status": purchase.receipt_status,
                   "quantity_received": float(purchase.quantity_received or 0),
               })
    return purchase
