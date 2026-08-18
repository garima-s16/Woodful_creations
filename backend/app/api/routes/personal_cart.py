from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.personal_cart_item import PersonalCartItem
from app.models.material import Material
from app.models.supplier import Supplier
from app.schemas.personal_cart import PersonalCartItemCreate, PersonalCartItemUpdate, PersonalCartItemResponse

router = APIRouter(prefix="/api/personal-cart", tags=["personal-cart"])


def _my_items_query(db: Session, auth):
    """Every query in this file starts here - scoped to the
    authenticated user's own id. There is no path in this router that
    accepts or trusts a client-supplied user_id; "whose cart" is always
    derived from the token, never a request parameter (matching the
    "Pankaj cannot see Garima's cart" requirement at the API layer, not
    just hidden in the UI)."""
    return db.query(PersonalCartItem).filter(
        PersonalCartItem.user_id == auth.get("user_id"), PersonalCartItem.status == "ACTIVE"
    )


def _serialize_cart_items(items, role: str):
    """rate is stored regardless of role (useful for a future
    master-side review of what's been requested), but genuinely
    redacted here in the response for non-privileged roles - an
    employee should not see a material's price by adding it to their
    own cart when the Materials page itself hides it from them."""
    responses = [PersonalCartItemResponse.model_validate(i) for i in items]
    if role not in ("master",):
        for r in responses:
            r.rate = None
    return responses


def _serialize_cart_item(item, role: str):
    return _serialize_cart_items([item], role)[0]


@router.get("/", response_model=List[PersonalCartItemResponse])
def list_my_cart(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    items = _my_items_query(db, auth).order_by(PersonalCartItem.created_at.asc()).all()
    return _serialize_cart_items(items, auth.get("role", "user"))


@router.post("/", response_model=PersonalCartItemResponse, status_code=201)
def add_to_cart(data: PersonalCartItemCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

    supplier_name = None
    if data.supplier_id:
        supplier = db.query(Supplier).filter(Supplier.id == data.supplier_id).first()
        supplier_name = supplier.name if supplier else None

    # Adding the same material again increases quantity on the existing
    # active row, rather than creating a duplicate line - matches how
    # the previous client-side cart already behaved.
    existing = _my_items_query(db, auth).filter(PersonalCartItem.material_id == data.material_id).first()
    if existing:
        existing.quantity = existing.quantity + data.quantity
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize_cart_item(existing, auth.get("role", "user"))

    item = PersonalCartItem(
        user_id=auth.get("user_id"), material_id=material.id, material_name=material.name,
        unit=material.unit, quantity=data.quantity, supplier_id=data.supplier_id,
        supplier_name=supplier_name, rate=material.average_rate, note=data.note, status="ACTIVE",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_cart_item(item, auth.get("role", "user"))


@router.put("/{item_id}", response_model=PersonalCartItemResponse)
def update_cart_item(item_id: int, data: PersonalCartItemUpdate, db: Session = Depends(get_db),
                      auth=Depends(get_current_user)):
    item = _my_items_query(db, auth).filter(PersonalCartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    update_data = data.dict(exclude_unset=True)
    if "quantity" in update_data and update_data["quantity"] <= 0:
        snapshot = PersonalCartItemResponse(
            id=item.id, material_id=item.material_id, material_name=item.material_name, unit=item.unit,
            quantity=0, supplier_id=item.supplier_id, supplier_name=item.supplier_name,
            rate=item.rate if auth.get("role", "user") in ("master",) else None,
            note=item.note, status="REMOVED", created_at=item.created_at,
        )
        db.delete(item)
        db.commit()
        return snapshot
    for field, value in update_data.items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_cart_item(item, auth.get("role", "user"))


@router.delete("/{item_id}", status_code=204)
def remove_cart_item(item_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    item = _my_items_query(db, auth).filter(PersonalCartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()


@router.delete("/", status_code=204)
def clear_my_cart(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    _my_items_query(db, auth).delete(synchronize_session=False)
    db.commit()
