from typing import List

from fastapi import APIRouter, Depends, HTTPException
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


@router.post("/", response_model=SupplierMaterialResponse, status_code=201)
def link_supplier_material(data: SupplierMaterialCreate, db: Session = Depends(get_db),
                            auth=Depends(require_role("master", "manager"))):
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
    suppliers" experience - preferred supplier first, then by price."""
    return db.query(SupplierMaterial).filter(SupplierMaterial.material_id == material_id).order_by(
        SupplierMaterial.is_preferred.desc(), SupplierMaterial.supplier_price.asc(),
    ).all()


@router.get("/by-supplier/{supplier_id}", response_model=List[SupplierMaterialWithMaterialName])
def list_materials_for_supplier(supplier_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return db.query(SupplierMaterial).filter(SupplierMaterial.supplier_id == supplier_id).all()


@router.put("/{link_id}", response_model=SupplierMaterialResponse)
def update_supplier_material(link_id: int, data: SupplierMaterialUpdate, db: Session = Depends(get_db),
                              auth=Depends(require_role("master", "manager"))):
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
def delete_supplier_material(link_id: int, db: Session = Depends(get_db),
                              auth=Depends(require_role("master", "manager"))):
    link = db.query(SupplierMaterial).filter(SupplierMaterial.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Supplier-material link not found")
    db.delete(link)
    db.commit()
