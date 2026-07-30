from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_token
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.chat_service import MATERIAL_TYPES

router = APIRouter(prefix="/api/inventory", tags=["inventory"])
security = HTTPBearer()


def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@router.get("/materials", response_model=dict)
def get_material_types():
    return {"materials": MATERIAL_TYPES}


@router.get("/", response_model=list[ProductResponse])
def get_inventory(
    material_type: str | None = Query(default=None),
    thickness: float | None = Query(default=None),
    db: Session = Depends(get_db),
    auth=Depends(verify_auth),
):
    query = db.query(Product)
    if material_type:
        query = query.filter(Product.material_type == material_type)
    if thickness is not None:
        query = query.filter(Product.thickness == thickness)
    return query.all()


@router.post("/", response_model=ProductResponse)
def add_product(product: ProductCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    if product.material_type not in MATERIAL_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid material type. Available: {list(MATERIAL_TYPES.keys())}")

    if product.thickness not in MATERIAL_TYPES[product.material_type]:
        raise HTTPException(status_code=400, detail=f"Invalid thickness for {product.material_type}. Valid: {MATERIAL_TYPES[product.material_type]}")

    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, product: ProductUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product.dict(exclude_unset=True)

    if "material_type" in update_data or "thickness" in update_data:
        material = update_data.get("material_type", db_product.material_type)
        thickness = update_data.get("thickness", db_product.thickness)

        if material not in MATERIAL_TYPES or thickness not in MATERIAL_TYPES[material]:
            raise HTTPException(status_code=400, detail="Invalid material type or thickness combination")

    for key, value in update_data.items():
        setattr(db_product, key, value)

    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@router.get("/alerts/low-stock")
def get_low_stock_alerts(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    low_stock = db.query(Product).filter(Product.quantity <= Product.min_quantity).all()
    return {"low_stock_items": low_stock, "count": len(low_stock)}
