"""Family P0.49 (Cross-Module Business Risk) + P0.51 (Business
Decision Centre) API. Given its own router/prefix rather than folded
into dashboard.py's widget list, so a developer searching for
"business risk" or "business decision" finds this file directly
(section 4's discoverability requirement) - the underlying
calculation still lives in business_risk_service.py, reusing
OrderService.compute_order_health and SalarySlip data rather than
recalculating anything."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user
from app.modules.reporting.business_risk_service import get_business_risks, get_risk_for_entity

router = APIRouter(prefix="/api/business-decisions", tags=["business-decisions"])


@router.get("/")
def list_business_decisions(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The P0.51 Business Decision Centre's single data source: a
    prioritized list of cross-module business risks plus a summary
    count. Financial/payroll risk items are only included for MASTER
    (sections 17/18/21) - an employee genuinely receives a shorter
    list, not a redacted copy of the same one."""
    is_privileged = auth.get("role", "user") in ("master",)
    return get_business_risks(db, is_privileged)


@router.get("/{entity_type}/{entity_id}")
def get_business_decision_for_entity(entity_type: str, entity_id: int,
                                      db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Section 19's AI contract - "why is this order at risk" needs one
    structured item, not the full list. Returns 404 both when the
    entity has no current risk and when the caller isn't authorized to
    see it (a non-privileged caller asking about a salary slip gets
    the same 404 as asking about one that doesn't exist - never a
    distinguishable "exists but you can't see it" leak)."""
    is_privileged = auth.get("role", "user") in ("master",)
    if entity_type not in ("order", "salary_slip", "salary_advance"):
        raise HTTPException(status_code=404, detail="No business decision found for this entity")
    result = get_risk_for_entity(db, entity_type, entity_id, is_privileged)
    if not result:
        raise HTTPException(status_code=404, detail="No business decision found for this entity")
    return result
