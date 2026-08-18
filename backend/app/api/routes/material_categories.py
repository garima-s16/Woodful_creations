from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.material_category import MaterialCategory, MaterialSubcategory
from app.models.material_attribute import MaterialAttributeDefinition
from app.schemas.material_category import (
    MaterialCategoryCreate, MaterialCategoryResponse, MaterialCategoryWithSubcategories,
    MaterialSubcategoryCreate, MaterialSubcategoryResponse,
    MaterialAttributeDefinitionCreate, MaterialAttributeDefinitionResponse,
)
from app.utils.id_generator import generate_short_id

router = APIRouter(prefix="/api/material-categories", tags=["material-categories"])


@router.get("/", response_model=List[MaterialCategoryWithSubcategories])
def list_categories(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return db.query(MaterialCategory).order_by(MaterialCategory.name).all()


@router.post("/", response_model=MaterialCategoryResponse, status_code=201)
def create_category(data: MaterialCategoryCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    if db.query(MaterialCategory).filter(MaterialCategory.name == data.name).first():
        raise HTTPException(status_code=400, detail=f'A category named "{data.name}" already exists.')
    category = MaterialCategory(**data.dict(), business_id=generate_short_id())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'A category named "{data.name}" already exists.')
    db.refresh(category)
    return category


@router.post("/subcategories", response_model=MaterialSubcategoryResponse, status_code=201)
def create_subcategory(data: MaterialSubcategoryCreate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    category = db.query(MaterialCategory).filter(MaterialCategory.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if db.query(MaterialSubcategory).filter(
        MaterialSubcategory.category_id == data.category_id, MaterialSubcategory.name == data.name
    ).first():
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under {category.name}.')

    subcategory = MaterialSubcategory(**data.dict(), business_id=generate_short_id())
    db.add(subcategory)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under {category.name}.')
    db.refresh(subcategory)
    return subcategory


@router.get("/subcategories/{subcategory_id}", response_model=MaterialSubcategoryResponse)
def get_subcategory(subcategory_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    subcategory = db.query(MaterialSubcategory).filter(MaterialSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return subcategory


@router.post("/subcategories/{subcategory_id}/attributes",
             response_model=MaterialAttributeDefinitionResponse, status_code=201)
def create_attribute_definition(subcategory_id: int, data: MaterialAttributeDefinitionCreate,
                                 db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Defines a specification field for this subcategory - e.g. adding
    "Voltage" (number, unit "V") to a new "LED Strip" subcategory. Every
    material later created under this subcategory can then have a real
    value for it, filterable via value_number, not a free-text guess."""
    subcategory = db.query(MaterialSubcategory).filter(MaterialSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    if db.query(MaterialAttributeDefinition).filter(
        MaterialAttributeDefinition.subcategory_id == subcategory_id, MaterialAttributeDefinition.name == data.name
    ).first():
        raise HTTPException(status_code=400, detail=f'An attribute named "{data.name}" already exists here.')

    definition = MaterialAttributeDefinition(subcategory_id=subcategory_id, **data.dict())
    db.add(definition)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'An attribute named "{data.name}" already exists here.')
    db.refresh(definition)
    return definition
