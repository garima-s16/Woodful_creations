from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, get_current_master_user
from app.models.models import Product, StockMovement, StockAlert, User
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

router = APIRouter(prefix="/inventory", tags=["inventory"])

class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    description: Optional[str] = None
    quantity: int
    min_stock: int
    unit_cost: float
    selling_price: float
    supplier: Optional[str] = None
    warehouse_location: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    min_stock: Optional[int] = None
    unit_cost: Optional[float] = None
    selling_price: Optional[float] = None
    supplier: Optional[str] = None
    warehouse_location: Optional[str] = None

@router.post("/products")
async def create_product(
    product: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sku_exists = db.query(Product).filter(Product.sku == product.sku).first()
    if sku_exists:
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    new_product = Product(
        **product.dict(),
        created_by=current_user.id
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    return new_product

@router.get("/products")
async def get_products(
    skip: int = Query(0),
    limit: int = Query(100),
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(Product.is_active == True)
    
    if category:
        query = query.filter(Product.category == category)
    
    products = query.offset(skip).limit(limit).all()
    return {"products": products, "total": query.count()}

@router.get("/products/{product_id}")
async def get_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    product_update: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product

@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_master_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.is_active = False
    db.commit()
    return {"message": "Product deleted successfully"}

@router.patch("/products/{product_id}/stock")
async def update_stock(
    product_id: str,
    quantity: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    old_quantity = product.quantity
    product.quantity = quantity
    product.updated_at = datetime.utcnow()
    
    movement = StockMovement(
        product_id=product_id,
        movement_type="update",
        quantity=quantity - old_quantity,
        notes=f"Stock updated by {current_user.full_name}"
    )
    db.add(movement)
    db.commit()
    db.refresh(product)
    
    return product

@router.get("/low-stock")
async def get_low_stock_items(
    threshold: int = Query(10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    products = db.query(Product).filter(
        (Product.quantity <= threshold) & (Product.is_active == True)
    ).all()
    
    return {"items": products}

@router.get("/categories")
async def get_categories(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    categories = db.query(Product.category).distinct().all()
    return {"categories": [cat[0] for cat in categories if cat[0]]}