from typing import List, Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.material import Material
from app.models.material_category import MaterialSubcategory
from app.models.material_attribute import MaterialAttributeValue
from app.models.location import Location
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/materials", tags=["materials"])


def _try_decimal(value):
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@router.get("/", response_model=List[MaterialResponse])
def list_materials(response: Response, category: Optional[str] = Query(None), search: Optional[str] = Query(None),
                    low_stock_only: bool = Query(False), subcategory_id: Optional[int] = Query(None),
                    attribute_filters: Optional[str] = Query(
                        None, description='JSON object mapping attribute_definition_id to the desired value, '
                                           'e.g. {"5": "18", "7": "White"} - matched against either the numeric '
                                           'or text value depending on the attribute\'s own data type.'),
                    limit: Optional[int] = Query(None, ge=1, le=500),
                    offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Material)
    if category:
        query = query.filter(Material.category == category)
    if subcategory_id:
        query = query.filter(Material.subcategory_id == subcategory_id)
    if search:
        like = f"%{search}%"
        query = query.filter((Material.name.ilike(like)) | (Material.material_code.ilike(like)))
    if low_stock_only:
        # Was previously filtered in Python after fetching everything -
        # moved into SQL so it composes correctly with pagination below
        # (filtering after paginating would silently return wrong pages).
        query = query.filter(Material.current_stock <= Material.minimum_stock)
    if attribute_filters:
        try:
            filters = json.loads(attribute_filters)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="attribute_filters must be a valid JSON object")
        for attr_def_id_str, desired_value in filters.items():
            try:
                attr_def_id = int(attr_def_id_str)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid attribute_definition_id: {attr_def_id_str}")
            numeric_value = _try_decimal(desired_value)
            match_conditions = [MaterialAttributeValue.value_text == str(desired_value)]
            if numeric_value is not None:
                match_conditions.append(MaterialAttributeValue.value_number == numeric_value)
            matching_material_ids = db.query(MaterialAttributeValue.material_id).filter(
                MaterialAttributeValue.attribute_definition_id == attr_def_id,
                or_(*match_conditions),
            )
            # Each attribute filter narrows the result further (AND
            # across filters) - a material must match every selected
            # attribute value, not just any one of them.
            query = query.filter(Material.id.in_(matching_material_ids))

    query = query.order_by(Material.name)
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if limit is not None:
        query = query.offset(offset).limit(limit)
        # Existing callers that never pass limit/offset get exactly the
        # same response shape as before this change - a plain array with
        # every matching row, no pagination applied.
    return query.all()


def _resolve_category_name(db: Session, subcategory_id):
    """The legacy category string stays in sync with the subcategory's
    parent category name whenever subcategory_id is set - this is what
    keeps every existing consumer (dashboard, chatbot, PDF/Excel,
    low-stock filtering) correct without needing to touch them."""
    if not subcategory_id:
        return None
    subcategory = db.query(MaterialSubcategory).filter(MaterialSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return subcategory.category.name


def _resolve_location_path(db: Session, location_id):
    """Same sync pattern as category - the legacy location string stays
    in sync with the new Location's full_path whenever location_id is set."""
    if not location_id:
        return None
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location.full_path


def _apply_attribute_values(db: Session, material: Material, attribute_values):
    """Replaces the material's full attribute value set - matching the
    same "submit the current complete list" semantics already used for
    estimate/order line items, not an incremental patch."""
    for existing in list(material.attribute_values):
        db.delete(existing)
    db.flush()
    for item in attribute_values:
        db.add(MaterialAttributeValue(
            material_id=material.id, attribute_definition_id=item.attribute_definition_id,
            value_text=item.value_text, value_number=item.value_number,
        ))


@router.post("/", response_model=MaterialResponse, status_code=201)
def create_material(data: MaterialCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    payload = data.dict(exclude={"material_code", "attribute_values"})
    payload["current_stock"] = payload["opening_stock"]
    if data.subcategory_id:
        payload["category"] = _resolve_category_name(db, data.subcategory_id)
    if data.location_id:
        payload["location"] = _resolve_location_path(db, data.location_id)

    for _ in range(5):
        code = generate_unique_code(db, Material, "material_code", "MAT-")
        material = Material(**payload, material_code=code, business_id=generate_short_id())
        db.add(material)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        if data.attribute_values:
            _apply_attribute_values(db, material, data.attribute_values)
        db.commit()
        db.refresh(material)
        return material
    raise HTTPException(status_code=500, detail="Unable to generate a unique material code, please try again")


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

    update_data = data.dict(exclude_unset=True, exclude={"attribute_values"})
    if "subcategory_id" in update_data:
        update_data["category"] = _resolve_category_name(db, update_data["subcategory_id"])
    if "location_id" in update_data:
        update_data["location"] = _resolve_location_path(db, update_data["location_id"])
    for field, value in update_data.items():
        setattr(material, field, value)

    if data.attribute_values is not None:
        _apply_attribute_values(db, material, data.attribute_values)

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
