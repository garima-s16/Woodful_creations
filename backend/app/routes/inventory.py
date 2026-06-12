from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
import uuid

from app.database import get_db
from app.models.inventory import Product, StockMovement, StockAlert
from app.models.user import User
from app.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, 
    StockUpdateRequest, LowStockResponse
)
from app.routes.auth import get_current_user, get_current_master_user

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    product_data: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(Product).filter(Product.sku == product_data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    new_product = Product(
        id=str(uuid.uuid4()),
        name=product_data.name,
        sku=product_data.sku,
        category=product_data.category,
        description=product_data.description,
        quantity=product_data.quantity,
        min_stock=product_data.min_stock,
        unit_cost=product_data.unit_cost,
        selling_price=product_data.selling_price,
        supplier=product_data.supplier,
        warehouse_location=product_data.warehouse_location,
        created_by=current_user.id
    )
    
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    if new_product.quantity <= new_product.min_stock:
        alert = StockAlert(
            id=str(uuid.uuid4()),
            product_id=new_product.id,
            alert_type="low_stock",
            message=f"Product {new_product.name} is below minimum stock level"
        )
        db.add(alert)
        db.commit()
    
    return new_product


@router.get("/products", response_model=dict)
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(Product.is_active == True)
    
    if category:
        query = query.filter(Product.category == category)
    
    if search:
        query = query.filter(
            (Product.name.ilike(f"%{search}%")) | 
            (Product.sku.ilike(f"%{search}%"))
        )
    
    total = query.count()
    products = query.offset(skip).limit(limit).all()
    
    return {
        "products": products,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        (Product.id == product_id) & (Product.is_active == True)
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return product


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product_data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        (Product.id == product_id) & (Product.is_active == True)
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_dict = product_data.dict(exclude_unset=True)
    
    if "sku" in update_dict and update_dict["sku"] != product.sku:
        existing = db.query(Product).filter(
            (Product.sku == update_dict["sku"]) & (Product.id != product_id)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="SKU already exists")
    
    for field, value in update_dict.items():
        setattr(product, field, value)
    
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    
    return product


@router.delete("/products/{product_id}", status_code=200)
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_master_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        (Product.id == product_id) & (Product.is_active == True)
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.is_active = False
    product.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Product deleted successfully", "product_id": product_id}


@router.patch("/products/{product_id}/stock", response_model=ProductResponse)
async def update_stock(
    product_id: str,
    stock_data: StockUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        (Product.id == product_id) & (Product.is_active == True)
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    old_quantity = product.quantity
    new_quantity = stock_data.quantity
    quantity_change = new_quantity - old_quantity
    
    product.quantity = new_quantity
    product.updated_at = datetime.utcnow()
    
    movement = StockMovement(
        id=str(uuid.uuid4()),
        product_id=product_id,
        movement_type="adjustment",
        quantity=quantity_change,
        notes=stock_data.notes or f"Stock updated by {current_user.full_name}"
    )
    
    db.add(movement)
    
    old_alerts = db.query(StockAlert).filter(
        (StockAlert.product_id == product_id) & (StockAlert.is_read == False)
    ).all()
    for alert in old_alerts:
        alert.is_read = True
    
    if new_quantity <= product.min_stock and new_quantity > 0:
        new_alert = StockAlert(
            id=str(uuid.uuid4()),
            product_id=product_id,
            alert_type="low_stock",
            message=f"Product {product.name} (SKU: {product.sku}) is below minimum stock. Current: {new_quantity}, Min: {product.min_stock}"
        )
        db.add(new_alert)
    elif new_quantity <= 0:
        out_alert = StockAlert(
            id=str(uuid.uuid4()),
            product_id=product_id,
            alert_type="out_of_stock",
            message=f"Product {product.name} (SKU: {product.sku}) is out of stock"
        )
        db.add(out_alert)
    
    db.commit()
    db.refresh(product)
    
    return product


@router.get("/low-stock", response_model=LowStockResponse)
async def get_low_stock_items(
    threshold: Optional[int] = Query(10, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    products = db.query(Product).filter(
        (Product.quantity <= threshold) & (Product.is_active == True)
    ).all()
    
    alerts = db.query(StockAlert).filter(
        StockAlert.is_read == False
    ).all()
    
    return {
        "items": products,
        "count": len(products),
        "alerts": alerts
    }


@router.get("/categories", response_model=dict)
async def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    categories = db.query(Product.category).filter(
        Product.is_active == True
    ).distinct().all()
    
    category_list = sorted([cat[0] for cat in categories if cat[0]])
    
    return {"categories": category_list}


@router.get("/statistics", response_model=dict)
async def get_inventory_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_products = db.query(Product).filter(Product.is_active == True).count()
    low_stock_count = db.query(Product).filter(
        (Product.quantity <= Product.min_stock) & (Product.is_active == True)
    ).count()
    out_of_stock_count = db.query(Product).filter(
        (Product.quantity <= 0) & (Product.is_active == True)
    ).count()
    
    total_value = db.query(Product).filter(Product.is_active == True).all()
    inventory_value = sum(p.quantity * p.unit_cost for p in total_value)
    
    return {
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_inventory_value": inventory_value,
        "active_categories": db.query(Product.category).filter(
            Product.is_active == True
        ).distinct().count()
    }