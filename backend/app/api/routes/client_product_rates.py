from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.audit import log_action
from app.models.client_product_rate import ClientProductRate
from app.models.product import Product
from app.models.estimate import Estimate
from app.schemas.client_product_rate import (
    ClientProductRateCreate, ClientProductRateUpdate, ClientProductRateResponse,
    PricingResolveRequest, PricingResolveResponse,
)
from app.utils.pricing_priority import resolve_selling_rate

router = APIRouter(prefix="/api/client-product-rates", tags=["client-product-rates"])


@router.get("/", response_model=List[ClientProductRateResponse])
def list_client_product_rates(
    client_id: Optional[int] = Query(None), product_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    # Master-only even to VIEW - these are negotiated commercial terms
    # per client, same sensitivity as any other pricing/cost data here.
    query = db.query(ClientProductRate)
    if client_id:
        query = query.filter(ClientProductRate.client_id == client_id)
    if product_id:
        query = query.filter(ClientProductRate.product_id == product_id)
    return query.all()


@router.post("/", response_model=ClientProductRateResponse, status_code=201)
def create_client_product_rate(data: ClientProductRateCreate, request: Request,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    if data.product_id is not None and not db.query(Product).filter(Product.id == data.product_id).first():
        raise HTTPException(status_code=400, detail="Invalid Product ID")
    from app.models.client import Client
    if not db.query(Client).filter(Client.id == data.client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")

    if data.product_id is None:
        existing_default = db.query(ClientProductRate).filter(
            ClientProductRate.client_id == data.client_id, ClientProductRate.product_id.is_(None),
        ).first()
        if existing_default:
            raise HTTPException(status_code=409, detail="This client already has a client-wide default margin - edit it instead.")

    rate = ClientProductRate(**data.dict(), created_by=auth.get("username") or str(auth.get("user_id")))
    db.add(rate)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A rate override for this client and product already exists - edit it instead.")
    db.refresh(rate)
    log_action(db, request, user_id=auth.get("user_id"), action="create_client_product_rate",
               module_name="client_product_rates", record_id=rate.id,
               new_value={"client_id": rate.client_id, "product_id": rate.product_id})
    return rate


@router.put("/{rate_id}", response_model=ClientProductRateResponse)
def update_client_product_rate(rate_id: int, data: ClientProductRateUpdate, request: Request,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    rate = db.query(ClientProductRate).filter(ClientProductRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate override not found")
    updates = data.dict(exclude_unset=True)
    for field, value in updates.items():
        setattr(rate, field, value)
    db.add(rate)
    db.commit()
    db.refresh(rate)
    log_action(db, request, user_id=auth.get("user_id"), action="update_client_product_rate",
               module_name="client_product_rates", record_id=rate.id, new_value={k: str(v) for k, v in updates.items()})
    return rate


@router.delete("/{rate_id}", status_code=204)
def delete_client_product_rate(rate_id: int, request: Request, db: Session = Depends(get_db),
                                auth=Depends(require_role("master"))):
    rate = db.query(ClientProductRate).filter(ClientProductRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate override not found")
    db.delete(rate)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_client_product_rate",
               module_name="client_product_rates", record_id=rate_id)


@router.post("/resolve", response_model=PricingResolveResponse)
def resolve_pricing(data: PricingResolveRequest, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    """Preview what rate/rule would apply for a given product+client(+
    estimate) combination, without saving anything - lets the Estimate
    UI show "Calculated Price" before the person commits to it."""
    if not data.product_id:
        raise HTTPException(status_code=400, detail="product_id is required to resolve a price")
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=400, detail="Invalid Product ID")

    cost = product.cost_price or product.suggested_cost_price
    if cost is None:
        cost = Decimal("0")
    cost = Decimal(str(cost))

    customer_fixed = None
    customer_margin = None
    if data.client_id:
        override = db.query(ClientProductRate).filter(
            ClientProductRate.client_id == data.client_id, ClientProductRate.product_id == data.product_id,
        ).first()
        if not override:
            override = db.query(ClientProductRate).filter(
                ClientProductRate.client_id == data.client_id, ClientProductRate.product_id.is_(None),
            ).first()
        if override:
            customer_fixed = override.fixed_selling_price
            customer_margin = override.margin_percent

    estimate_margin = None
    if data.estimate_id:
        estimate = db.query(Estimate).filter(Estimate.id == data.estimate_id).first()
        if estimate:
            estimate_margin = estimate.margin_percent_override

    result = resolve_selling_rate(
        cost=cost, explicit_override=data.explicit_override,
        customer_product_fixed_price=customer_fixed, customer_margin_percent=customer_margin,
        estimate_margin_percent=estimate_margin, product_margin_percent=product.margin_percent,
    )
    return PricingResolveResponse(
        selling_rate=result.selling_rate, pricing_rule_applied=result.pricing_rule_applied,
        margin_percent_used=result.margin_percent_used, cost_used=cost,
    )
