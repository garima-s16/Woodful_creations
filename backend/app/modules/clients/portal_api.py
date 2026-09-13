"""Client-facing portal - the PUBLIC, unauthenticated half of Family
137's Client Approval Hub (feature 1) and My Order link (feature 3).

Deliberately kept in its own file, separate from clients/api.py: every
route here has NO Depends(get_current_user)/require_role - access is
governed entirely by possession of a valid, unrevoked, unexpired
ClientAccessToken, a fundamentally different trust boundary from the
rest of this application. Keeping that boundary in its own file (and
its own router, registered separately in api/routes.py) makes it easy
to see at a glance that nothing here accidentally assumes an internal
staff session.

Every response shape here is hand-picked, never a reused internal
OrderResponse/EstimateResponse - the "do not expose internal ERP
information" requirement is enforced by what these schemas simply do
not have a field for, not by a redaction step that could be forgotten.

Defect repair (P1-13): client_portal_router is intentionally NOT
registered in app/api/routes.py anymore - Woodful is an internal-only
tool, and this router's entire design (no auth dependency of any
kind, reachable by anyone with a link) is exactly what that decision
rules out. The functions below are kept in place rather than deleted:
generate_client_access_token/build_client_link_email_footer are still
imported by app/modules/sales/api.py, where they now raise/no-op (see
that file's P1-13 comments) instead of silently minting links to a
route that no longer serves any requests. This file, the
ClientAccessToken/ClientActivity models, and the two migrations that
created them are left untouched - restricted, not removed - so this
is a one-line reversal (re-adding the router in routes.py) if that
product decision is ever revisited, not a rebuild from scratch."""
import hashlib
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.platform.database import get_db
from app.platform.audit import log_action
from app.modules.clients.models import ClientAccessToken, ClientActivity
from app.modules.sales.models import Estimate, Order, ApprovedSpecification
from app.modules.sales.services import validate_estimate_status_transition


client_portal_router = APIRouter(prefix="/api/client-portal", tags=["client-portal"])

CLIENT_DECIDABLE_ESTIMATE_STATUSES = {"sent", "changes_requested"}


def _hash_token(raw_token: str) -> str:
    """Same approach as app.modules.auth.auth._hash_token (SHA-256 of
    the raw token) - not imported directly to avoid coupling this
    public-facing file to the auth module for a one-line hash call."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_client_access_token(
    db: Session, subject_type: str, subject_id: int, purpose: str,
    created_by_user_id: Optional[int] = None, expires_at: Optional[datetime] = None,
) -> str:
    """Creates a new ClientAccessToken and returns the RAW token (only
    ever returned once, here, at creation time - only its hash is
    stored). Used by the staff-facing "generate client link" actions
    in sales/api.py, not called from this router itself."""
    raw_token = secrets.token_urlsafe(32)
    token = ClientAccessToken(
        token_hash=_hash_token(raw_token), purpose=purpose,
        subject_type=subject_type, subject_id=subject_id,
        created_by_user_id=created_by_user_id, expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    return raw_token


def build_client_link_email_footer(url: str, label: str) -> str:
    """Appended to an outgoing estimate/order email body so the
    persistent client-portal link travels with every communication
    that touches that estimate/order, per Family 137 features 1 and 3
    ("use the same persistent link in relevant future communications").

    Each call creates a genuinely new token (this file never stores a
    raw token, so an existing one can't be looked up and resent - see
    the ClientAccessToken docstring) rather than reusing one - but
    every token for the same subject/purpose points at the exact same
    live page, so the client-facing "one persistent My Order
    experience" is about the page being singular and always current,
    not about the token bytes staying identical across emails."""
    return f"\n\n---\n{label}: {url}"


def _resolve_token(db: Session, raw_token: str, purpose: str, subject_type: str) -> ClientAccessToken:
    """Looks up and validates a raw token from a URL, or raises a 404 -
    deliberately the same response for "no such token" and "token
    exists but is revoked/expired/wrong purpose", so a client-portal
    URL never distinguishes "this link is dead" from "this link never
    existed" to whoever is holding it."""
    token_hash = _hash_token(raw_token)
    token = db.query(ClientAccessToken).filter(ClientAccessToken.token_hash == token_hash).first()
    if (
        not token or token.is_revoked or token.purpose != purpose or token.subject_type != subject_type
        or (token.expires_at is not None and token.expires_at < datetime.utcnow())
    ):
        raise HTTPException(status_code=404, detail="This link is invalid or no longer active.")
    token.last_accessed_at = datetime.utcnow()
    token.access_count = (token.access_count or 0) + 1
    db.add(token)
    return token


# ============================================================
# Feature 1 - Client Approval Hub
# ============================================================

class ClientEstimateLineItemView(BaseModel):
    description: str
    quantity: float
    unit: str
    rate: float
    amount: float


class ClientEstimateVersionSummary(BaseModel):
    version: int
    status: str
    created_at: datetime


class ClientEstimateView(BaseModel):
    estimate_code: str
    client_name: str
    status: str
    valid_until: Optional[datetime] = None
    created_at: datetime
    line_items: List[ClientEstimateLineItemView]
    subtotal: float
    discount: float
    tax_percent: float
    tax_amount: float
    total_cost: float
    can_decide: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    client_decision_comments: Optional[str] = None
    other_versions: List[ClientEstimateVersionSummary] = []


class ClientEstimateDecision(BaseModel):
    name: str  # the client's own typed name - becomes Estimate.approved_by
    comments: Optional[str] = None


def _client_estimate_view(estimate: Estimate) -> ClientEstimateView:
    root_id = estimate.parent_estimate_id or estimate.id
    siblings = [estimate] + list(estimate.revisions or [])
    if estimate.parent_estimate and estimate.parent_estimate.id == root_id:
        siblings.append(estimate.parent_estimate)
    other_versions = [
        ClientEstimateVersionSummary(version=e.version, status=e.status, created_at=e.created_at)
        for e in siblings if e.id != estimate.id
    ]
    return ClientEstimateView(
        estimate_code=estimate.estimate_code,
        client_name=estimate.client.name if estimate.client else "",
        status=estimate.status, valid_until=estimate.valid_until, created_at=estimate.created_at,
        line_items=[
            ClientEstimateLineItemView(
                description=i.description, quantity=float(i.quantity), unit=i.unit,
                rate=float(i.rate), amount=float(i.amount),
            ) for i in estimate.line_items
        ],
        subtotal=float(estimate.subtotal), discount=float(estimate.discount or 0),
        tax_percent=float(estimate.tax_percent or 0), tax_amount=float(estimate.tax_amount or 0),
        total_cost=float(estimate.total_cost or 0),
        can_decide=estimate.status in CLIENT_DECIDABLE_ESTIMATE_STATUSES,
        approved_by=estimate.approved_by, approved_at=estimate.approved_at,
        client_decision_comments=estimate.client_decision_comments,
        other_versions=sorted(other_versions, key=lambda v: v.version),
    )


@client_portal_router.get("/estimates/{token}", response_model=ClientEstimateView)
def view_estimate(token: str, db: Session = Depends(get_db)):
    access = _resolve_token(db, token, purpose="estimate_approval", subject_type="estimate")
    estimate = db.query(Estimate).filter(Estimate.id == access.subject_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="This link is invalid or no longer active.")
    db.commit()
    return _client_estimate_view(estimate)


@client_portal_router.post("/estimates/{token}/approve", response_model=ClientEstimateView)
def approve_estimate(token: str, data: ClientEstimateDecision, request: Request, db: Session = Depends(get_db)):
    access = _resolve_token(db, token, purpose="estimate_approval", subject_type="estimate")
    estimate = db.query(Estimate).filter(Estimate.id == access.subject_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="This link is invalid or no longer active.")
    if estimate.status not in CLIENT_DECIDABLE_ESTIMATE_STATUSES:
        raise HTTPException(status_code=400, detail="This estimate is not currently awaiting a decision.")
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Please enter your name to approve this estimate.")

    error = validate_estimate_status_transition(estimate.status, "approved")
    if error:
        raise HTTPException(status_code=400, detail=error)

    estimate.status = "approved"
    estimate.approved_by = data.name.strip()
    estimate.approved_at = datetime.utcnow()
    estimate.client_decision_comments = data.comments.strip() if data.comments else None
    db.add(estimate)

    if estimate.client_id:
        db.add(ClientActivity(
            client_id=estimate.client_id, activity_type="Note", date=datetime.utcnow(),
            summary=f"Estimate {estimate.estimate_code} approved via client portal by {estimate.approved_by}."
                    + (f" Comment: {estimate.client_decision_comments}" if estimate.client_decision_comments else ""),
            logged_by="Client Portal",
        ))
    log_action(
        db, request, user_id=None, action="client_approved_estimate", module_name="estimates",
        record_id=estimate.id,
        old_value={"status": "sent"},
        new_value={"status": "approved", "approved_by": estimate.approved_by},
    )
    db.commit()
    db.refresh(estimate)
    return _client_estimate_view(estimate)


@client_portal_router.post("/estimates/{token}/request-changes", response_model=ClientEstimateView)
def request_estimate_changes(token: str, data: ClientEstimateDecision, request: Request, db: Session = Depends(get_db)):
    access = _resolve_token(db, token, purpose="estimate_approval", subject_type="estimate")
    estimate = db.query(Estimate).filter(Estimate.id == access.subject_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="This link is invalid or no longer active.")
    if estimate.status not in CLIENT_DECIDABLE_ESTIMATE_STATUSES:
        raise HTTPException(status_code=400, detail="This estimate is not currently awaiting a decision.")
    if not data.comments or not data.comments.strip():
        raise HTTPException(status_code=400, detail="Please describe what changes you'd like.")

    error = validate_estimate_status_transition(estimate.status, "changes_requested")
    if error:
        raise HTTPException(status_code=400, detail=error)

    estimate.status = "changes_requested"
    estimate.client_decision_comments = data.comments.strip()
    db.add(estimate)

    if estimate.client_id:
        db.add(ClientActivity(
            client_id=estimate.client_id, activity_type="Note", date=datetime.utcnow(),
            summary=f"Changes requested on estimate {estimate.estimate_code} via client portal"
                    + (f" by {data.name.strip()}" if data.name else "")
                    + f": {estimate.client_decision_comments}",
            logged_by="Client Portal",
        ))
    log_action(
        db, request, user_id=None, action="client_requested_estimate_changes", module_name="estimates",
        record_id=estimate.id,
        old_value={"status": "sent"},
        new_value={"status": "changes_requested", "comments": estimate.client_decision_comments},
    )
    db.commit()
    db.refresh(estimate)
    return _client_estimate_view(estimate)


# ============================================================
# Feature 3 - Client "My Order" Link
# ============================================================

class ClientOrderMilestoneView(BaseModel):
    name: str
    target_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None


class ClientApprovedSpecView(BaseModel):
    material: Optional[str] = None
    finish: Optional[str] = None
    veneer: Optional[str] = None
    laminate: Optional[str] = None
    colour: Optional[str] = None
    hardware: Optional[str] = None
    approved_at: datetime


class ClientOrderView(BaseModel):
    order_code: str
    client_name: str
    project_status: str
    order_date: datetime
    delivery_date: Optional[datetime] = None
    order_value: float
    amount_paid: float
    outstanding_balance: float
    approved_specification: Optional[ClientApprovedSpecView] = None
    milestones: List[ClientOrderMilestoneView] = []


@client_portal_router.get("/orders/{token}", response_model=ClientOrderView)
def view_order(token: str, db: Session = Depends(get_db)):
    """Read-only. No decision/mutation actions exist on this endpoint
    or anywhere else in this router for orders - the My Order link is
    purely informational, per Family 137 feature 3's spec."""
    access = _resolve_token(db, token, purpose="my_order", subject_type="order")
    order = db.query(Order).filter(Order.id == access.subject_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="This link is invalid or no longer active.")

    spec = (
        db.query(ApprovedSpecification)
        .filter(ApprovedSpecification.order_id == order.id, ApprovedSpecification.status == "approved")
        .order_by(ApprovedSpecification.version.desc())
        .first()
    )
    db.commit()
    return ClientOrderView(
        order_code=order.order_code, client_name=order.client.name if order.client else "",
        project_status=order.project_status, order_date=order.order_date, delivery_date=order.delivery_date,
        order_value=float(order.order_value or 0), amount_paid=float(order.total_received or 0),
        outstanding_balance=float(order.balance or 0),
        approved_specification=ClientApprovedSpecView(
            material=spec.material, finish=spec.finish, veneer=spec.veneer, laminate=spec.laminate,
            colour=spec.colour, hardware=spec.hardware, approved_at=spec.approved_at,
        ) if spec else None,
        milestones=[
            ClientOrderMilestoneView(name=m.name, target_date=m.target_date, completed_date=m.completed_date)
            for m in sorted(order.milestones, key=lambda m: m.target_date or datetime.max)
        ],
    )
