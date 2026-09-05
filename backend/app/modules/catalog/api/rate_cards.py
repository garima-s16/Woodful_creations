from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.audit.audit import log_action
from app.modules.catalog.models import RateCard
from app.modules.catalog.schemas import RateCardCreate, RateCardUpdate, RateCardOverride, RateCardResponse
from app.platform.database.id_generator import generate_unique_code, generate_business_id

router = APIRouter(prefix="/api/rate-cards", tags=["rate-cards"])


@router.get("/", response_model=List[RateCardResponse])
def list_rate_cards(
    response: Response,
    category: Optional[str] = Query(None), search: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None), confidence: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),  # defaults to current rates only
    limit: int = Query(500, ge=1, le=500), offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    query = db.query(RateCard)
    if category:
        query = query.filter(RateCard.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(RateCard.item_name.ilike(like), RateCard.specification.ilike(like),
                                  RateCard.rate_code.ilike(like)))
    if source_type:
        query = query.filter(RateCard.source_type == source_type)
    if confidence:
        query = query.filter(RateCard.confidence == confidence)
    if is_active is not None:
        query = query.filter(RateCard.is_active == is_active)
    total = query.count()
    response.headers["X-Total-Count"] = str(total)
    return query.order_by(RateCard.category, RateCard.item_name).offset(offset).limit(limit).all()


@router.get("/{rate_id}", response_model=RateCardResponse)
def get_rate_card(rate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    rate = db.query(RateCard).filter(RateCard.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    return rate


@router.get("/{rate_id}/history", response_model=List[RateCardResponse])
def get_rate_history(rate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Walks the supersedes_id chain both backward (older versions)
    and forward (newer versions superseding this one), so the full
    version history of one item's rate is visible regardless of which
    version's ID the caller started from."""
    rate = db.query(RateCard).filter(RateCard.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    chain = [rate]
    cursor = rate
    while cursor.supersedes_id:
        cursor = db.query(RateCard).filter(RateCard.id == cursor.supersedes_id).first()
        if not cursor:
            break
        chain.append(cursor)
    newer = db.query(RateCard).filter(RateCard.supersedes_id == rate.id).first()
    forward_chain = []
    while newer:
        forward_chain.insert(0, newer)
        newer = db.query(RateCard).filter(RateCard.supersedes_id == newer.id).first()
    return forward_chain + chain


@router.post("/", response_model=RateCardResponse, status_code=201)
def create_rate_card(data: RateCardCreate, request: Request, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"rate_code"})
    for _ in range(5):
        code = generate_unique_code(db, RateCard, "rate_code", "RATE-")
        rate = RateCard(**payload, rate_code=code, business_id=generate_business_id(db))
        db.add(rate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        db.commit()
        db.refresh(rate)
        log_action(db, request, user_id=auth.get("user_id"), action="create_rate_card", module_name="rate_cards",
                   record_id=rate.id, new_value={"item_name": rate.item_name, "category": rate.category})
        return rate
    raise HTTPException(status_code=500, detail="Unable to generate a unique rate code, please try again")


@router.put("/{rate_id}", response_model=RateCardResponse)
def revise_rate_card(rate_id: int, data: RateCardUpdate, request: Request, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    """"Never overwrite historical rates used by old estimates/orders. A
    new rate creates a new effective version" - this endpoint name is
    PUT for REST convention, but it never mutates the existing row's
    price-bearing fields: it deactivates the old RateCard (effective_to
    = now, is_active = False) and creates a brand new one that
    supersedes it, copying forward any field the caller didn't
    explicitly change. Anything that already snapshotted the old
    rate_card_id (an Estimate/Order line item) keeps reading the exact
    old numbers - only new lookups see the new version."""
    old = db.query(RateCard).filter(RateCard.id == rate_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="Rate not found")

    updates = data.dict(exclude_unset=True)
    carried_forward = {
        "category": old.category, "subcategory": old.subcategory, "item_name": old.item_name,
        "specification": old.specification, "location": old.location, "uom": old.uom,
        "market_reference_rate": old.market_reference_rate, "woodful_cost_rate": old.woodful_cost_rate,
        "woodful_selling_rate": old.woodful_selling_rate, "overhead_percent": old.overhead_percent,
        "target_margin_percent": old.target_margin_percent, "wastage_percent": old.wastage_percent,
        "tax_percent": old.tax_percent, "source_type": old.source_type,
        "source_reference": old.source_reference, "confidence": old.confidence, "notes": old.notes,
        "effective_from": datetime.utcnow(),
    }
    carried_forward.update(updates)

    old.is_active = False
    old.effective_to = carried_forward["effective_from"]
    db.add(old)

    for _ in range(5):
        code = generate_unique_code(db, RateCard, "rate_code", "RATE-")
        new_rate = RateCard(**carried_forward, rate_code=code, business_id=generate_business_id(db),
                             supersedes_id=old.id, is_active=True)
        db.add(new_rate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        db.commit()
        db.refresh(new_rate)
        log_action(db, request, user_id=auth.get("user_id"), action="revise_rate_card", module_name="rate_cards",
                   record_id=new_rate.id, old_value={"superseded_rate_id": old.id},
                   new_value={k: str(v) for k, v in updates.items()})
        return new_rate
    raise HTTPException(status_code=500, detail="Unable to generate a unique rate code, please try again")


@router.post("/{rate_id}/override", response_model=RateCardResponse)
def override_rate_card(rate_id: int, data: RateCardOverride, request: Request, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    """MASTER manual override of the calculated selling rate - recorded
    alongside, never replacing, the calculated woodful_selling_rate
    (spec: "Do not silently overwrite the calculated price"). See
    RateCard.effective_selling_rate for which one a caller should
    actually use."""
    rate = db.query(RateCard).filter(RateCard.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    old_override = rate.override_price
    rate.override_price = data.override_price
    rate.override_by = auth.get("username") or str(auth.get("user_id"))
    rate.override_at = datetime.utcnow()
    rate.override_reason = data.override_reason
    db.add(rate)
    db.commit()
    db.refresh(rate)
    log_action(db, request, user_id=auth.get("user_id"), action="override_rate_card", module_name="rate_cards",
               record_id=rate.id, old_value={"override_price": str(old_override) if old_override else None},
               new_value={"override_price": str(data.override_price), "reason": data.override_reason})
    return rate


@router.post("/{rate_id}/deactivate", response_model=RateCardResponse)
def deactivate_rate_card(rate_id: int, request: Request, db: Session = Depends(get_db),
                          auth=Depends(require_role("master"))):
    rate = db.query(RateCard).filter(RateCard.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    rate.is_active = False
    rate.effective_to = datetime.utcnow()
    db.add(rate)
    db.commit()
    db.refresh(rate)
    log_action(db, request, user_id=auth.get("user_id"), action="deactivate_rate_card", module_name="rate_cards",
               record_id=rate.id, new_value={"is_active": False})
    return rate
