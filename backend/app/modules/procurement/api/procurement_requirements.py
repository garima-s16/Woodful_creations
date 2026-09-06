from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import require_role
from app.modules.procurement.models import ProcurementRequirement, SupplierDecision, SupplierMaterial
from app.modules.procurement.schemas import (
    ProcurementRequirementCreate, ProcurementRequirementUpdate, ProcurementRequirementResponse,
    SupplierDecisionCreate, SupplierDecisionResponse, RequirementPurchaseCreate,
)
from app.modules.inventory.schemas import PurchaseCreate, PurchaseResponse
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/procurement-requirements", tags=["procurement-requirements"])

# Financial/procurement-decision data - master-only throughout, matching
# the existing sensitivity tier for purchases/suppliers elsewhere in
# this module (see procurement/api/purchases.py, suppliers.py).


def _serialize_requirement(db: Session, requirement: ProcurementRequirement) -> ProcurementRequirementResponse:
    response = ProcurementRequirementResponse.model_validate(requirement)
    if requirement.material:
        response.material_name = requirement.material.name
    if requirement.decision:
        if requirement.decision.recommended_supplier:
            response.decision.recommended_supplier_name = requirement.decision.recommended_supplier.name
        if requirement.decision.selected_supplier:
            response.decision.selected_supplier_name = requirement.decision.selected_supplier.name
    return response


@router.get("/", response_model=List[ProcurementRequirementResponse])
def list_procurement_requirements(order_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                                   db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(ProcurementRequirement)
    if order_id:
        query = query.filter(ProcurementRequirement.order_id == order_id)
    if status:
        query = query.filter(ProcurementRequirement.status == status)
    rows = query.order_by(ProcurementRequirement.created_at.desc()).all()
    return [_serialize_requirement(db, r) for r in rows]


@router.post("/", response_model=ProcurementRequirementResponse, status_code=201)
def create_procurement_requirement(data: ProcurementRequirementCreate, db: Session = Depends(get_db),
                                    auth=Depends(require_role("master"))):
    """Snapshots the CURRENT shortage from the one authoritative
    calculation (StockService.calculate_order_material_requirements) -
    required/available/shortage are never accepted from the client,
    exactly the P0.2.1 requirement that this must not become a second,
    independently-drifting shortage engine."""
    from app.modules.inventory.stock_service import StockService

    result = StockService.calculate_order_material_requirements(db, data.order_id)
    row = next((r for r in result["materials"] if r["material_id"] == data.material_id), None)
    if row is None:
        raise HTTPException(
            status_code=400,
            detail="This order has no material requirement recorded for that material - nothing to snapshot.",
        )

    for _ in range(5):
        requirement = ProcurementRequirement(
            order_id=data.order_id, material_id=data.material_id,
            required_quantity=row["required"], available_quantity_at_creation=row["available"],
            shortage_quantity_at_creation=row["shortage"],
            priority=data.priority, required_by_date=data.required_by_date, remarks=data.remarks,
            created_by=auth.get("user_id"), business_id=generate_business_id(db),
        )
        db.add(requirement)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(requirement)
        return _serialize_requirement(db, requirement)
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{requirement_id}", response_model=ProcurementRequirementResponse)
def get_procurement_requirement(requirement_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    return _serialize_requirement(db, requirement)


@router.put("/{requirement_id}", response_model=ProcurementRequirementResponse)
def update_procurement_requirement(requirement_id: int, data: ProcurementRequirementUpdate,
                                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(requirement, field, value)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return _serialize_requirement(db, requirement)


@router.get("/{requirement_id}/supplier-options")
def get_requirement_supplier_options(requirement_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Read-only preview of the same recommendation
    record_supplier_decision itself uses - so the frontend can show
    "here are your options" before the Master commits to one. Not a
    second recommendation calculation: this and the decision endpoint
    both call ProcurementService._supplier_options_for_materials."""
    from app.modules.procurement.services import ProcurementService

    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    options = ProcurementService._supplier_options_for_materials(db, [requirement.material_id]).get(requirement.material_id, [])
    return {"requirement_id": requirement_id, "material_id": requirement.material_id, "options": options}


@router.post("/{requirement_id}/decision", response_model=SupplierDecisionResponse, status_code=201)
def record_supplier_decision(requirement_id: int, data: SupplierDecisionCreate, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    """Preserves the distinction P0.2.3 requires: what the system
    recommended versus what the Master actually chose. The
    recommendation is snapshotted here, at decision time, from the
    same supplier-options calculation the material-requirements
    endpoint already surfaces - never re-derived later, so a
    subsequent price change can never retroactively change what this
    decision recorded as "recommended" at the time it was made."""
    if data.requirement_id != requirement_id:
        raise HTTPException(status_code=400, detail="requirement_id in the path and body must match")
    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    if requirement.decision is not None:
        raise HTTPException(status_code=409, detail="A supplier decision has already been recorded for this requirement.")

    # P0.2.4: the selected supplier must actually be able to supply this
    # material - never trust a frontend dropdown to have filtered this
    # correctly. A supplier with no SupplierMaterial link for this exact
    # material is rejected here, in the backend, regardless of what the
    # client sent.
    valid_link = db.query(SupplierMaterial).filter(
        SupplierMaterial.supplier_id == data.selected_supplier_id,
        SupplierMaterial.material_id == requirement.material_id,
    ).first()
    if not valid_link:
        raise HTTPException(
            status_code=400,
            detail="The selected supplier has no recorded supply relationship for this material - "
                   "add a SupplierMaterial link first, or choose a different supplier.",
        )

    from app.modules.procurement.services import ProcurementService
    options = ProcurementService._supplier_options_for_materials(db, [requirement.material_id]).get(requirement.material_id, [])
    top = options[0] if options else None
    recommended_reason = None
    if top:
        recommended_reason = "Preferred supplier" if top.get("is_preferred") else "Lowest price"
        if top.get("lead_time_days") is not None:
            recommended_reason += f", {top['lead_time_days']}d lead time"

    for _ in range(5):
        decision = SupplierDecision(
            requirement_id=requirement_id,
            recommended_supplier_id=top["supplier_id"] if top else None,
            recommended_reason=recommended_reason,
            selected_supplier_id=data.selected_supplier_id, decision_reason=data.decision_reason,
            decided_by=auth.get("user_id"), business_id=generate_business_id(db),
        )
        db.add(decision)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(decision)
        response = SupplierDecisionResponse.model_validate(decision)
        if decision.recommended_supplier:
            response.recommended_supplier_name = decision.recommended_supplier.name
        if decision.selected_supplier:
            response.selected_supplier_name = decision.selected_supplier.name
        response.followed_recommendation = decision.followed_recommendation
        return response
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.post("/{requirement_id}/purchase", response_model=PurchaseResponse, status_code=201)
def create_purchase_from_requirement(requirement_id: int, data: RequirementPurchaseCreate,
                                      db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """P0.2.5 traceability: the resulting Purchase is persisted back onto
    the requirement (requirement.purchase_id), and a requirement that
    already has one cannot create a second - the two known failure
    modes section 12 names ("known related records become disconnected"
    and "fulfilled requirements incorrectly create another purchase")
    are both a single row-lock + two checks, not separate mechanisms.
    supplier_id/material_id for the Purchase come from the requirement's
    own recorded SupplierDecision, never from this request body, so the
    purchase can never disagree with the decision actually made."""
    from app.modules.procurement.services import ProcurementService

    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    if requirement.status in ("Fulfilled", "Cancelled"):
        raise HTTPException(status_code=409, detail=f"This requirement is already {requirement.status.lower()} - cannot create a purchase from it.")
    if requirement.purchase_id is not None:
        raise HTTPException(status_code=409, detail="A purchase has already been created for this requirement.")
    if requirement.decision is None:
        raise HTTPException(status_code=400, detail="Record a supplier decision for this requirement before creating a purchase.")

    purchase_data = PurchaseCreate(
        date=datetime.utcnow(), expected_delivery_date=data.expected_delivery_date,
        supplier_id=requirement.decision.selected_supplier_id, material_id=requirement.material_id,
        quantity=data.quantity, unit=data.unit, rate=data.rate, gst_percent=data.gst_percent,
        receipt_status=data.receipt_status, location_id=data.location_id,
    )
    purchase = ProcurementService.record_purchase(db, purchase_data)

    requirement.purchase_id = purchase.id
    # A purchase recorded as already fully "Received" means the goods
    # are already in hand - the requirement is genuinely fulfilled, not
    # merely ordered (matching section 14's "do not mark a requirement
    # fulfilled merely because a Purchase exists" - this is the one
    # case where the Purchase itself confirms receipt has truly
    # happened, not an assumption).
    requirement.status = "Fulfilled" if data.receipt_status == "Received" else "Ordered"
    db.add(requirement)
    db.commit()
    db.refresh(purchase)
    return purchase
