from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.product_category import ProductCategory, ProductSubcategory
from app.schemas.product_category import (
    ProductCategoryCreate, ProductCategoryResponse, ProductCategoryWithSubcategories,
    ProductSubcategoryCreate, ProductSubcategoryResponse,
)
from app.utils.id_generator import generate_short_id

router = APIRouter(prefix="/api/product-categories", tags=["product-categories"])


@router.get("/", response_model=List[ProductCategoryWithSubcategories])
def list_categories(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return db.query(ProductCategory).order_by(ProductCategory.name).all()


@router.post("/", response_model=ProductCategoryResponse, status_code=201)
def create_category(data: ProductCategoryCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    if db.query(ProductCategory).filter(ProductCategory.name == data.name).first():
        raise HTTPException(status_code=400, detail=f'A category named "{data.name}" already exists.')
    category = ProductCategory(**data.dict(), business_id=generate_short_id(db))
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'A category named "{data.name}" already exists.')
    db.refresh(category)
    return category


@router.post("/subcategories", response_model=ProductSubcategoryResponse, status_code=201)
def create_subcategory(data: ProductSubcategoryCreate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    category = db.query(ProductCategory).filter(ProductCategory.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if db.query(ProductSubcategory).filter(
        ProductSubcategory.category_id == data.category_id, ProductSubcategory.name == data.name
    ).first():
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under {category.name}.')

    subcategory = ProductSubcategory(**data.dict(), business_id=generate_short_id(db))
    db.add(subcategory)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under {category.name}.')
    db.refresh(subcategory)
    return subcategory


@router.get("/subcategories/{subcategory_id}", response_model=ProductSubcategoryResponse)
def get_subcategory(subcategory_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    subcategory = db.query(ProductSubcategory).filter(ProductSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return subcategory
