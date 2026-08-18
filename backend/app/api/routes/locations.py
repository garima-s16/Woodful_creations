from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.location import Location
from app.schemas.location import LocationCreate, LocationResponse, LocationTreeResponse
from app.utils.id_generator import generate_short_id

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.get("/", response_model=List[LocationResponse])
def list_locations(parent_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    """Flat list, optionally filtered to one parent's direct children -
    what a "choose a location" dropdown actually needs. Use /tree for
    the full nested structure."""
    query = db.query(Location)
    if parent_id is not None:
        query = query.filter(Location.parent_id == parent_id)
    return query.order_by(Location.name).all()


@router.get("/tree", response_model=List[LocationTreeResponse])
def get_location_tree(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Every top-level location (no parent) with its full descendant
    tree nested inside - what the warehouse browser view needs."""
    return db.query(Location).filter(Location.parent_id.is_(None)).order_by(Location.name).all()


@router.post("/", response_model=LocationResponse, status_code=201)
def create_location(data: LocationCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    if data.parent_id is not None:
        if not db.query(Location).filter(Location.id == data.parent_id).first():
            raise HTTPException(status_code=404, detail="Parent location not found")
    if db.query(Location).filter(Location.parent_id == data.parent_id, Location.name == data.name).first():
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under this parent.')

    location = Location(**data.dict(), business_id=generate_short_id())
    db.add(location)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under this parent.')
    db.refresh(location)
    return location


@router.get("/{location_id}", response_model=LocationResponse)
def get_location(location_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location
