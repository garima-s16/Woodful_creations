from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.core.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.supplier import Supplier
from app.models.purchase import Purchase
from app.models.supplier_material import SupplierMaterial
from app.schemas.supplier import SupplierCreate, SupplierUpdate, SupplierResponse
from app.utils.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("/", response_model=List[SupplierResponse])
def list_suppliers(category: Optional[str] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(Supplier)
    if category:
        query = query.filter(Supplier.category == category)
    return query.order_by(Supplier.name).all()


@router.post("/", response_model=SupplierResponse, status_code=201)
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"supplier_code"})
    for _ in range(5):
        code = generate_unique_code(db, Supplier, "supplier_code", "SUP-")
        supplier = Supplier(**payload, supplier_code=code, business_id=generate_business_id(db))
        db.add(supplier)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(supplier)
        return supplier
    raise HTTPException(status_code=500, detail="Unable to generate a unique supplier code, please try again")


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(supplier_id: int, data: SupplierUpdate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if db.query(Purchase).filter(Purchase.supplier_id == supplier_id).first():
        raise HTTPException(status_code=400, detail="This supplier has purchase history and cannot be deleted.")
    if db.query(SupplierMaterial).filter(SupplierMaterial.supplier_id == supplier_id).first():
        raise HTTPException(status_code=400, detail="This supplier is linked to materials and cannot be deleted. Remove those links first.")
    supplier_name = supplier.name
    db.delete(supplier)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_supplier", module_name="suppliers",
               record_id=supplier_id, old_value={"name": supplier_name})
