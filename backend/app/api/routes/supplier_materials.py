from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.supplier_material import SupplierMaterial
from app.models.supplier import Supplier
from app.models.material import Material
from app.schemas.supplier_material import (
    SupplierMaterialCreate, SupplierMaterialUpdate, SupplierMaterialResponse,
    SupplierMaterialWithSupplierName, SupplierMaterialWithMaterialName,
)

router = APIRouter(prefix="/api/supplier-materials", tags=["supplier-materials"])


def _serialize_links(links, response_cls, role: str):
    """Pricing (supplier_price, last_purchase_price) is financial data,
    genuinely nulled for non-master roles - which suppliers can
    provide a material, MOQ, and lead time stay visible, since that's
    operational information an employee needs to plan a request, not
    money data."""
    responses = [response_cls.model_validate(link) for link in links]
    if role not in ("master",):
        for r in responses:
            r.supplier_price = None
            r.last_purchase_price = None
    return responses


@router.post("/", response_model=SupplierMaterialResponse, status_code=201)
def link_supplier_material(data: SupplierMaterialCreate, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    if not db.query(Supplier).filter(Supplier.id == data.supplier_id).first():
        raise HTTPException(status_code=404, detail="Supplier not found")
    if not db.query(Material).filter(Material.id == data.material_id).first():
        raise HTTPException(status_code=404, detail="Material not found")
    if db.query(SupplierMaterial).filter(
        SupplierMaterial.supplier_id == data.supplier_id, SupplierMaterial.material_id == data.material_id
    ).first():
        raise HTTPException(status_code=400, detail="This supplier is already linked to this material.")

    link = SupplierMaterial(**data.dict())
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="This supplier is already linked to this material.")
    db.refresh(link)
    return link


@router.get("/by-material/{material_id}", response_model=List[SupplierMaterialWithSupplierName])
def list_suppliers_for_material(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Every supplier who can provide this material, for the "compare
    suppliers" experience - preferred supplier first, then by price.
    Sorting by price is itself a financial signal (the first row is the
    cheapest even with the number hidden), so a non-privileged role gets
    a price-blind order instead - preferred first, then alphabetical."""
    role = auth.get("role", "user")
    query = db.query(SupplierMaterial).filter(SupplierMaterial.material_id == material_id)
    if role in ("master",):
        links = query.order_by(SupplierMaterial.is_preferred.desc(), SupplierMaterial.supplier_price.asc()).all()
    else:
        links = query.join(Supplier).order_by(SupplierMaterial.is_preferred.desc(), Supplier.name.asc()).all()
    return _serialize_links(links, SupplierMaterialWithSupplierName, role)


@router.get("/by-supplier/{supplier_id}", response_model=List[SupplierMaterialWithMaterialName])
def list_materials_for_supplier(supplier_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    links = db.query(SupplierMaterial).filter(SupplierMaterial.supplier_id == supplier_id).all()
    return _serialize_links(links, SupplierMaterialWithMaterialName, auth.get("role", "user"))


@router.put("/{link_id}", response_model=SupplierMaterialResponse)
def update_supplier_material(link_id: int, data: SupplierMaterialUpdate, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    link = db.query(SupplierMaterial).filter(SupplierMaterial.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Supplier-material link not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(link, field, value)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{link_id}", status_code=204)
def delete_supplier_material(link_id: int, request: Request, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    link = db.query(SupplierMaterial).filter(SupplierMaterial.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Supplier-material link not found")
    old_value = {"supplier_id": link.supplier_id, "material_id": link.material_id}
    db.delete(link)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_supplier_material",
               module_name="supplier_materials", record_id=link_id, old_value=old_value)
