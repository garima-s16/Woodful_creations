from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.material import Material
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialResponse
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.get("/", response_model=List[MaterialResponse])
def list_materials(response: Response, category: Optional[str] = Query(None), search: Optional[str] = Query(None),
                    low_stock_only: bool = Query(False),
                    limit: Optional[int] = Query(None, ge=1, le=500),
                    offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Material)
    if category:
        query = query.filter(Material.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter((Material.name.ilike(like)) | (Material.material_code.ilike(like)))
    if low_stock_only:
        # Was previously filtered in Python after fetching everything -
        # moved into SQL so it composes correctly with pagination below
        # (filtering after paginating would silently return wrong pages).
        query = query.filter(Material.current_stock <= Material.minimum_stock)

    query = query.order_by(Material.name)
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if limit is not None:
        query = query.offset(offset).limit(limit)
        # Existing callers that never pass limit/offset get exactly the
        # same response shape as before this change - a plain array with
        # every matching row, no pagination applied.
    return query.all()


@router.post("/", response_model=MaterialResponse, status_code=201)
def create_material(data: MaterialCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    payload = data.dict(exclude={"material_code"})
    payload["current_stock"] = payload["opening_stock"]
    for _ in range(5):
        code = generate_unique_code(db, Material, "material_code", "MAT-")
        material = Material(**payload, material_code=code, business_id=generate_short_id())
        db.add(material)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
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
    for field, value in data.dict(exclude_unset=True).items():
        setattr(material, field, value)
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
