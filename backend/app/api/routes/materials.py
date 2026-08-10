from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.material import Material
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialResponse

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.get("/", response_model=List[MaterialResponse])
def list_materials(category: Optional[str] = Query(None), search: Optional[str] = Query(None),
                    low_stock_only: bool = Query(False), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(Material)
    if category:
        query = query.filter(Material.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter((Material.name.ilike(like)) | (Material.material_code.ilike(like)))
    materials = query.order_by(Material.name).all()
    if low_stock_only:
        materials = [m for m in materials if m.current_stock <= m.minimum_stock]
    return materials


@router.post("/", response_model=MaterialResponse, status_code=201)
def create_material(data: MaterialCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    if db.query(Material).filter(Material.material_code == data.material_code).first():
        raise HTTPException(status_code=400, detail="Material code already exists")
    payload = data.dict()
    payload["current_stock"] = payload["opening_stock"]
    material = Material(**payload)
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.get("/{material_id}", response_model=MaterialResponse)
def get_material(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.put("/{material_id}", response_model=MaterialResponse)
def update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(material, field, value)
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    db.delete(material)
    db.commit()
