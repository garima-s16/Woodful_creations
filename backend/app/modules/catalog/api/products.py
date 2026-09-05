from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.audit.audit import log_action
from app.modules.catalog.models import Product, ProductMaterial
from app.modules.sales.models import OrderItem, EstimateLineItem
from app.modules.catalog.schemas import ProductCreate, ProductUpdate, ProductResponse
from app.platform.database.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/products", tags=["products"])


def _serialize_products(products, role: str):
    """Costing (every *_cost field, overhead/margin %, cost_price,
    suggested prices, margin) is financial data, same treatment as
    Material.average_rate/stock_value - genuinely nulled server-side for
    non-master roles, not merely hidden by the frontend. selling_price
    stays visible (that's the customer-facing catalog price, not an
    internal cost figure)."""
    responses = [ProductResponse.model_validate(p) for p in products]
    if role not in ("master",):
        for r in responses:
            r.material_cost = None
            r.hardware_cost = None
            r.labour_cost = None
            r.machine_cost = None
            r.finish_cost = None
            r.packing_cost = None
            r.transport_cost = None
            r.other_cost = None
            r.overhead_percent = None
            r.margin_percent = None
            r.cost_price = None
            r.suggested_cost_price = None
            r.suggested_selling_price = None
            r.margin = None
            r.actual_margin_percent = None
    return responses


def _apply_materials_used(db: Session, product: Product, materials_used):
    db.query(ProductMaterial).filter(ProductMaterial.product_id == product.id).delete()
    db.flush()
    for m in materials_used:
        db.add(ProductMaterial(
            product_id=product.id, material_id=m.material_id,
            quantity_required=m.quantity_required, unit=m.unit, notes=m.notes,
        ))


@router.get("/", response_model=List[ProductResponse])
def list_products(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    product_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    response: Response = None,
    limit: int = Query(500, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    query = db.query(Product).options(joinedload(Product.materials_used))
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(like), Product.product_code.ilike(like),
                                  Product.business_id.ilike(like)))
    if category:
        query = query.filter(Product.category == category)
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    query = query.order_by(Product.name)
    total = query.count()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return _serialize_products(query.offset(offset).limit(limit).all(), auth.get("role", "user"))


@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, request: Request, confirm_duplicate: bool = Query(False),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    # Duplicate check (Product Master section 9): a warning, not an
    # automatic rejection - the same normalized name could legitimately
    # be two different real products (e.g. two custom one-offs that
    # happen to share a description). confirm_duplicate=true proceeds
    # anyway once the user has seen the warning and decided it's fine.
    # Duplicate check (Product Master section 9): a
    # warning, not an automatic rejection - the same normalized name could
    # legitimately be two different real products (e.g. two custom
    # one-offs that happen to share a description). confirm_duplicate=true
    # proceeds anyway once the user has seen the warning and decided it's
    # fine. Uses the same fuzzy matcher as the Product Excel importer
    # (app.modules.clients.matching.find_fuzzy_name_matches) - an exact match
    # ("Custom Walk-in Wardrobe" typed twice) and a close typo ("Custom
    # Walk-in Wardrob") are both caught here, not just in Excel, so the UI
    # and the importer can never silently disagree about what counts as a
    # possible duplicate.
    if not confirm_duplicate:
        from app.modules.clients.matching import find_fuzzy_name_matches
        active_products = db.query(Product).filter(Product.is_active == True).all()  # noqa: E712
        matches = find_fuzzy_name_matches(db=None, name=data.name, candidates=active_products, limit=5)
        if matches:
            raise HTTPException(status_code=409, detail={
                "warning": "Possible existing product found.",
                "matches": [{"id": p.id, "product_code": p.product_code, "name": p.name} for p in matches],
            })

    payload = data.dict(exclude={"product_code", "materials_used"})
    for _ in range(5):
        code = generate_unique_code(db, Product, "product_code", "PRD-")
        product = Product(**payload, product_code=code, business_id=generate_business_id(db))
        db.add(product)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        if data.materials_used:
            _apply_materials_used(db, product, data.materials_used)
        db.commit()
        db.refresh(product)
        log_action(db, request, user_id=auth.get("user_id"), action="create_product", module_name="products",
                   record_id=product.id, new_value={"product_code": product.product_code, "name": product.name})
        return product
    raise HTTPException(status_code=500, detail="Unable to generate a unique product code, please try again")


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    product = db.query(Product).options(joinedload(Product.materials_used)).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_products([product], auth.get("role", "user"))[0]


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, data: ProductUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = data.dict(exclude_unset=True, exclude={"materials_used"})
    old_status = product.is_active
    for field, value in updates.items():
        setattr(product, field, value)
    if data.materials_used is not None:
        _apply_materials_used(db, product, data.materials_used)
    db.add(product)
    db.commit()
    db.refresh(product)

    if "is_active" in updates and updates["is_active"] != old_status:
        action = "activate_product" if product.is_active else "deactivate_product"
    else:
        action = "update_product"
    log_action(db, request, user_id=auth.get("user_id"), action=action, module_name="products",
               record_id=product.id, new_value={k: str(v) for k, v in updates.items()})
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db.query(OrderItem).filter(OrderItem.product_id == product_id).first():
        raise HTTPException(status_code=400, detail="This product has order history and cannot be deleted. Mark it inactive instead.")
    if db.query(EstimateLineItem).filter(EstimateLineItem.product_id == product_id).first():
        raise HTTPException(status_code=400, detail="This product is referenced by an estimate and cannot be deleted. Mark it inactive instead.")
    product_name = product.name
    db.delete(product)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_product", module_name="products",
               record_id=product_id, old_value={"name": product_name})
