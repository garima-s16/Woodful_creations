from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.material import Material
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialResponse
from app.services.stock_service import StockService
from typing import List

router = APIRouter(prefix="/api/materials", tags=["Materials"])

@router.get("/", response_model=List[MaterialResponse])
async def get_materials(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    category: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Material).filter(Material.is_active == 1)
    if category:
        query = query.filter(Material.category == category)
    materials = query.offset(skip).limit(limit).all()
    
    for material in materials:
        material.current_stock = material.calculate_current_stock()
    
    return materials

@router.post("/", response_model=MaterialResponse, status_code=201)
async def create_material(material: MaterialCreate, db: Session = Depends(get_db)):
    existing = db.query(Material).filter(Material.material_id == material.material_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Material ID already exists")
    
    db_material = Material(
        **material.dict(),
        current_stock=material.opening_stock
    )
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    return db_material

@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    material.current_stock = material.calculate_current_stock()
    return material

@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(material_id: int, material_update: MaterialUpdate, db: Session = Depends(get_db)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    update_data = material_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(material, field, value)
    
    db.add(material)
    db.commit()
    db.refresh(material)
    return material

@router.get("/stock-status/low-stock")
async def get_low_stock_materials(db: Session = Depends(get_db)):
    materials = StockService.get_low_stock_materials(db)
    return {
        "count": len(materials),
        "materials": materials
    }

@router.get("/stock-status/summary")
async def get_stock_summary(db: Session = Depends(get_db)):
    summary = StockService.get_stock_summary(db)
    return summary

@router.get("/stock-status/by-category")
async def get_stock_by_category(db: Session = Depends(get_db)):
    category_summary = StockService.get_stock_by_category(db)
    return category_summary

@router.delete("/{material_id}")
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    material.is_active = 0
    db.add(material)
    db.commit()
    return {"message": "Material deleted successfully"}
