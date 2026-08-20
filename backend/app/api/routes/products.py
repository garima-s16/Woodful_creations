from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.audit import log_action
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.product import Product
from app.models.product_category import ProductSubcategory
from app.models.product_material import ProductMaterial
from app.models.material import Material
from app.models.order_item import OrderItem
from app.models.estimate_line_item import EstimateLineItem
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductMaterialResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/products", tags=["products"])


def _serialize_products(products, role: str):
    """Cost price is a genuinely financial figure (what it costs
    Woodful to make/source a piece) - nulled server-side for non-master
    roles, same discipline as Material.average_rate/stock_value in
    _serialize_materials(). Selling price stays visible to everyone
    (it's what a client is quoted, not internal cost data), so margin
    is nulled too rather than left computable by subtraction."""
    responses = []
    for p in products:
        r = ProductResponse.model_validate(p)
        r.bom_items = [
            ProductMaterialResponse(
                id=b.id, material_id=b.material_id, material_name=b.material.name,
                material_unit=b.material.unit, quantity=b.quantity, unit=b.unit or b.material.unit,
            )
            for b in p.bom_items
        ]
        responses.append(r)
    if role not in ("master",):
        for r in responses:
            r.cost_price = None
            r.margin = None
    return responses


def _serialize_product(product, role: str):
    return _serialize_products([product], role)[0]


def _resolve_product_category_name(db: Session, subcategory_id):
    """Same sync pattern as Material._resolve_category_name - the legacy
    flat `category` string stays in sync with the subcategory's parent
    category name whenever subcategory_id is set."""
    if not subcategory_id:
        return None
    subcategory = db.query(ProductSubcategory).filter(ProductSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return subcategory.category.name


def _apply_bom(db: Session, product: Product, bom_items):
    """Replaces the product's full bill-of-materials - "submit the
    current complete list" semantics, matching
    materials.py's _apply_attribute_values."""
    for existing in list(product.bom_items):
        db.delete(existing)
    db.flush()
    for item in bom_items:
        material = db.query(Material).filter(Material.id == item.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail=f"Material {item.material_id} not found")
        db.add(ProductMaterial(
            product_id=product.id, material_id=item.material_id,
            quantity=item.quantity, unit=item.unit,
        ))


@router.get("/", response_model=List[ProductResponse])
def list_products(response: Response, category: Optional[str] = Query(None), search: Optional[str] = Query(None),
                   product_type: Optional[str] = Query(None), active_only: bool = Query(False),
                   subcategory_id: Optional[int] = Query(None),
                   limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                   db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    if subcategory_id:
        query = query.filter(Product.subcategory_id == subcategory_id)
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if active_only:
        query = query.filter(Product.is_active.is_(True))
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Product.name.ilike(like)) | (Product.product_code.ilike(like)) | (Product.sku.ilike(like))
        )

    query = query.order_by(Product.name)
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if limit is not None:
        query = query.offset(offset).limit(limit)
    return _serialize_products(query.all(), auth.get("role", "user"))


@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"product_code", "bom_items"})
    if data.subcategory_id:
        payload["category"] = _resolve_product_category_name(db, data.subcategory_id)

    for _ in range(5):
        code = generate_unique_code(db, Product, "product_code", "PROD-")
        product = Product(**payload, product_code=code, business_id=generate_short_id(db))
        db.add(product)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        if data.bom_items:
            _apply_bom(db, product, data.bom_items)
        db.commit()
        db.refresh(product)
        log_action(db, request, user_id=auth.get("user_id"), action="create_product", module_name="products",
                   record_id=product.id, new_value={"name": product.name, "product_code": product.product_code})
        return product
    raise HTTPException(status_code=500, detail="Unable to generate a unique product code, please try again")


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_product(product, auth.get("role", "user"))


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, data: ProductUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.dict(exclude_unset=True, exclude={"bom_items"})
    if "subcategory_id" in update_data:
        update_data["category"] = _resolve_product_category_name(db, update_data["subcategory_id"])
    for field, value in update_data.items():
        setattr(product, field, value)

    if data.bom_items is not None:
        _apply_bom(db, product, data.bom_items)

    db.add(product)
    db.commit()
    db.refresh(product)
    log_action(db, request, user_id=auth.get("user_id"), action="update_product", module_name="products",
               record_id=product.id, new_value=update_data)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db.query(OrderItem).filter(OrderItem.product_id == product_id).first():
        raise HTTPException(status_code=400, detail="This product is used on an order and cannot be deleted. Mark it inactive instead.")
    if db.query(EstimateLineItem).filter(EstimateLineItem.product_id == product_id).first():
        raise HTTPException(status_code=400, detail="This product is used on an estimate and cannot be deleted. Mark it inactive instead.")
    product_name = product.name
    db.delete(product)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_product", module_name="products",
               record_id=product_id, old_value={"name": product_name})
