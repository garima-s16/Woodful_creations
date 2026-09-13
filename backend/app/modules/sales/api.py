"""Sales domain API routes: orders, order imports, estimates,
estimate imports, payments, and exports. Combines the former
orders.py, order_imports.py, estimates.py, estimate_imports.py,
payments.py, and reports.py."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.platform.audit import log_action, serializable_fields
from app.modules.sales.models import Order, OrderComment, OrderItem, Estimate, Payment, ApprovedSpecification
from app.modules.clients.models import Client, ClientActivity
from app.modules.reporting.services import AIWorkspaceReport
from app.modules.catalog.models import Product
from app.modules.operations.models import DailyTask, TaskComment
from app.modules.operations.models import Milestone
from app.modules.communications.models import Notification
from app.modules.sales.schemas import OrderCreate, OrderUpdate, OrderResponse, OrderCommentCreate, OrderCommentResponse
from app.modules.sales.schemas import ApprovedSpecificationCreate, ApprovedSpecificationResponse
from app.modules.sales.schemas import CostDriftLineItem, CostDriftResponse
from app.modules.sales.schemas import MarginOptimizationRequest, MarginOptimizationResponse, MarginOptimizationSuggestion
from app.modules.sales.schemas import DeliveryPromiseRecord
from app.modules.clients.services import ClientEmailPreview, ClientEmailSendRequest, ClientEmailSendResult
from app.modules.sales.exports import generate_order_estimate_pdf, generate_invoice_pdf
from app.modules.communications.services import EmailService
from app.modules.sales.services import OrderService
from app.modules.inventory.services import StockService
from app.modules.communications.services import NotificationService
from app.modules.communications.services import notify_mentions
from app.platform.ids import generate_unique_code, generate_business_id
from app.modules.sales.services import validate_order_status_value, validate_order_project_status_transition
from app.modules.sales.services import compute_totals
from datetime import datetime, timedelta
from decimal import Decimal
from datetime import datetime
import zipfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy import update as sa_update
from fastapi.responses import StreamingResponse
from app.platform.config import settings
from app.platform.security import require_role
from app.platform.audit import log_action
from app.modules.clients.models import Client
from app.modules.sales.models import Estimate, Order, OrderItem
from app.modules.sales.imports import (
    build_order_import_template, parse_order_uploaded_workbook,
    validate_order_header_row, validate_order_item_row,
    normalize_match_key, normalize_phone_key,
    ORDER_LOCKED_STATUSES,
)
from app.modules.sales.imports import (
    OrderImportPreviewResponse, OrderImportHeaderPreview, OrderImportItemPreview,
    OrderImportCommitRequest, OrderImportCommitResult, OrderImportCommitResultRow,
)
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.modules.sales.models import Estimate, EstimateLineItem, Order
from app.modules.sales.schemas import EstimateCreate, EstimateUpdate, EstimateResponse
from app.modules.sales.services import (
    validate_estimate_status_transition, ESTIMATE_FINALIZED_STATUSES,
)
from app.modules.sales.services import compute_totals as _compute_totals
from app.modules.sales.exports import generate_estimate_pdf
from app.modules.clients.models import ClientActivity
from app.modules.sales.services import ESTIMATE_FINALIZED_STATUSES
from app.modules.sales.imports import (
    build_estimate_import_template, parse_estimate_uploaded_workbook,
    validate_estimate_header_row, validate_estimate_item_row,
    normalize_match_key, normalize_phone_key,
)
from app.modules.sales.imports import (
    EstimateImportPreviewResponse, EstimateImportHeaderPreview, EstimateImportItemPreview,
    EstimateImportCommitRequest, EstimateImportCommitResult, EstimateImportCommitResultRow,
)
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from fastapi import Request
from app.modules.sales.models import Payment, PaymentDocument, Order
from app.modules.sales.schemas import PaymentCreate, PaymentUpdate, PaymentResponse, PaymentDocumentResponse
from app.modules.sales.exports import generate_invoice_pdf
from app.shared import validate_file_signature
from app.platform.storage import get_storage_backend, get_storage_backend_for_record
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.platform.security import rate_limit
from app.modules.sales.models import Order, Estimate, Payment
from app.shared import build_workbook, xlsx_response
from app.modules.sales.exports import generate_order_estimate_pdf, generate_estimate_pdf, generate_invoice_pdf


# --- orders.py ---
orders_router = APIRouter(prefix="/api/orders", tags=["orders"])


def _serialize_orders(orders, role: str, db: Session = None, precomputed_attention_flags: dict = None):
    """Employees can see order status/progress/client/project info, but
    not money - order_value, discount, tax_percent, tax_amount, advance,
    other_received, total_received, balance, items_subtotal, and
    payment_status are genuinely nulled here, including each order
    item's rate/amount (redacting only the order-level total while
    leaving line-item pricing visible would let anyone just sum the
    items back to the real total).

    Also attaches the batched, non-material needs_attention flag (s.11)
    when a db session is supplied - callers serializing a single
    already-fetched order without one (e.g. after create/update) simply
    don't get the flag rather than triggering an extra query for it.
    precomputed_attention_flags lets a caller that already ran
    bulk_attention_flags for a larger set (e.g. the risk-sort path,
    which must classify every matching order before pagination) pass
    those results straight through instead of this function silently
    re-querying the same thing a second time for just this subset."""
    responses = [OrderResponse.model_validate(o) for o in orders]
    if role not in ("master",):
        for r in responses:
            r.order_value = None
            r.discount = None
            r.tax_percent = None
            r.tax_amount = None
            r.advance = None
            r.other_received = None
            r.total_received = None
            r.balance = None
            r.items_subtotal = None
            r.payment_status = None
            for item in r.items:
                item.rate = None
                item.amount = None
    if precomputed_attention_flags is not None:
        flags = precomputed_attention_flags
    elif db is not None and responses:
        flags = OrderService.bulk_attention_flags(db, [r.id for r in responses])
    else:
        flags = {}
    for r in responses:
        flag = flags.get(r.id)
        if flag:
            r.needs_attention = flag["needs_attention"]
            r.attention_reason = flag["reason"]
            r.attention_risk_level = flag["risk_level"]
    return responses


def _serialize_order(order, role: str, db: Session = None):
    return _serialize_orders([order], role, db)[0]


@orders_router.get("/", response_model=List[OrderResponse])
def list_orders(response: Response, status: Optional[str] = Query(None), client_id: Optional[int] = Query(None),
                 priority: Optional[str] = Query(None),
                 overdue_only: bool = Query(False),
                 active_only: bool = Query(False),
                 upcoming_delivery_within_days: Optional[int] = Query(None, ge=1, le=365),
                 limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                 sort: Optional[str] = Query(None, description="Set to 'risk' to sort by delivery-risk severity"),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    # Eager-loaded: OrderResponse serializes each order's items (and,
    # via items_subtotal) and source_estimate_id/source_estimate_code
    # (via the estimates relationship) for every row returned - without
    # this, listing a page of orders was an N+1 (2 extra queries per
    # order, not just per page).
    query = db.query(Order).options(selectinload(Order.items), selectinload(Order.estimates))
    if status:
        query = query.filter(Order.project_status == status)
    if client_id:
        query = query.filter(Order.client_id == client_id)
    if priority:
        query = query.filter(Order.priority == priority)
    if active_only:
        # Defect repair (P1-8) - for a "pick a project to assign this
        # to" dropdown (Employee Detail's task/production-job forms
        # and similar pickers elsewhere), not a report. Same
        # active-order definition already used by the dashboard's
        # active_order_ids (app/modules/reporting/api.py) - a
        # Completed order is never a valid assignment target anyway,
        # so this both bounds the result AND keeps the picker itself
        # meaningful, rather than a caller silently relying on the
        # generic `limit` default (100) and truncating an
        # unfiltered, irrelevantly-ordered list once the business has
        # more than 100 orders total.
        query = query.filter(Order.project_status != "Completed")
    if overdue_only:
        # Same rule the frontend used to apply client-side: balance still
        # outstanding and the order was placed more than 30 days ago.
        # There is no due-date field on Order, so this is a stated
        # approximation, not a precise "overdue" status - kept in SQL now
        # so it composes correctly with pagination below.
        cutoff = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Order.balance > 0, Order.order_date < cutoff)
    if upcoming_delivery_within_days is not None:
        # Dashboard "upcoming deliveries" widget - was previously
        # ordersAPI.list() with NO filter (the entire order table,
        # forever) filtered/sliced client-side in React. Same rule,
        # in SQL: has a delivery_date, not already Completed, and that
        # date falls within the next N days.
        now = datetime.utcnow()
        cutoff = now + timedelta(days=upcoming_delivery_within_days)
        query = query.filter(
            Order.delivery_date.isnot(None), Order.delivery_date >= now, Order.delivery_date <= cutoff,
            Order.project_status != "Completed",
        )
        query = query.order_by(Order.delivery_date.asc())
    elif sort == "risk":
        # Risk-priority sort (P0.50 s.19) needs every matching order's
        # risk classified BEFORE pagination, not just the page - a
        # CRITICAL order 200 rows in must still surface on page 1.
        # bulk_attention_flags is still a fixed, small number of
        # queries regardless of how many order_ids are passed in (see
        # its own docstring) - this does not turn into a per-order N+1.
        all_ids = [r[0] for r in query.with_entities(Order.id).all()]
        total = len(all_ids)
        response.headers["X-Total-Count"] = str(total)
        flags = OrderService.bulk_attention_flags(db, all_ids) if all_ids else {}
        priority = {"CRITICAL": 0, "AT_RISK": 1, "WATCH": 2, "ON_TRACK": 3}
        sorted_ids = sorted(all_ids, key=lambda oid: priority.get(flags.get(oid, {}).get("risk_level"), 3))
        page_ids = sorted_ids[offset:offset + limit]
        if not page_ids:
            return []
        orders_by_id = {o.id: o for o in query.filter(Order.id.in_(page_ids)).all()}
        # Re-apply the risk-priority order - the IN-query above does not
        # preserve page_ids' order.
        ordered_page = [orders_by_id[oid] for oid in page_ids if oid in orders_by_id]
        return _serialize_orders(ordered_page, auth.get("role", "user"), db, precomputed_attention_flags=flags)
    else:
        query = query.order_by(Order.order_date.desc())

    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    return _serialize_orders(query.offset(offset).limit(limit).all(), auth.get("role", "user"), db)


def _build_order_items(db, items_data, order_id: int = None):
    """Computes amount = quantity * rate server-side for each item -
    never trusted from client input directly, matching the estimate
    line items pattern (including ROUND_HALF_UP - Python's default
    quantize rounding is banker's rounding, which would silently
    disagree with how estimate amounts are computed for the exact same
    calculation).

    Also validates every supplied product_id actually references a
    real, active Product Master row - order line items must reference
    the actual Product records used by the ERP, not just any integer, and product_id
    is now mandatory - Pydantic already rejects a missing one with
    "Product ID is required" before this function ever runs."""
    from decimal import Decimal, ROUND_HALF_UP

    product_ids = {item.product_id for item in items_data if item.product_id is not None}
    if product_ids:
        found_products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
        missing = product_ids - set(found_products.keys())
        if missing:
            raise HTTPException(status_code=400, detail="Invalid Product ID")
        inactive = [p.name for p in found_products.values() if not p.is_active]
        if inactive:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use inactive product(s) on a new order: {', '.join(inactive)}",
            )

    result = []
    for idx, item in enumerate(items_data):
        amount = (item.quantity * item.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.append(OrderItem(
            order_id=order_id, description=item.description, category=item.category,
            quantity=item.quantity, unit=item.unit, rate=item.rate, amount=amount, sort_order=idx,
            product_id=item.product_id, is_custom_item=item.is_custom_item,
        ))
    return result


@orders_router.post("/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, request: Request, db: Session = Depends(get_db),
                  auth=Depends(require_role("master"))):
    from decimal import Decimal
    from app.modules.clients.services import find_or_create_client

    payload = data.dict(exclude={
        "order_code", "advance", "items", "from_estimate_id",
        "client_name", "client_phone", "client_email", "client_contact_person",
        "client_address", "client_city", "client_lead_source",
    })

    source_estimate = None
    if data.from_estimate_id:
        source_estimate = db.query(Estimate).filter(Estimate.id == data.from_estimate_id).first()
        if not source_estimate:
            raise HTTPException(status_code=404, detail="Source estimate not found")
        if source_estimate.status != "approved":
            raise HTTPException(
                status_code=400,
                detail=f"Only an approved estimate can be converted into an order "
                        f"(this estimate is '{source_estimate.status}').",
            )
        if source_estimate.order_id:
            raise HTTPException(status_code=400, detail="This estimate has already been converted to an order.")

    client_was_created = False
    if source_estimate:
        # The estimate's own client is authoritative for a conversion -
        # a converted order must belong to the same client the estimate
        # was for, never a different client_id/client_name the request
        # might also carry (whether by mistake or a manipulated
        # payload). The frontend's own convert-to-order flow already
        # only ever sends the estimate's own client_id here anyway, so
        # this changes nothing for the legitimate path.
        client = db.query(Client).filter(Client.id == source_estimate.client_id).first()
        if not client:
            raise HTTPException(status_code=400, detail="The estimate's client could not be found.")
    elif data.client_id is not None:
        client = db.query(Client).filter(Client.id == data.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
    else:
        # Client recognition intake (see app/modules/clients/services.py):
        # reuses an existing client only when BOTH name and phone match;
        # otherwise creates a new client here, in the same request, so
        # the order never ends up pointing at a client_id that doesn't
        # really represent this person.
        try:
            client, client_was_created = find_or_create_client(
                db, data.client_name, data.client_phone,
                email=data.client_email, contact_person=data.client_contact_person,
                address=data.client_address, city=data.client_city, lead_source=data.client_lead_source,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        if client_was_created:
            # Committed on its own, separate from the order's own
            # retry-on-order-code-collision loop below - otherwise a
            # rollback from an order_code collision would also undo
            # this brand-new client, and the retry would then try to
            # reuse a client.id that no longer exists.
            db.commit()
            db.refresh(client)
    payload["client_id"] = client.id
    advance = data.advance

    if source_estimate and source_estimate.line_items:
        # Copy items from the estimate's line items rather than re-enter
        # them - each new OrderItem stays traceable back to the
        # estimate line it came from via source_estimate_item_id.
        order_items = [
            OrderItem(
                description=li.description, category=li.category, quantity=li.quantity,
                unit=li.unit, rate=li.rate, amount=li.amount,
                source_estimate_item_id=li.id, sort_order=idx, product_id=li.product_id,
                is_custom_item=li.is_custom_item, pricing_rule_applied=li.pricing_rule_applied,
                applied_margin_percent=li.applied_margin_percent,
            )
            for idx, li in enumerate(source_estimate.line_items)
        ]
    elif data.items:
        order_items = _build_order_items(db, data.items)
    else:
        order_items = []

    # Discount/tax_percent: when converting from an estimate, inherit
    # the estimate's own values unless the caller explicitly overrode
    # them - discount and GST are preserved from the Estimate unless
    # explicitly overridden. model_fields_set distinguishes
    # "caller sent discount explicitly" from "used the schema default".
    explicit_fields = data.model_fields_set
    discount = data.discount if "discount" in explicit_fields or not source_estimate else source_estimate.discount
    tax_percent = data.tax_percent if "tax_percent" in explicit_fields or not source_estimate else source_estimate.tax_percent

    if order_items:
        items_subtotal = sum((i.amount for i in order_items), Decimal("0"))
        tax_amount, grand_total = compute_totals(items_subtotal, discount, tax_percent)
        payload["order_value"] = grand_total
    else:
        # No line items at all - a bare order with just a caller-supplied
        # total (e.g. a quick internal-work order). discount/tax still
        # apply to whatever order_value was given, same formula.
        tax_amount, grand_total = compute_totals(data.order_value, discount, tax_percent)
        payload["order_value"] = grand_total
    payload["discount"] = discount
    payload["tax_percent"] = tax_percent

    if advance > payload["order_value"]:
        raise HTTPException(
            status_code=400,
            detail=f"Advance (Rs {advance}) cannot exceed the order value (Rs {payload['order_value']}).",
        )

    year = datetime.utcnow().year
    for _ in range(5):
        code = generate_unique_code(db, Order, "order_code", f"WC-{year}-")
        order = Order(**payload, order_code=code, business_id=generate_business_id(db),
                      advance=advance, total_received=advance, balance=payload["order_value"] - advance,
                      tax_amount=tax_amount)
        db.add(order)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        for item in order_items:
            item.order_id = order.id
            db.add(item)
        if source_estimate:
            # Compare-and-swap: only claims the estimate if order_id is
            # still NULL, checked and set in one atomic statement rather
            # than a separate read-then-write - two concurrent conversion
            # requests (e.g. a doubled-up button click) racing past the
            # earlier order_id check above can't both win here. The
            # loser's whole order (and its items, still uncommitted)
            # rolls back rather than leaving an order that no longer has
            # a valid claim on its source estimate.
            #
            # status="closed" is set in this SAME atomic statement -
            # a converted estimate is automatically closed, distinct
            # from merely "approved" (approved-but-not-yet-converted
            # vs approved-and-now-an-order are different, useful
            # states to tell apart in the Estimate list/detail UI).
            from sqlalchemy import update as sa_update
            claim_result = db.execute(
                sa_update(Estimate.__table__)
                .where(Estimate.id == source_estimate.id, Estimate.order_id.is_(None))
                .values(order_id=order.id, status="closed")
            )
            if claim_result.rowcount != 1:
                db.rollback()
                raise HTTPException(status_code=409, detail="This estimate has already been converted to an order.")
        db.commit()
        db.refresh(order)
        log_action(db, request, user_id=auth.get("user_id"),
                   action="convert_estimate_to_order" if source_estimate else "create_order",
                   module_name="orders",
                   record_id=order.id, new_value={
                       "client_id": order.client_id, "order_code": order.order_code,
                       "order_value": float(order.order_value or 0), "advance": float(order.advance or 0),
                       "client_created_via_recognition": client_was_created,
                       "source_estimate_id": source_estimate.id if source_estimate else None,
                       "source_estimate_code": source_estimate.estimate_code if source_estimate else None,
                   })
        if source_estimate:
            # Separate entry on the Estimate's own audit trail (not just
            # the Order's) - so "when did this estimate close" is
            # discoverable from the estimate side too.
            log_action(db, request, user_id=auth.get("user_id"), action="close_estimate", module_name="estimates",
                       record_id=source_estimate.id, old_value={"status": "approved"},
                       new_value={"status": "closed", "order_id": order.id, "order_code": order.order_code})
        return order
    raise HTTPException(status_code=500, detail="Unable to generate a unique order code, please try again")


@orders_router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _serialize_order(order, auth.get("role", "user"))


@orders_router.get("/{order_id}/dispatch-check")
def check_dispatch_readiness(order_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family 137, feature 4 (Balance-Before-Dispatch Guardrail) - a
    read-only precheck the frontend calls before showing a "mark as
    delivered/dispatched" confirmation, so the outstanding balance is
    explained BEFORE the person attempts the change, not only as a
    rejection after they submit it. The actual enforcement lives in
    update_order - this endpoint changes nothing, it only explains what
    that endpoint would do. DATA -> INSIGHT: this is the insight step;
    the human still makes the call on the update_order request.

    master-only: update_order itself (the action this precheck exists
    to explain) already requires the master role, so there is no
    legitimate non-master caller of this endpoint - and outstanding
    balance is financial data, redacted to non-master roles everywhere
    else in this app (see _serialize_orders). A get_current_user-only
    version of this endpoint would have quietly bypassed that
    redaction for anyone who could reach this URL directly."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    outstanding_balance = order.balance or Decimal("0")
    already_completed = order.delivery_status == "Completed"
    blocked = (not already_completed) and outstanding_balance > 0
    return {
        "order_id": order.id,
        "order_code": order.order_code,
        "delivery_status": order.delivery_status,
        "outstanding_balance": float(outstanding_balance),
        "payment_status": order.payment_status if hasattr(order, "payment_status") else None,
        "ready_to_dispatch": not blocked,
        "reason": (
            f"Outstanding balance of {outstanding_balance} must be cleared, or an "
            f"authorized override with a reason recorded, before this order can be "
            f"marked delivered/dispatched."
        ) if blocked else None,
    }


APPROVED_SPEC_MAX_PHOTO_BYTES = 8 * 1024 * 1024


@orders_router.post("/{order_id}/client-link")
def generate_order_client_link(order_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family 137, feature 3 - Client 'My Order' Link.

    Defect repair (P1-13): disabled - Woodful is internal-only, and
    the public client-portal router this link would point to is no
    longer registered (see clients/portal_api.py). Returns 410 Gone
    rather than 404, since this specific endpoint still exists and is
    reachable by staff; it deliberately no longer mints a token or a
    URL that would only 404 for whoever received it."""
    raise HTTPException(
        status_code=410,
        detail="Client links are disabled - Woodful is an internal-only system.",
    )


@orders_router.get("/{order_id}/approved-specifications", response_model=List[ApprovedSpecificationResponse])
def list_approved_specifications(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Full version history for the order's Approved Specification /
    Sample Lock (Family 137, feature 8), most recent first - every past
    approval stays visible, never deleted, so a client's dispute about
    what was approved can always be answered from a real record."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    specs = (
        db.query(ApprovedSpecification)
        .filter(ApprovedSpecification.order_id == order_id)
        .order_by(ApprovedSpecification.version.desc())
        .all()
    )
    return specs


@orders_router.post("/{order_id}/approved-specifications", response_model=ApprovedSpecificationResponse, status_code=201)
def create_approved_specification(
    order_id: int, data: ApprovedSpecificationCreate, request: Request,
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Records a newly-approved specification/sample version. Never
    edits an existing row - the previous active version (if any) is
    flipped to "superseded" and this becomes version N+1, linked back
    via supersedes_id, so the full approval history is always
    reconstructable (Family 137, feature 8's required change flow:
    Original Approved -> Change Requested -> New Version/Sample ->
    Human/Client Approval -> New Approved Version)."""
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if data.sample_photo_path and len(data.sample_photo_path) > 2000:
        raise HTTPException(status_code=400, detail="sample_photo_path is too long to be a valid stored path.")

    current = (
        db.query(ApprovedSpecification)
        .filter(ApprovedSpecification.order_id == order_id, ApprovedSpecification.status == "approved")
        .order_by(ApprovedSpecification.version.desc())
        .first()
    )
    next_version = (current.version + 1) if current else 1
    if current:
        current.status = "superseded"

    new_spec = ApprovedSpecification(
        order_id=order_id, version=next_version,
        supersedes_id=current.id if current else None,
        material=data.material, finish=data.finish, veneer=data.veneer,
        laminate=data.laminate, colour=data.colour, hardware=data.hardware,
        batch_reference=data.batch_reference, sample_photo_path=data.sample_photo_path,
        notes=data.notes, status="approved",
        approved_by=data.approved_by, approved_at=data.approved_at or datetime.utcnow(),
        recorded_by_user_id=auth.get("user_id"),
    )
    db.add(new_spec)
    db.flush()
    log_action(
        db, request, user_id=auth.get("user_id"), action="approve_specification",
        module_name="orders", record_id=order.id,
        old_value={"previous_version": current.version if current else None},
        new_value={
            "approved_specification_id": new_spec.id, "version": new_spec.version,
            "material": new_spec.material, "finish": new_spec.finish, "colour": new_spec.colour,
            "batch_reference": new_spec.batch_reference, "approved_by": new_spec.approved_by,
        },
    )
    db.commit()
    db.refresh(new_spec)
    return new_spec


@orders_router.put("/{order_id}", response_model=OrderResponse)
def update_order(order_id: int, data: OrderUpdate, request: Request, db: Session = Depends(get_db),
                  auth=Depends(require_role("master"))):
    from decimal import Decimal

    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    update_fields = data.dict(exclude_unset=True, exclude={"items"})

    for field_name in ("project_status", "design_status", "execution_status", "delivery_status"):
        if field_name in update_fields:
            error = validate_order_status_value(field_name, update_fields[field_name])
            if error:
                raise HTTPException(status_code=400, detail=error)

    if "project_status" in update_fields:
        # Checked against order.project_status BEFORE the setattr loop
        # below overwrites it - a cancelled order must not be silently
        # reopened via this same generic field (see status_rules.py).
        error = validate_order_project_status_transition(order.project_status, update_fields["project_status"])
        if error:
            raise HTTPException(status_code=400, detail=error)

    # --- Family 137, feature 4: Balance-Before-Dispatch Guardrail ---
    # "Dispatched"/"Delivered" has no separate status value in this
    # codebase - delivery_status's real terminal value is "Completed"
    # (see ORDER_SUB_STATUSES) - so that is the one real transition this
    # guardrail checks. Checked against order.delivery_status BEFORE the
    # setattr loop overwrites it, and against order.balance, which is
    # already maintained transactionally elsewhere - never recomputed
    # here, only read.
    if (
        "delivery_status" in update_fields
        and update_fields["delivery_status"] == "Completed"
        and order.delivery_status != "Completed"
    ):
        outstanding_balance = order.balance or Decimal("0")
        if outstanding_balance > 0:
            if not data.override_balance_guardrail:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Order {order.order_code} has an outstanding balance of "
                        f"{outstanding_balance} and cannot be marked delivered/dispatched. "
                        f"Set override_balance_guardrail to true with an override_reason "
                        f"to dispatch anyway."
                    ),
                )
            if not data.override_reason or not data.override_reason.strip():
                raise HTTPException(
                    status_code=400,
                    detail="An override_reason is required to dispatch an order with an outstanding balance.",
                )
            # Authorized override - this endpoint already requires the
            # "master" role (see the route decorator), so no separate
            # permission check is needed here; the guardrail's job is to
            # force a deliberate, explained decision, not to add a new
            # authorization layer. Recorded on the shared audit_logs
            # table, never a bespoke one.
            log_action(
                db, request, user_id=auth.get("user_id"),
                action="dispatch_with_outstanding_balance_override",
                module_name="orders", record_id=order.id,
                old_value={"delivery_status": order.delivery_status, "balance": float(outstanding_balance)},
                new_value={"delivery_status": "Completed", "override_reason": data.override_reason.strip()},
            )

    # Captured before the setattr loop below overwrites them - needed
    # to safely recompute a bare order's subtotal (see the "else"
    # branch further down), and these are internally consistent with
    # each other (they were computed together as one grand total).
    old_order_value = order.order_value or Decimal("0")
    old_discount = order.discount or Decimal("0")
    old_tax_percent = order.tax_percent or Decimal("0")

    old_value = serializable_fields(order, update_fields.keys())
    for field, value in update_fields.items():
        setattr(order, field, value)

    if "delivery_date" in update_fields:
        # A changed Order due date propagates to every
        # task under it that inherited the date and was never
        # task-specifically overridden by a Master. An overridden task
        # deadline is left untouched.
        db.query(DailyTask).filter(
            DailyTask.order_id == order.id, DailyTask.due_date_overridden.is_(False),
        ).update({DailyTask.due_date: update_fields["delivery_date"]}, synchronize_session=False)

    recompute_needed = (
        data.items is not None or "discount" in update_fields
        or "tax_percent" in update_fields or "order_value" in update_fields
    )

    old_items_snapshot = None
    if data.items is not None:
        old_items_snapshot = [
            {
                "description": i.description, "category": i.category, "quantity": float(i.quantity),
                "unit": i.unit, "rate": float(i.rate), "amount": float(i.amount), "product_id": i.product_id,
            }
            for i in order.items
        ]
        for existing in list(order.items):
            db.delete(existing)
        db.flush()
        new_items = _build_order_items(db, data.items, order_id=order.id)
        for item in new_items:
            db.add(item)
        db.flush()
        subtotal_base = sum((i.amount for i in new_items), Decimal("0"))
    elif order.items:
        # Items weren't touched this call, but discount/tax_percent (or
        # a direct order_value) may have been - recompute from the
        # REAL current items total, not the old order_value (which is
        # already a grand total; reusing it as input would double-apply
        # the discount/tax on top of itself).
        subtotal_base = order.items_subtotal or Decimal("0")
    elif "order_value" in update_fields:
        # A bare lump-sum order with no line items, and the caller
        # explicitly supplied a new order_value - that IS the intended
        # new subtotal input to discount/tax, same as create_order.
        subtotal_base = order.order_value or Decimal("0")
    else:
        # A bare lump-sum order whose discount/tax_percent changed but
        # order_value itself was NOT explicitly supplied - the stored
        # order_value is already a grand total (subtotal - discount +
        # tax) from the last computation, not a fresh subtotal. Reusing
        # it directly here would double-apply the discount/tax that
        # already went into producing it. The real subtotal is
        # recovered from the OLD, internally-consistent (order_value,
        # discount, tax_percent) triple instead - exact except for the
        # 2-decimal-place rounding already baked into the old
        # tax_amount, which is an existing, bounded imprecision, not
        # the unbounded, compounding double-application this replaces.
        old_taxable = old_order_value / (Decimal("1") + old_tax_percent / Decimal("100"))
        subtotal_base = old_taxable + old_discount

    if recompute_needed:
        tax_amount, grand_total = compute_totals(subtotal_base, order.discount, order.tax_percent)
        order.tax_amount = tax_amount
        order.order_value = grand_total

    if (order.advance or Decimal("0")) > (order.order_value or Decimal("0")):
        raise HTTPException(
            status_code=400,
            detail=f"Advance (Rs {order.advance}) cannot exceed the order value (Rs {order.order_value}).",
        )

    # total_received (advance + every persisted payment - the exact
    # same formula Order.recompute_totals() uses, not a second,
    # competing calculation), not just advance - an order whose value
    # is reduced below what has already been genuinely received must
    # not silently create an unexplained negative outstanding balance.
    # Locked above, so this sees a consistent, current total_received
    # even against a concurrent payment being recorded at the same time.
    payments_total = sum((p.amount for p in order.payments), Decimal("0"))
    prospective_total_received = (order.advance or Decimal("0")) + payments_total
    if prospective_total_received > (order.order_value or Decimal("0")):
        raise HTTPException(
            status_code=400,
            detail=f"New order value (Rs {order.order_value}) is below the amount already received "
                   f"(Rs {prospective_total_received}). Reduce or refund the received amount first, "
                   f"or set a higher order value.",
        )

    order.recompute_totals()

    db.add(order)
    db.commit()
    db.refresh(order)
    new_value = serializable_fields(order, update_fields.keys())
    if data.items is not None:
        old_value["items"] = old_items_snapshot
        new_value["items"] = [
            {
                "description": i.description, "category": i.category, "quantity": float(i.quantity),
                "unit": i.unit, "rate": float(i.rate), "amount": float(i.amount), "product_id": i.product_id,
            }
            for i in order.items
        ]
    action = "cancel_order" if update_fields.get("project_status") == "Cancelled" else (
        "change_order_status" if "project_status" in update_fields else "update_order"
    )
    log_action(db, request, user_id=auth.get("user_id"), action=action, module_name="orders",
               record_id=order.id, old_value=old_value, new_value=new_value)
    return order


@orders_router.get("/{order_id}/email-preview", response_model=ClientEmailPreview)
def preview_order_email(order_id: int, kind: str = Query("order", pattern="^(order|invoice)$"),
                         db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    client = order.client
    if kind == "invoice":
        subject = f"Invoice for Order {order.order_code} - Woodful Creations"
        body = (
            f"Dear {client.name},\n\n"
            f"Please find attached the invoice for your order {order.order_code}.\n\n"
            f"Please let us know if you have any questions.\n\n"
            f"Regards,\nWoodful Creations"
        )
        attachment_filename = f"Invoice-{order.order_code}.pdf"
    else:
        subject = f"Order {order.order_code} - Woodful Creations"
        body = (
            f"Dear {client.name},\n\n"
            f"Please find attached the details for your order {order.order_code}.\n\n"
            f"Please let us know if you have any questions.\n\n"
            f"Regards,\nWoodful Creations"
        )
        attachment_filename = f"Order-{order.order_code}.pdf"
    # Defect repair (P1-13): this preview used to note that the actual
    # sent email would have a client-portal tracking link appended -
    # send_order_email no longer does that (Woodful is internal-only),
    # so the body shown here now matches exactly what gets sent.
    return ClientEmailPreview(
        recipient_email=client.email, client_has_email=bool(client.email),
        subject=subject, body=body, attachment_filename=attachment_filename,
    )


@orders_router.post("/{order_id}/send-email", response_model=ClientEmailSendResult)
def send_order_email(order_id: int, data: ClientEmailSendRequest, request: Request,
                      kind: str = Query("order", pattern="^(order|invoice)$"),
                      db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not data.recipient_email or "@" not in data.recipient_email:
        raise HTTPException(status_code=400, detail="A valid recipient email is required")

    # Defect repair (P1-13): Family 137 feature 3's persistent
    # order-tracking link used to be appended to every order-related
    # email here. Woodful is internal-only now and the public
    # client-portal route that link pointed to is no longer served
    # (see clients/portal_api.py), so nothing is generated or
    # appended anymore - the email still sends normally with whatever
    # body/attachment staff prepared, just without a link that would
    # only 404 for the client who received it.

    if kind == "invoice":
        payments = db.query(Payment).filter(Payment.order_id == order.id).order_by(Payment.date).all()
        pdf_buffer = generate_invoice_pdf(order, payments)
        attachment_filename = f"Invoice-{order.order_code}.pdf"
        action_name = "send_order_invoice_email"
    else:
        pdf_buffer = generate_order_estimate_pdf(order)
        attachment_filename = f"Order-{order.order_code}.pdf"
        action_name = "send_order_email"

    email_service = EmailService()
    sent = email_service.send_email(
        to_email=data.recipient_email, subject=data.subject, body=data.body, is_html=False,
        attachment_bytes=pdf_buffer.read(), attachment_filename=attachment_filename,
    )

    db.add(ClientActivity(
        client_id=order.client_id, activity_type="Email",
        summary=f"Emailed {kind} for {order.order_code} to {data.recipient_email} - subject: {data.subject}"
                + ("" if sent else " (SEND FAILED - see server logs)"),
        logged_by=auth.get("email") or "system",
    ))
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action=action_name,
               module_name="orders", record_id=order.id,
               new_value={"recipient": data.recipient_email, "sent": sent, "kind": kind,
                          "sender": email_service.sender_email, "attachment_filename": attachment_filename})

    if not sent:
        reason_text = {
            "missing_configuration": "Email sending is not configured on this server (SENDER_EMAIL/SENDER_PASSWORD/SMTP settings).",
            "authentication_failed": "The email account's login was rejected by the mail server - check the sender email and app password.",
            "connection_failed": "Could not reach the mail server - check SMTP_SERVER/SMTP_PORT and network/firewall settings.",
            "smtp_error": "The mail server rejected this message.",
            "unknown_error": "An unexpected error occurred while sending.",
        }.get(email_service.last_error, "email service unavailable or misconfigured")
        raise HTTPException(
            status_code=502,
            detail=f"The {kind} could not be emailed right now ({reason_text}). "
                   f"The order itself is unaffected - this only failed to send.",
        )
    return ClientEmailSendResult(sent=True, message=f"{'Invoice' if kind == 'invoice' else 'Order'} emailed to {data.recipient_email}.")


@orders_router.get("/{order_id}/health")
def get_order_health(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Deterministic, explainable Order Health/Risk (Family 130 P0.1) -
    the authoritative contract this order's frontend Command Centre,
    the chatbot's "what is blocking this order" workspace, and any
    future AI/agent should all read from, rather than each re-deriving
    risk from raw tables. See OrderService.compute_order_health's own
    docstring for exactly what is and isn't computed.

    Open to any role, matching material-requirements/ai-reports above -
    financial figures are the only thing gated, added here only for
    master rather than baked into the shared computation."""
    findings = OrderService.compute_order_health(db, order_id)
    if findings is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if auth.get("role", "user") in ("master",):
        order = db.query(Order).filter(Order.id == order_id).first()
        findings["pending_payment"] = float(order.balance or 0)
    return findings


@orders_router.get("/{order_id}/what-if")
def get_order_what_if(order_id: int, new_delivery_date: datetime = Query(
                           ..., description="ISO 8601 datetime - the hypothetical delivery date to simulate"),
                       db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """What-If Scheduling (P0.50 section 11) - "what happens if this
    order's delivery date changes to X". Reuses
    OrderService.compute_order_health exactly via its
    override_delivery_date parameter - never a second, simplified risk
    calculation. A simulation only: nothing is written to the
    database, the order's real, committed delivery_date is never
    touched. Returns the simulated result alongside the current real
    result so the caller can see the actual impact, not just the
    hypothetical state in isolation."""
    current = OrderService.compute_order_health(db, order_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Order not found")
    simulated = OrderService.compute_order_health(db, order_id, override_delivery_date=new_delivery_date)
    return {
        "order_id": order_id,
        "current": {"risk_level": current["risk_level"], "delivery_timing": current["delivery_timing"]},
        "simulated": {"risk_level": simulated["risk_level"], "delivery_timing": simulated["delivery_timing"],
                      "reasons": simulated["reasons"], "business_impact": simulated["business_impact"]},
        "risk_level_changed": current["risk_level"] != simulated["risk_level"],
    }


@orders_router.get("/{order_id}/build-timeline")
def get_order_build_timeline(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Family 137 feature 2 - Visual Build Timeline. A read-only view
    over this order's real Milestone and ProductionJob data - see
    OrderService.build_timeline's own docstring for exactly how each
    milestone's status (planned/current/completed/delayed/at_risk) is
    derived. Open to any role, matching /health above - nothing
    financial is exposed here."""
    timeline = OrderService.build_timeline(db, order_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return timeline


@orders_router.get("/{order_id}/delivery-promise")
def get_order_delivery_promise(order_id: int,
                                requested_date: datetime = Query(
                                    ..., description="ISO 8601 datetime - the delivery date being considered"),
                                db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Family 137 feature 12 - Capacity-Aware Delivery Promise
    (evaluation half). Read-only - see OrderService.
    evaluate_delivery_promise's own docstring for the real signals
    used. This is a PREDICTION plus a RECOMMENDATION, never a promise:
    nothing is written until POST .../delivery-promise below is
    explicitly called by a human."""
    evaluation = OrderService.evaluate_delivery_promise(db, order_id, requested_date)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return evaluation


@orders_router.post("/{order_id}/delivery-promise")
def record_order_delivery_promise(order_id: int, data: DeliveryPromiseRecord, request: Request,
                                   db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family 137 feature 12 - Capacity-Aware Delivery Promise
    (decision half). The system only ever recommends (see the GET
    evaluation above) - this is the one place a human's final promised
    date is actually recorded, on the existing Order.delivery_date
    column (never a second "promised date" field), with its own
    distinct audit action so it is never confused with a routine order
    edit. Master-only: promising a delivery date to a client is a
    consequential, client-facing commitment (section 9/11)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    old_date = order.delivery_date.isoformat() if order.delivery_date else None
    order.delivery_date = data.promised_date
    db.add(order)
    log_action(
        db, request, user_id=auth.get("user_id"), action="delivery_date_promised", module_name="orders",
        record_id=order.id,
        old_value={"delivery_date": old_date},
        new_value={"delivery_date": data.promised_date.isoformat(), "reason": data.reason},
    )
    db.commit()
    db.refresh(order)
    return {
        "order_id": order.id, "order_code": order.order_code,
        "promised_date": order.delivery_date.isoformat(), "reason": data.reason,
        "promised_by": auth.get("email"),
    }


@orders_router.get("/{order_id}/profitability")
def get_order_profitability(order_id: int, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderService.profitability(db, order)


@orders_router.get("/{order_id}/material-requirements")
def get_order_material_requirements(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Material Requirement + Shortage Intelligence: what this order's
    products actually need (via each Product's BOM), against real
    current stock and purchases already placed but not yet received.
    Every figure traces to a real row - see
    StockService.calculate_order_material_requirements's own docstring."""
    return StockService.calculate_order_material_requirements(db, order_id)


@orders_router.get("/{order_id}/ai-reports")
def list_order_ai_reports(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Persisted AI workspace reports for this order (real
    artifacts must be viewable). Open to any role, matching "everyone
    can view tasks/order status" - but findings are re-redacted here
    against the CURRENT viewer's role, not trusted from whatever role
    created the report. A master's report viewed later by an employee
    must not leak the payment figure it was created with."""
    if not db.query(Order).filter(Order.id == order_id).first():
        raise HTTPException(status_code=404, detail="Order not found")
    is_privileged = auth.get("role", "user") in ("master",)
    reports = db.query(AIWorkspaceReport).filter(AIWorkspaceReport.order_id == order_id).order_by(
        AIWorkspaceReport.created_at.desc()
    ).all()
    result = []
    for r in reports:
        findings = json.loads(r.findings)
        if not is_privileged:
            findings.pop("pending_payment", None)
        result.append({
            "id": r.id, "query_text": r.query_text, "risk_level": r.risk_level,
            "findings": findings, "created_at": r.created_at,
        })
    return result


@orders_router.get("/{order_id}/comments", response_model=List[OrderCommentResponse])
def list_order_comments(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(Order).filter(Order.id == order_id).first():
        raise HTTPException(status_code=404, detail="Order not found")
    return db.query(OrderComment).filter(OrderComment.order_id == order_id).order_by(OrderComment.date.asc()).all()


@orders_router.post("/{order_id}/comments", response_model=OrderCommentResponse, status_code=201)
def add_order_comment(order_id: int, data: OrderCommentCreate, db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    comment = OrderComment(order_id=order_id, author=auth.get("email") or "Unknown", text=data.text,
                            date=datetime.utcnow())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    notify_mentions(
        db, text=data.text, comment_id=comment.id, source_type="order_comment",
        entity_type="order", entity_id=order_id,
        title=f"Mentioned in project {order.order_code}", action_path=f"/orders/{order_id}",
        excluded_user_id=auth.get("user_id"),
    )
    return comment


@orders_router.get("/{order_id}/activity")
def get_order_activity(order_id: int, limit: int = Query(100, ge=1, le=500),
                        db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """A single chronological feed of everything tied to this project -
    project comments, comments on its tasks, milestones reached, and
    notifications about it (task overdue, project delayed, ...) - so
    "what's been happening on this order" doesn't mean checking four
    separate screens. Financial notifications (e.g. a payment-overdue
    alert for this order) are filtered through the exact same
    NotificationService.visible_to used everywhere else notifications
    are shown - an employee opening this timeline sees the same set of
    notifications they'd see in their own notification panel, never
    more."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    role = auth.get("role", "user")
    entries = []

    for c in db.query(OrderComment).filter(OrderComment.order_id == order_id).all():
        entries.append({"type": "order_comment", "date": c.date, "author": c.author, "text": c.text,
                         "path": f"/orders/{order_id}"})

    task_ids = [t.id for t in db.query(DailyTask.id).filter(DailyTask.order_id == order_id).all()]
    if task_ids:
        for tc in db.query(TaskComment).filter(TaskComment.task_id.in_(task_ids)).all():
            entries.append({"type": "task_comment", "date": tc.date, "author": tc.author, "text": tc.text,
                             "path": f"/daily-tasks/{tc.task_id}"})

    for ms in db.query(Milestone).filter(Milestone.order_id == order_id).all():
        if ms.completed_date:
            entries.append({"type": "milestone_completed", "date": ms.completed_date, "author": None,
                             "text": f"Milestone completed: {ms.name}", "path": f"/orders/{order_id}"})

    notif_query = NotificationService.visible_to(
        db.query(Notification).filter(Notification.related_entity_type == "order",
                                       Notification.related_entity_id == order_id),
        auth.get("user_id"), role,
    )
    for n in notif_query.all():
        entries.append({"type": "notification", "date": n.created_at, "author": None,
                         "text": f"{n.title}: {n.message}", "path": n.action_path or f"/orders/{order_id}"})

    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries[:limit]


# --- order_imports.py ---
order_imports_router = APIRouter(prefix="/api/order-imports", tags=["order-imports"])


@order_imports_router.get("/template")
def download_order_import_template(auth=Depends(require_role("master"))):
    buffer = build_order_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Order_Import_Template.xlsx"},
    )


def _read_order_upload(file: UploadFile) -> bytes:
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    allowed_mime_types = {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
            )
    return bytes(file_bytes)


@order_imports_router.post("/preview", response_model=OrderImportPreviewResponse)
def preview_order_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    try:
        file_bytes = _read_order_upload(file)
        raw_headers, raw_items = parse_order_uploaded_workbook(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Couldn't read this file - please upload a valid .xlsx file using the downloaded template.",
        )

    orders_by_code = {normalize_match_key(o.order_code): o for o in db.query(Order).all()}
    for o in db.query(Order).filter(Order.business_id.isnot(None)).all():
        orders_by_code.setdefault(normalize_match_key(o.business_id), o)

    clients_by_key = {}
    for c in db.query(Client).all():
        clients_by_key[(normalize_match_key(c.name), normalize_phone_key(c.phone))] = c

    estimates_by_code = {normalize_match_key(e.estimate_code): e for e in db.query(Estimate).all()}
    for e in db.query(Estimate).filter(Estimate.business_id.isnot(None)).all():
        estimates_by_code.setdefault(normalize_match_key(e.business_id), e)

    products_by_code = {}
    for p in db.query(Product).all():
        products_by_code[normalize_match_key(p.product_code)] = p
        if p.business_id:
            products_by_code.setdefault(normalize_match_key(p.business_id), p)

    header_previews = []
    ref_to_header_idx = {}
    seen_estimate_ids_in_file = {}
    seen_order_ids_in_file = {}
    for idx, row in enumerate(raw_headers, start=1):
        result, errors = validate_order_header_row(row, idx, orders_by_code, clients_by_key, estimates_by_code)
        # Two "existing order" rows both updating the same order would
        # otherwise commit silently, one overwriting the other with no
        # warning - same reasoning as the estimate-conversion check
        # below, just for a direct update instead of a one-time
        # estimate-to-order conversion.
        matched_order_id = result.get("matched_order_id")
        if not errors and matched_order_id is not None:
            if matched_order_id in seen_order_ids_in_file:
                errors = errors + [
                    f"Order {result.get('matched_order_code')} is also being updated by row "
                    f"{seen_order_ids_in_file[matched_order_id]} in this same file - only one of these "
                    f"will end up taking effect."
                ]
            else:
                seen_order_ids_in_file[matched_order_id] = idx
        # Two "new order" rows both converting the same estimate can't
        # be caught by validate_header_row alone - it only checks
        # against the pre-upload database snapshot, so both rows
        # independently see the estimate as still available. Flagged
        # here instead, against every earlier header row in this same
        # file.
        matched_estimate_id = result.get("matched_estimate_id")
        if not errors and matched_estimate_id is not None:
            if matched_estimate_id in seen_estimate_ids_in_file:
                errors = errors + [
                    f"Estimate {result.get('matched_estimate_code')} is also being converted by row "
                    f"{seen_estimate_ids_in_file[matched_estimate_id]} in this same file - an estimate "
                    f"can only become one order."
                ]
            else:
                seen_estimate_ids_in_file[matched_estimate_id] = idx
        header_previews.append(OrderImportHeaderPreview(**result, errors=errors, items=[]))
        ref_to_header_idx[idx] = len(header_previews) - 1

    orphan_items = []
    for idx, row in enumerate(raw_items, start=1):
        result, errors = validate_order_item_row(row, idx, products_by_code)
        preview_item = OrderImportItemPreview(**result, errors=errors)
        ref = result.get("order_ref")
        if ref is not None and ref in ref_to_header_idx:
            header_previews[ref_to_header_idx[ref]].items.append(preview_item)
        else:
            if ref is not None:
                preview_item.errors.append(f'Order Row # {ref} does not match any row on the Order Header sheet.')
            orphan_items.append(preview_item)

    valid_count = error_count = new_count = existing_count = 0
    for h in header_previews:
        converting = bool(h.matched_estimate_id)
        item_errors = any(it.errors for it in h.items)
        has_items = len(h.items) > 0
        if not converting and not has_items and not h.errors:
            h.errors.append(
                "This order has no valid item rows on the Order Items sheet, and no Estimate ID to convert from."
            )
        if h.errors or (item_errors and not converting):
            error_count += 1
        else:
            valid_count += 1
            if not converting:
                subtotal = sum((it.amount for it in h.items if it.amount is not None), Decimal("0"))
                tax_amount, total = compute_totals(subtotal, h.discount or Decimal("0"), h.tax_percent or Decimal("18"))
                h.computed_subtotal = subtotal
                h.computed_tax_amount = tax_amount
                h.computed_total = total
            if h.is_new_order:
                new_count += 1
            else:
                existing_count += 1

    return OrderImportPreviewResponse(
        total_orders=len(header_previews), valid_orders=valid_count, error_orders=error_count,
        new_orders=new_count, existing_orders=existing_count,
        orphan_item_rows=orphan_items, orders=header_previews,
    )


@order_imports_router.post("/error-report")
def download_order_import_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the header+item
    grouping logic /preview uses) and returns a real .xlsx listing
    every rejected header row and every rejected item row, each
    labeled with its source sheet - matching the established pattern
    from client_imports.py, adapted for this import's
    two-sheet structure."""
    file_bytes = _read_order_upload(file)
    try:
        raw_headers, raw_items = parse_order_uploaded_workbook(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Couldn't read this file - please upload a valid .xlsx file.")

    orders_by_code = {normalize_match_key(o.order_code): o for o in db.query(Order).all()}
    for o in db.query(Order).filter(Order.business_id.isnot(None)).all():
        orders_by_code.setdefault(normalize_match_key(o.business_id), o)
    clients_by_key = {}
    for c in db.query(Client).all():
        clients_by_key[(normalize_match_key(c.name), normalize_phone_key(c.phone))] = c
    estimates_by_code = {normalize_match_key(e.estimate_code): e for e in db.query(Estimate).all()}
    for e in db.query(Estimate).filter(Estimate.business_id.isnot(None)).all():
        estimates_by_code.setdefault(normalize_match_key(e.business_id), e)
    products_by_code = {}
    for p in db.query(Product).all():
        products_by_code[normalize_match_key(p.product_code)] = p
        if p.business_id:
            products_by_code.setdefault(normalize_match_key(p.business_id), p)

    error_rows = []
    for idx, row in enumerate(raw_headers, start=1):
        result, errors = validate_order_header_row(row, idx, orders_by_code, clients_by_key, estimates_by_code)
        if errors:
            error_rows.append({
                "sheet": "Order Header", "row": idx, "reference": result.get("client_name") or "",
                "reason": "; ".join(errors),
            })
    for idx, row in enumerate(raw_items, start=1):
        result, errors = validate_order_item_row(row, idx, products_by_code)
        if errors:
            error_rows.append({
                "sheet": "Order Items", "row": idx, "reference": result.get("description") or "",
                "reason": "; ".join(errors),
            })

    from app.shared import build_workbook
    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Order Import Error Report",
        "subtitle": f"{len(error_rows)} rejected row(s) across both sheets. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["sheet", "row", "reference", "reason"],
        "headers": ["Sheet", "Row", "Reference", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Order_Import_Errors.xlsx"},
    )


@order_imports_router.post("/commit", response_model=OrderImportCommitResult)
def commit_order_import(data: OrderImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Creates/updates one Order per confirmed row - each commits as its
    own all-or-nothing transaction, same discipline as
    estimate_imports.commit_order_import. An order with from_estimate_id set
    converts that estimate using the exact same compare-and-swap claim
    POST /api/orders/ uses, so a race against a UI-driven conversion of
    the same estimate can't double-convert it."""
    results = []
    created_count = updated_count = skipped_count = error_count = 0

    for row in data.orders:
        if row.skip:
            skipped_count += 1
            results.append(OrderImportCommitResultRow(skipped=True))
            continue

        try:
            client = db.query(Client).filter(Client.id == row.client_id).first()
            if not client:
                raise ValueError("Invalid Client ID")

            source_estimate = None
            if row.from_estimate_id:
                source_estimate = db.query(Estimate).filter(Estimate.id == row.from_estimate_id).first()
                if not source_estimate:
                    raise ValueError("Source estimate not found")
                if source_estimate.status != "approved":
                    raise ValueError(
                        f"Only an approved estimate can be converted into an order "
                        f"(this estimate is '{source_estimate.status}')."
                    )
                if source_estimate.order_id:
                    raise ValueError("This estimate has already been converted to an order.")
                if source_estimate.client_id != client.id:
                    raise ValueError(
                        "The source estimate belongs to a different client than this imported order row."
                    )

            if source_estimate and source_estimate.line_items:
                order_items = [
                    OrderItem(
                        description=li.description, category=li.category, quantity=li.quantity,
                        unit=li.unit, rate=li.rate, amount=li.amount,
                        source_estimate_item_id=li.id, sort_order=i, product_id=li.product_id,
                        is_custom_item=li.is_custom_item, pricing_rule_applied=li.pricing_rule_applied,
                        applied_margin_percent=li.applied_margin_percent,
                    )
                    for i, li in enumerate(source_estimate.line_items)
                ]
                discount = source_estimate.discount
                tax_percent = source_estimate.tax_percent
            else:
                product_ids = {item.product_id for item in row.items}
                found_products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}
                missing = product_ids - set(found_products.keys())
                if missing:
                    raise ValueError(f"Invalid Product ID(s): {sorted(missing)}")
                inactive = [p.name for p in found_products.values() if not p.is_active]
                if inactive:
                    raise ValueError(f"Cannot use inactive product(s): {', '.join(inactive)}")
                order_items = []
                for i, item in enumerate(row.items):
                    amount = item.quantity * item.rate
                    if item.discount_percent:
                        amount = amount - (amount * item.discount_percent / Decimal("100"))
                    amount = amount.quantize(Decimal("0.01"))
                    order_items.append(OrderItem(
                        description=item.description, category=item.category, quantity=item.quantity,
                        unit=item.unit, rate=item.rate, amount=amount, product_id=item.product_id, sort_order=i,
                    ))
                discount = row.discount
                tax_percent = row.tax_percent

            if order_items:
                items_subtotal = sum((i.amount for i in order_items), Decimal("0"))
                tax_amount, grand_total = compute_totals(items_subtotal, discount, tax_percent)
            else:
                tax_amount, grand_total = compute_totals(Decimal("0"), discount, tax_percent)

            if row.matched_order_id:
                order = db.query(Order).filter(Order.id == row.matched_order_id).with_for_update().first()
                if not order:
                    raise ValueError("Order no longer exists")
                if order.project_status in ORDER_LOCKED_STATUSES:
                    raise ValueError(
                        f'Order {order.order_code} is "{order.project_status}" and can no longer be edited by re-import.'
                    )
                if grand_total < (order.total_received or Decimal("0")):
                    raise ValueError(
                        f"New order value (Rs {grand_total}) is below the amount already received "
                        f"(Rs {order.total_received}) - this row was not imported."
                    )
                old_value = {"order_value": float(order.order_value or 0), "item_count": len(order.items)}
                order.client_id = client.id
                if row.delivery_date:
                    order.delivery_date = row.delivery_date
                order.discount = discount
                order.tax_percent = tax_percent
                order.tax_amount = tax_amount
                order.order_value = grand_total
                order.balance = grand_total - (order.total_received or Decimal("0"))
                if row.notes is not None:
                    order.remarks = row.notes
                for existing_item in list(order.items):
                    db.delete(existing_item)
                db.flush()
                for oi in order_items:
                    oi.order_id = order.id
                    db.add(oi)
                db.commit()
                db.refresh(order)
                log_action(db, request, user_id=auth.get("user_id"), action="import_update_order",
                           module_name="orders", record_id=order.id,
                           old_value=old_value, new_value={"order_value": float(order.order_value or 0)})
                updated_count += 1
                results.append(OrderImportCommitResultRow(order_id=order.id, order_code=order.order_code, updated=True))
            else:
                year = (row.order_date or datetime.utcnow()).year
                created_id = None
                for _ in range(5):
                    code = generate_unique_code(db, Order, "order_code", f"WC-{year}-")
                    order_kwargs = dict(
                        order_code=code, business_id=generate_business_id(db), client_id=client.id,
                        delivery_date=row.delivery_date, discount=discount, tax_percent=tax_percent,
                        tax_amount=tax_amount, order_value=grand_total, advance=Decimal("0"),
                        total_received=Decimal("0"), balance=grand_total, remarks=row.notes,
                    )
                    if row.order_date:
                        order_kwargs["order_date"] = row.order_date
                    order = Order(**order_kwargs)
                    db.add(order)
                    try:
                        db.flush()
                        created_id = order.id
                        break
                    except IntegrityError:
                        db.rollback()
                        continue
                if created_id is None:
                    raise ValueError("Could not generate a unique order code")
                for oi in order_items:
                    oi.order_id = created_id
                    db.add(oi)
                if source_estimate:
                    # Same atomic compare-and-swap as the UI conversion
                    # path (see api/routes/orders.py create_order) - the
                    # estimate is only claimed if still unconverted, and
                    # this whole order (with its just-added items) rolls
                    # back if it loses the race.
                    claim_result = db.execute(
                        sa_update(Estimate.__table__)
                        .where(Estimate.id == source_estimate.id, Estimate.order_id.is_(None))
                        .values(order_id=created_id, status="closed")
                    )
                    if claim_result.rowcount != 1:
                        db.rollback()
                        raise ValueError("This estimate has already been converted to an order.")
                db.commit()
                db.refresh(order)
                log_action(db, request, user_id=auth.get("user_id"), action="import_create_order",
                           module_name="orders", record_id=order.id,
                           new_value={"client_id": client.id, "order_code": order.order_code,
                                      "order_value": float(order.order_value or 0),
                                      "source_estimate_id": source_estimate.id if source_estimate else None})
                created_count += 1
                results.append(OrderImportCommitResultRow(order_id=order.id, order_code=order.order_code, created=True))

        except (ValueError, HTTPException) as e:
            db.rollback()
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_count += 1
            results.append(OrderImportCommitResultRow(error=detail))

    return OrderImportCommitResult(
        created_count=created_count, updated_count=updated_count,
        skipped_count=skipped_count, error_count=error_count, results=results,
    )


# --- estimates.py ---
estimates_router = APIRouter(prefix="/api/estimates", tags=["estimates"])


def _build_line_items(db, line_items_data, estimate_id: int = None):
    """Computes amount = quantity * rate server-side for each line item -
    the frontend may show a running total for UX, but the stored amount
    is never taken from client input directly.

    Also validates every supplied product_id actually references a
    real, active Product Master row - product_id is now mandatory
    (Pydantic already rejects a missing one with "Product ID is
    required" before this function ever runs) - same fix as the
    equivalent Order builder, kept consistent since an order's items
    are frequently copied straight from an estimate's."""
    from app.modules.catalog.models import Product

    product_ids = {item.product_id for item in line_items_data if item.product_id is not None}
    if product_ids:
        found_products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
        missing = product_ids - set(found_products.keys())
        if missing:
            raise HTTPException(status_code=400, detail="Invalid Product ID")
        inactive = [p.name for p in found_products.values() if not p.is_active]
        if inactive:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use inactive product(s) on a new estimate: {', '.join(inactive)}",
            )

    items = []
    for idx, item in enumerate(line_items_data):
        amount = (item.quantity * item.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Family 137, feature 9 (Cost-Drift Alert): snapshot the cost
        # basis actually in effect right now, at the moment this line is
        # priced - the same cost_price/suggested_cost_price a later
        # cost-drift check compares against. None for a custom item with
        # no product_id, or a product with no cost recorded yet - left
        # NULL (unknown), never defaulted to 0, so it is correctly
        # excluded from drift math rather than reported as "cost fell to
        # zero".
        cost_at_creation = None
        if item.product_id is not None:
            product = found_products.get(item.product_id)
            if product is not None:
                cost_basis = product.cost_price if product.cost_price is not None else product.suggested_cost_price
                if cost_basis is not None:
                    cost_at_creation = Decimal(str(cost_basis))
        items.append(EstimateLineItem(
            estimate_id=estimate_id, description=item.description, category=item.category,
            quantity=item.quantity, unit=item.unit, rate=item.rate, amount=amount, sort_order=idx,
            product_id=item.product_id, is_custom_item=item.is_custom_item,
            cost_at_creation=cost_at_creation,
        ))
    return items


def _serialize_estimates(estimates, role: str):
    """An estimate is inherently a pricing document - material_cost,
    labor_cost, discount, subtotal, tax_amount, total_cost, and each
    line item's rate/amount are genuinely nulled for non-master
    roles. status/version (workflow state, not money) stay visible."""
    responses = [EstimateResponse.model_validate(e) for e in estimates]
    if role not in ("master",):
        for r in responses:
            r.material_cost = None
            r.labor_cost = None
            r.discount = None
            r.subtotal = None
            r.tax_amount = None
            r.total_cost = None
            for item in r.line_items:
                item.rate = None
                item.amount = None
    return responses


def _serialize_estimate(estimate, role: str):
    return _serialize_estimates([estimate], role)[0]


@estimates_router.get("/", response_model=List[EstimateResponse])
def list_estimates(client_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                    limit: int = Query(500, ge=1, le=500), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Estimate)
    if client_id:
        query = query.filter(Estimate.client_id == client_id)
    if status:
        query = query.filter(Estimate.status == status)
    rows = query.order_by(Estimate.created_at.desc()).offset(offset).limit(limit).all()
    return _serialize_estimates(rows, auth.get("role", "user"))


@estimates_router.post("/", response_model=EstimateResponse, status_code=201)
def create_estimate(data: EstimateCreate, request: Request, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"estimate_code", "line_items"})

    if data.order_id is not None:
        linked_order = db.query(Order).filter(Order.id == data.order_id).first()
        if not linked_order:
            raise HTTPException(status_code=404, detail="The related order was not found.")
        if linked_order.client_id != data.client_id:
            raise HTTPException(
                status_code=400,
                detail="The related order belongs to a different client than this estimate.",
            )

    if data.line_items:
        line_items = _build_line_items(db, data.line_items)
        subtotal = sum((item.amount for item in line_items), Decimal("0"))
        # material_cost/labor_cost are legacy summary fields - when real
        # line items are supplied, keep them in sync by category rather
        # than let them silently go stale for any report still reading
        # them directly.
        payload["material_cost"] = sum(
            (i.amount for i in line_items if i.category == "Material"), Decimal("0"))
        payload["labor_cost"] = sum(
            (i.amount for i in line_items if i.category == "Labor"), Decimal("0"))
    else:
        line_items = []
        subtotal = data.material_cost + data.labor_cost

    tax_amount, total_cost = _compute_totals(subtotal, data.discount, data.tax_percent)

    for _ in range(5):
        code = generate_unique_code(db, Estimate, "estimate_code", "EST-")
        estimate = Estimate(**payload, estimate_code=code, business_id=generate_business_id(db),
                             tax_amount=tax_amount, total_cost=total_cost)
        db.add(estimate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        for item in line_items:
            item.estimate_id = estimate.id
            db.add(item)
        db.commit()
        db.refresh(estimate)
        log_action(db, request, user_id=auth.get("user_id"), action="create_estimate", module_name="estimates",
                   record_id=estimate.id, new_value={
                       "client_id": estimate.client_id, "estimate_code": estimate.estimate_code,
                       "total_cost": float(estimate.total_cost or 0),
                   })
        return estimate
    raise HTTPException(status_code=500, detail="Unable to generate a unique estimate code, please try again")


@estimates_router.get("/{estimate_id}", response_model=EstimateResponse)
def get_estimate(estimate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return _serialize_estimate(estimate, auth.get("role", "user"))


@estimates_router.get("/{estimate_id}/cost-drift", response_model=CostDriftResponse)
def get_estimate_cost_drift(estimate_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family 137, feature 9 - Cost-Drift Alert.

    Compares each line item's cost_at_creation (the cost basis snapshot
    taken when the line was priced - see _build_line_items) against the
    product's CURRENT cost_price/suggested_cost_price, holding the
    quoted selling rate fixed. This is read-only and changes nothing -
    it is the INSIGHT step; a human decides what to do with it (revise
    price, review substitutions, accept the margin impact) through the
    normal estimate-update endpoint, never automatically here.

    A line item is skipped, not reported as zero drift, when it has no
    product_id (a genuine custom/one-off line) or no recorded
    cost_at_creation (created before this column existed, or the
    product had no cost on file at that time) - the drift for those is
    genuinely unknown, not zero."""
    from app.modules.catalog.models import Product

    estimate = (
        db.query(Estimate)
        .options(selectinload(Estimate.line_items))
        .filter(Estimate.id == estimate_id)
        .first()
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    checkable_items = [i for i in estimate.line_items if i.product_id is not None and i.cost_at_creation is not None]
    skipped_count = len(estimate.line_items) - len(checkable_items)

    product_ids = {i.product_id for i in checkable_items}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}

    drift_items: List[CostDriftLineItem] = []
    original_total = Decimal("0")
    current_total = Decimal("0")
    rate_weighted_total = Decimal("0")

    for item in checkable_items:
        product = products.get(item.product_id)
        if product is None:
            skipped_count += 1
            continue
        current_cost_basis = product.cost_price if product.cost_price is not None else product.suggested_cost_price
        if current_cost_basis is None:
            skipped_count += 1
            continue
        current_cost = Decimal(str(current_cost_basis)) * item.quantity
        original_cost = item.cost_at_creation * item.quantity
        rate_total = item.rate * item.quantity

        original_margin = None
        current_margin = None
        if rate_total > 0:
            original_margin = ((rate_total - original_cost) / rate_total * Decimal("100")).quantize(Decimal("0.01"))
            current_margin = ((rate_total - current_cost) / rate_total * Decimal("100")).quantize(Decimal("0.01"))

        drift_items.append(CostDriftLineItem(
            line_item_id=item.id, description=item.description,
            original_cost=original_cost.quantize(Decimal("0.01")),
            current_cost=current_cost.quantize(Decimal("0.01")),
            cost_delta=(current_cost - original_cost).quantize(Decimal("0.01")),
            rate=item.rate, original_margin_percent=original_margin, current_margin_percent=current_margin,
        ))
        original_total += original_cost
        current_total += current_cost
        rate_weighted_total += rate_total

    # Only line items whose cost actually moved are "drifted" - an
    # unchanged cost is checked, but not a finding.
    drifted = [d for d in drift_items if d.cost_delta != 0]

    overall_original_margin = None
    overall_current_margin = None
    if rate_weighted_total > 0:
        overall_original_margin = ((rate_weighted_total - original_total) / rate_weighted_total * Decimal("100")).quantize(Decimal("0.01"))
        overall_current_margin = ((rate_weighted_total - current_total) / rate_weighted_total * Decimal("100")).quantize(Decimal("0.01"))

    quote_age_days = (datetime.utcnow() - estimate.created_at).days

    return CostDriftResponse(
        estimate_id=estimate.id, estimate_code=estimate.estimate_code, quote_age_days=quote_age_days,
        checked_line_items=len(drift_items), drifted_line_items=len(drifted), skipped_line_items=skipped_count,
        original_cost_total=original_total.quantize(Decimal("0.01")),
        current_cost_total=current_total.quantize(Decimal("0.01")),
        cost_delta_total=(current_total - original_total).quantize(Decimal("0.01")),
        original_margin_percent=overall_original_margin, current_margin_percent=overall_current_margin,
        items=drift_items,
    )


@estimates_router.post("/{estimate_id}/margin-optimization", response_model=MarginOptimizationResponse)
def get_margin_optimization(
    estimate_id: int, data: MarginOptimizationRequest,
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Family 137, feature 6 - Smart Estimate / Margin Optimization.

    When a client pushes back on price, finds like-for-like catalog
    substitutions (same product category/subcategory, a genuinely
    different and cheaper active product) instead of a blind discount.
    For every line item backed by a real product, looks for the
    single best cheaper alternative in the same category and reports
    what changes, the saving, and the resulting margin - exactly the
    OPTIONS step of DATA -> INSIGHT -> OPTIONS -> RECOMMENDATION ->
    HUMAN DECISION. This endpoint is read-only: it never modifies the
    estimate. The human reviews the suggestions and, if they want to
    apply one, edits the estimate's line items themselves through the
    normal update-estimate endpoint - the same audited path as any
    other estimate change."""
    from app.modules.catalog.models import Product
    from app.modules.catalog.pricing import compute_selling_rate, DEFAULT_MARGIN_PERCENT

    estimate = (
        db.query(Estimate)
        .options(selectinload(Estimate.line_items))
        .filter(Estimate.id == estimate_id)
        .first()
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    current_total = sum((item.amount or Decimal("0")) for item in estimate.line_items) or Decimal("0")

    def _product_rate(product) -> Optional[Decimal]:
        """A candidate's own asking rate - its stated selling_price if
        set, otherwise what its own cost implies at the catalog default
        margin. Never derived from the CURRENT line item's margin -
        that would make a substitute look artificially cheap or
        expensive depending on what this estimate happens to be
        charging, rather than what the substitute product actually
        costs to sell."""
        if product.selling_price is not None:
            return Decimal(str(product.selling_price))
        if product.cost_price is not None:
            return compute_selling_rate(Decimal(str(product.cost_price)), DEFAULT_MARGIN_PERCENT)
        return None

    suggestions: List[MarginOptimizationSuggestion] = []
    checkable_items = [i for i in estimate.line_items if i.product_id is not None]
    if checkable_items:
        current_products = {
            p.id: p for p in db.query(Product).filter(Product.id.in_([i.product_id for i in checkable_items])).all()
        }
        for item in checkable_items:
            current_product = current_products.get(item.product_id)
            if current_product is None:
                continue
            category_filter = current_product.subcategory or current_product.category
            if not category_filter:
                continue
            candidates = db.query(Product).filter(
                Product.id != current_product.id,
                Product.is_active.is_(True),
                (Product.subcategory == category_filter) | (Product.category == category_filter),
            ).all()

            best_candidate = None
            best_rate = None
            for candidate in candidates:
                candidate_rate = _product_rate(candidate)
                if candidate_rate is None or candidate_rate >= item.rate:
                    continue
                if best_rate is None or candidate_rate < best_rate:
                    best_candidate, best_rate = candidate, candidate_rate

            if best_candidate is None:
                continue

            saving_per_unit = (item.rate - best_rate).quantize(Decimal("0.01"))
            total_saving = (saving_per_unit * item.quantity).quantize(Decimal("0.01"))
            resulting_margin = None
            if best_candidate.cost_price is not None and best_rate > 0:
                resulting_margin = (
                    (best_rate - Decimal(str(best_candidate.cost_price))) / best_rate * Decimal("100")
                ).quantize(Decimal("0.01"))

            suggestions.append(MarginOptimizationSuggestion(
                line_item_id=item.id, current_description=item.description,
                current_product_id=current_product.id, current_rate=item.rate, quantity=item.quantity,
                suggested_product_id=best_candidate.id, suggested_product_name=best_candidate.name,
                suggested_rate=best_rate, saving_per_unit=saving_per_unit, total_saving=total_saving,
                resulting_margin_percent=resulting_margin,
                availability_note=(
                    "Active in catalog." if best_candidate.is_active else "Inactive - confirm availability before offering."
                ),
            ))

    # Ranked by total saving, largest first - the options most likely
    # to actually move the price toward the target come first.
    suggestions.sort(key=lambda s: s.total_saving, reverse=True)

    best_achievable_price = (current_total - sum(s.total_saving for s in suggestions)).quantize(Decimal("0.01"))
    target_reachable = None
    if data.target_price is not None:
        target_reachable = best_achievable_price <= data.target_price

    current_margin_percent = None
    original_cost_total = sum(
        (item.cost_at_creation * item.quantity) for item in estimate.line_items if item.cost_at_creation is not None
    )
    if current_total > 0 and original_cost_total:
        current_margin_percent = ((current_total - original_cost_total) / current_total * Decimal("100")).quantize(Decimal("0.01"))

    return MarginOptimizationResponse(
        estimate_id=estimate.id, estimate_code=estimate.estimate_code,
        current_total=current_total.quantize(Decimal("0.01")), current_margin_percent=current_margin_percent,
        target_price=data.target_price, min_margin_percent=data.min_margin_percent,
        best_achievable_price=best_achievable_price, target_reachable=target_reachable,
        suggestions=suggestions,
    )


@estimates_router.post("/{estimate_id}/client-link")
def generate_estimate_client_link(estimate_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Family 137, feature 1 - Client Approval Hub.

    Defect repair (P1-13): disabled - same reasoning and behavior as
    generate_order_client_link above."""
    raise HTTPException(
        status_code=410,
        detail="Client links are disabled - Woodful is an internal-only system.",
    )


@estimates_router.get("/{estimate_id}/email-preview", response_model=ClientEmailPreview)
def preview_estimate_email(estimate_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    client = estimate.client
    subject = f"Estimate {estimate.estimate_code} - Woodful Creations"
    valid_until_note = f" (valid until {estimate.valid_until.strftime('%d %b %Y')})" if estimate.valid_until else ""
    body = (
        f"Dear {client.name},\n\n"
        f"Please find attached your estimate {estimate.estimate_code}{valid_until_note}.\n\n"
        f"Please let us know if you have any questions.\n\n"
        f"Regards,\nWoodful Creations"
    )
    return ClientEmailPreview(
        recipient_email=client.email, client_has_email=bool(client.email),
        subject=subject, body=body, attachment_filename=f"Estimate-{estimate.estimate_code}.pdf",
    )


@estimates_router.post("/{estimate_id}/send-email", response_model=ClientEmailSendResult)
def send_estimate_email(estimate_id: int, data: ClientEmailSendRequest, request: Request,
                         db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if not data.recipient_email or "@" not in data.recipient_email:
        raise HTTPException(status_code=400, detail="A valid recipient email is required")

    # Family 137, feature 1 - Client Approval Hub: sending this email is
    # what actually puts the estimate in front of the client to decide
    # on - so a still-"draft" estimate moves to "sent" here, the same
    # validated transition the manual status-update endpoint uses. This
    # part is unchanged by the P1-13 defect repair below - it reflects
    # a real, internal state transition, independent of any client-
    # portal link.
    if estimate.status == "draft":
        error = validate_estimate_status_transition(estimate.status, "sent")
        if not error:
            estimate.status = "sent"
            db.add(estimate)

    # Defect repair (P1-13): the persistent review/approval link used
    # to be generated and appended here. Woodful is internal-only now
    # and the public client-portal route it pointed to is no longer
    # served (see clients/portal_api.py), so no token is minted and no
    # link is appended - the estimate PDF still emails normally.

    pdf_buffer = generate_estimate_pdf(estimate)
    email_service = EmailService()
    sent = email_service.send_email(
        to_email=data.recipient_email, subject=data.subject, body=data.body, is_html=False,
        attachment_bytes=pdf_buffer.read(), attachment_filename=f"Estimate-{estimate.estimate_code}.pdf",
    )

    db.add(ClientActivity(
        client_id=estimate.client_id, activity_type="Email",
        summary=f"Emailed estimate {estimate.estimate_code} to {data.recipient_email} - subject: {data.subject}"
                + ("" if sent else " (SEND FAILED - see server logs)"),
        logged_by=auth.get("email") or "system",
    ))
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="send_estimate_email",
               module_name="estimates", record_id=estimate.id,
               new_value={"recipient": data.recipient_email, "sent": sent,
                          "sender": email_service.sender_email, "attachment_filename": f"Estimate-{estimate.estimate_code}.pdf"})

    if not sent:
        reason_text = {
            "missing_configuration": "Email sending is not configured on this server (SENDER_EMAIL/SENDER_PASSWORD/SMTP settings).",
            "authentication_failed": "The email account's login was rejected by the mail server - check the sender email and app password.",
            "connection_failed": "Could not reach the mail server - check SMTP_SERVER/SMTP_PORT and network/firewall settings.",
            "smtp_error": "The mail server rejected this message.",
            "unknown_error": "An unexpected error occurred while sending.",
        }.get(email_service.last_error, "email service unavailable or misconfigured")
        raise HTTPException(
            status_code=502,
            detail=f"The estimate could not be emailed right now ({reason_text}). "
                   f"The estimate itself is unaffected - this only failed to send.",
        )
    return ClientEmailSendResult(sent=True, message=f"Estimate emailed to {data.recipient_email}.")


@estimates_router.put("/{estimate_id}", response_model=EstimateResponse)
def update_estimate(estimate_id: int, data: EstimateUpdate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    update_fields = data.dict(exclude_unset=True, exclude={"line_items"})

    if "status" in update_fields:
        error = validate_estimate_status_transition(estimate.status, update_fields["status"])
        if error:
            raise HTTPException(status_code=400, detail=error)

    # Once an estimate is finalized (approved/rejected/expired/cancelled),
    # its content is a historical record. The one
    # thing still allowed from a finalized state is a further status
    # transition explicitly permitted above (e.g. approved -> cancelled);
    # everything else (costs, discount, tax, valid_until, line items)
    # requires creating a new version via /revise instead.
    #
    # "Touched" means the submitted value actually differs from what's
    # stored, not merely present in the request - the frontend's edit
    # form resubmits every field on every save (changed or not), so a
    # pure status change (approved -> cancelled) would otherwise always
    # look like it also touched material_cost/labor_cost/tax_percent
    # just because they were echoed back unchanged.
    CONTENT_FIELDS = {"material_cost", "labor_cost", "discount", "tax_percent", "valid_until"}
    is_finalized = estimate.status in ESTIMATE_FINALIZED_STATUSES
    touches_content = data.line_items is not None or any(
        field in update_fields and update_fields[field] != getattr(estimate, field)
        for field in CONTENT_FIELDS
    )
    if is_finalized and touches_content:
        raise HTTPException(
            status_code=400,
            detail=f"This estimate is '{estimate.status}' and its content is final. "
                    f"Create a new revision instead of editing it directly.",
        )

    old_value = serializable_fields(estimate, update_fields.keys())
    for field, value in update_fields.items():
        setattr(estimate, field, value)

    if data.line_items is not None:
        # Replace the whole set - editing an estimate's line items is a
        # "these are the current items" operation, not an incremental
        # patch, matching how the frontend's item editor works (it
        # submits the full current list, not a diff).
        for existing in list(estimate.line_items):
            db.delete(existing)
        db.flush()
        new_items = _build_line_items(db, data.line_items, estimate_id=estimate.id)
        for item in new_items:
            db.add(item)
        db.flush()
        subtotal = sum((item.amount for item in new_items), Decimal("0"))
        estimate.material_cost = sum((i.amount for i in new_items if i.category == "Material"), Decimal("0"))
        estimate.labor_cost = sum((i.amount for i in new_items if i.category == "Labor"), Decimal("0"))
    else:
        subtotal = estimate.subtotal

    if data.line_items is not None or any(f in update_fields for f in ("material_cost", "labor_cost", "discount", "tax_percent")):
        estimate.tax_amount, estimate.total_cost = _compute_totals(subtotal, estimate.discount, estimate.tax_percent)

    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    new_value = serializable_fields(estimate, update_fields.keys())
    if data.line_items is not None:
        new_value["items_changed"] = True

    STATUS_ACTION_NAMES = {
        "sent": "send_estimate", "approved": "accept_estimate", "rejected": "reject_estimate",
        "expired": "expire_estimate", "cancelled": "cancel_estimate",
    }
    action = STATUS_ACTION_NAMES.get(update_fields.get("status"), "update_estimate")
    log_action(db, request, user_id=auth.get("user_id"), action=action, module_name="estimates",
               record_id=estimate.id, old_value=old_value, new_value=new_value)
    return estimate


@estimates_router.post("/{estimate_id}/revise", response_model=EstimateResponse, status_code=201)
def revise_estimate(estimate_id: int, request: Request, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Create a new version of an estimate rather than overwriting it -
    copies the source estimate's figures (including its line items) into
    a new row, incrementing the version number and always pointing
    parent_estimate_id at the root of the chain (not necessarily the
    immediate source), so /versions can find every revision with one
    query."""
    source = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Estimate not found")

    root_id = source.parent_estimate_id or source.id

    for _ in range(5):
        latest_version = db.query(Estimate).filter(
            (Estimate.id == root_id) | (Estimate.parent_estimate_id == root_id)
        ).order_by(Estimate.version.desc()).first()
        next_version = (latest_version.version if latest_version else source.version) + 1

        new_code = f"{source.estimate_code.split('-v')[0]}-v{next_version}"
        revision = Estimate(
            estimate_code=new_code, business_id=generate_business_id(db),
            client_id=source.client_id, order_id=None,
            description=source.description, material_cost=source.material_cost, labor_cost=source.labor_cost,
            discount=source.discount, tax_percent=source.tax_percent, tax_amount=source.tax_amount,
            total_cost=source.total_cost, valid_until=source.valid_until, remarks=source.remarks,
            margin_percent_override=source.margin_percent_override,
            version=next_version, parent_estimate_id=root_id, status="draft",
        )
        db.add(revision)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        break
    else:
        raise HTTPException(status_code=500, detail="Unable to create a new revision, please try again")

    for idx, item in enumerate(source.line_items):
        db.add(EstimateLineItem(
            estimate_id=revision.id, description=item.description, category=item.category,
            quantity=item.quantity, unit=item.unit, rate=item.rate, amount=item.amount, sort_order=idx,
            product_id=item.product_id, is_custom_item=item.is_custom_item,
            pricing_rule_applied=item.pricing_rule_applied, applied_margin_percent=item.applied_margin_percent,
        ))
    db.commit()
    db.refresh(revision)
    log_action(db, request, user_id=auth.get("user_id"), action="revise_estimate", module_name="estimates",
               record_id=revision.id, old_value={"source_estimate_id": source.id, "source_version": source.version},
               new_value={"new_version": revision.version, "estimate_code": revision.estimate_code})
    return revision


@estimates_router.get("/{estimate_id}/versions", response_model=List[EstimateResponse])
def list_estimate_versions(estimate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Every version in the same chain as estimate_id, oldest first."""
    source = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Estimate not found")

    root_id = source.parent_estimate_id or source.id
    versions = db.query(Estimate).filter(
        (Estimate.id == root_id) | (Estimate.parent_estimate_id == root_id)
    ).order_by(Estimate.version.asc()).all()
    return _serialize_estimates(versions, auth.get("role", "user"))


# --- estimate_imports.py ---
estimate_imports_router = APIRouter(prefix="/api/estimate-imports", tags=["estimate-imports"])


@estimate_imports_router.get("/template")
def download_estimate_import_template(auth=Depends(require_role("master"))):
    buffer = build_estimate_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Estimate_Import_Template.xlsx"},
    )


def _read_estimate_upload(file: UploadFile) -> bytes:
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    allowed_mime_types = {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
            )
    return bytes(file_bytes)


@estimate_imports_router.post("/preview", response_model=EstimateImportPreviewResponse)
def preview_estimate_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates both sheets, matches Estimate ID / Client /
    Product ID against real records, and groups item rows under their
    header row by Estimate Row #. Never writes to the database - see
    module docstring in app/modules/sales/imports.py."""
    try:
        file_bytes = _read_estimate_upload(file)
        raw_headers, raw_items = parse_estimate_uploaded_workbook(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Couldn't read this file - please upload a valid .xlsx file using the downloaded template.",
        )

    estimates_by_code = {normalize_match_key(e.estimate_code): e for e in db.query(Estimate).all()}
    if_business = {normalize_match_key(e.business_id): e for e in db.query(Estimate).all() if e.business_id}
    estimates_by_code.update(if_business)

    clients_by_key = {}
    for c in db.query(Client).all():
        clients_by_key[(normalize_match_key(c.name), normalize_phone_key(c.phone))] = c

    products_by_code = {}
    for p in db.query(Product).all():
        products_by_code[normalize_match_key(p.product_code)] = p
        if p.business_id:
            products_by_code.setdefault(normalize_match_key(p.business_id), p)

    header_previews = []
    ref_to_header_idx = {}
    seen_estimate_ids_in_file = {}
    for idx, row in enumerate(raw_headers, start=1):
        result, errors = validate_estimate_header_row(row, idx, db, estimates_by_code, clients_by_key)
        # Two rows in the same file both updating the same existing
        # estimate would otherwise commit silently - the second row's
        # values would overwrite the first's with no warning that this
        # happened, since both independently validate successfully
        # against the same pre-upload snapshot.
        matched_estimate_id = result.get("matched_estimate_id")
        if not errors and matched_estimate_id is not None:
            if matched_estimate_id in seen_estimate_ids_in_file:
                errors = errors + [
                    f"This estimate is also being updated by row {seen_estimate_ids_in_file[matched_estimate_id]} "
                    f"in this same file - only one of these will end up taking effect."
                ]
            else:
                seen_estimate_ids_in_file[matched_estimate_id] = idx
        header_previews.append(EstimateImportHeaderPreview(**result, errors=errors, items=[]))
        # A header row's own spreadsheet position (idx, 1-based among
        # header rows) is what item rows reference via Estimate Row # -
        # this is a workbook-local grouping key, not a database column.
        ref_to_header_idx[idx] = len(header_previews) - 1

    orphan_items = []
    item_error_count = 0
    for idx, row in enumerate(raw_items, start=1):
        result, errors = validate_estimate_item_row(row, idx, products_by_code)
        preview_item = EstimateImportItemPreview(**result, errors=errors)
        ref = result.get("estimate_ref")
        if ref is not None and ref in ref_to_header_idx:
            header_previews[ref_to_header_idx[ref]].items.append(preview_item)
        else:
            if ref is not None:
                preview_item.errors.append(
                    f'Estimate Row # {ref} does not match any row on the Estimate Header sheet.'
                )
            orphan_items.append(preview_item)

    valid_count = 0
    error_count = 0
    new_count = 0
    existing_count = 0
    for h in header_previews:
        item_errors = any(it.errors for it in h.items)
        has_items = len(h.items) > 0
        if not has_items and not h.errors:
            h.errors.append("This estimate has no valid item rows on the Estimate Items sheet.")
        if h.errors or item_errors or not has_items:
            error_count += 1
        else:
            valid_count += 1
            subtotal = sum((it.amount for it in h.items if it.amount is not None), Decimal("0"))
            tax_amount, total = compute_totals(subtotal, h.discount or Decimal("0"), h.tax_percent or Decimal("18"))
            h.computed_subtotal = subtotal
            h.computed_tax_amount = tax_amount
            h.computed_total = total
            if h.is_new_estimate:
                new_count += 1
            else:
                existing_count += 1

    return EstimateImportPreviewResponse(
        total_estimates=len(header_previews), valid_estimates=valid_count, error_estimates=error_count,
        new_estimates=new_count, existing_estimates=existing_count,
        orphan_item_rows=orphan_items, estimates=header_previews,
    )


@estimate_imports_router.post("/error-report")
def download_estimate_import_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the header+item
    grouping logic /preview uses) and returns a real .xlsx listing
    every rejected header row and every rejected item row, each
    labeled with its source sheet so a person can find and fix it -
    matching the established pattern from client_imports.py (Section
    23), adapted for this import's two-sheet structure."""
    file_bytes = _read_estimate_upload(file)
    try:
        raw_headers, raw_items = parse_estimate_uploaded_workbook(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Couldn't read this file - please upload a valid .xlsx file.")

    estimates_by_code = {normalize_match_key(e.estimate_code): e for e in db.query(Estimate).all()}
    if_business = {normalize_match_key(e.business_id): e for e in db.query(Estimate).all() if e.business_id}
    estimates_by_code.update(if_business)
    clients_by_key = {}
    for c in db.query(Client).all():
        clients_by_key[(normalize_match_key(c.name), normalize_phone_key(c.phone))] = c
    products_by_code = {}
    for p in db.query(Product).all():
        products_by_code[normalize_match_key(p.product_code)] = p
        if p.business_id:
            products_by_code.setdefault(normalize_match_key(p.business_id), p)

    error_rows = []
    for idx, row in enumerate(raw_headers, start=1):
        result, errors = validate_estimate_header_row(row, idx, db, estimates_by_code, clients_by_key)
        if errors:
            error_rows.append({
                "sheet": "Estimate Header", "row": idx, "reference": result.get("client_name") or "",
                "reason": "; ".join(errors),
            })
    for idx, row in enumerate(raw_items, start=1):
        result, errors = validate_estimate_item_row(row, idx, products_by_code)
        if errors:
            error_rows.append({
                "sheet": "Estimate Items", "row": idx, "reference": result.get("description") or "",
                "reason": "; ".join(errors),
            })

    from app.shared import build_workbook
    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Estimate Import Error Report",
        "subtitle": f"{len(error_rows)} rejected row(s) across both sheets. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["sheet", "row", "reference", "reason"],
        "headers": ["Sheet", "Row", "Reference", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Estimate_Import_Errors.xlsx"},
    )


@estimate_imports_router.post("/commit", response_model=EstimateImportCommitResult)
def commit_estimate_import(data: EstimateImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Creates/updates one Estimate (header + line items) per confirmed
    row. Each estimate commits as its own all-or-nothing transaction
    (spec sections 21/48): if any item in an estimate fails, only that
    estimate rolls back and is reported as an error - estimates already
    committed earlier in the same request stay committed, matching the
    existing per-record commit behaviour used by product/purchase
    import. Totals are always recomputed here via compute_totals, never
    taken from the request (spec section 23)."""
    results = []
    created_count = updated_count = skipped_count = error_count = 0

    for row in data.estimates:
        if row.skip:
            skipped_count += 1
            results.append(EstimateImportCommitResultRow(skipped=True))
            continue

        try:
            product_ids = {item.product_id for item in row.items}
            found_products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
            missing = product_ids - set(found_products.keys())
            if missing:
                raise ValueError(f"Invalid Product ID(s): {sorted(missing)}")
            inactive = [p.name for p in found_products.values() if not p.is_active]
            if inactive:
                raise ValueError(f"Cannot use inactive product(s): {', '.join(inactive)}")

            client = db.query(Client).filter(Client.id == row.client_id).first()
            if not client:
                raise ValueError("Invalid Client ID")

            line_items = []
            for item in row.items:
                amount = (item.quantity * item.rate)
                if item.discount_percent:
                    amount = amount - (amount * item.discount_percent / Decimal("100"))
                amount = amount.quantize(Decimal("0.01"))
                line_items.append(EstimateLineItem(
                    description=item.description, category=item.category, quantity=item.quantity,
                    unit=item.unit, rate=item.rate, amount=amount, product_id=item.product_id,
                ))
            subtotal = sum((li.amount for li in line_items), Decimal("0"))
            tax_amount, total_cost = compute_totals(subtotal, row.discount, row.tax_percent)
            material_cost = sum((li.amount for li in line_items if li.category == "Material"), Decimal("0"))
            labor_cost = sum((li.amount for li in line_items if li.category == "Labor"), Decimal("0"))

            if row.matched_estimate_id:
                estimate = db.query(Estimate).filter(Estimate.id == row.matched_estimate_id).first()
                if not estimate:
                    raise ValueError("Estimate no longer exists")
                if estimate.status in ESTIMATE_FINALIZED_STATUSES:
                    raise ValueError(
                        f'Estimate {estimate.estimate_code} is "{estimate.status}" and can no longer be '
                        f'edited by re-import - use the Revise workflow instead.'
                    )
                old_value = {"total_cost": float(estimate.total_cost or 0), "line_item_count": len(estimate.line_items)}
                if estimate.order_id:
                    linked_order = db.query(Order).filter(Order.id == estimate.order_id).first()
                    if linked_order and linked_order.client_id != client.id:
                        raise ValueError(
                            f"Estimate {estimate.estimate_code} is already linked to an order belonging to a "
                            f"different client - re-import cannot reassign its client."
                        )
                # Estimate Date is not re-writable on an existing estimate -
                # it reflects when the estimate was first created
                # (Estimate.created_at), not when it was re-imported.
                estimate.client_id = client.id
                estimate.valid_until = row.valid_until
                estimate.margin_percent_override = row.margin_percent
                estimate.discount = row.discount
                estimate.tax_percent = row.tax_percent
                estimate.tax_amount = tax_amount
                estimate.total_cost = total_cost
                estimate.material_cost = material_cost
                estimate.labor_cost = labor_cost
                if row.notes is not None:
                    estimate.remarks = row.notes
                # Re-import replaces this estimate's line items wholesale
                # with what was reviewed/confirmed in preview, rather than
                # trying to diff-merge individual lines.
                for existing_item in list(estimate.line_items):
                    db.delete(existing_item)
                db.flush()
                for li in line_items:
                    li.estimate_id = estimate.id
                    db.add(li)
                db.commit()
                db.refresh(estimate)
                log_action(db, request, user_id=auth.get("user_id"), action="import_update_estimate",
                           module_name="estimates", record_id=estimate.id,
                           old_value=old_value, new_value={"total_cost": float(estimate.total_cost or 0)})
                updated_count += 1
                results.append(EstimateImportCommitResultRow(
                    estimate_id=estimate.id, estimate_code=estimate.estimate_code, updated=True))
            else:
                created_id = None
                for _ in range(5):
                    code = generate_unique_code(db, Estimate, "estimate_code", "EST-")
                    estimate_kwargs = dict(
                        estimate_code=code, business_id=generate_business_id(db), client_id=client.id,
                        valid_until=row.valid_until, margin_percent_override=row.margin_percent,
                        discount=row.discount, tax_percent=row.tax_percent, tax_amount=tax_amount,
                        total_cost=total_cost, material_cost=material_cost, labor_cost=labor_cost,
                        remarks=row.notes, status="draft",
                    )
                    if row.estimate_date:
                        estimate_kwargs["created_at"] = row.estimate_date
                    estimate = Estimate(**estimate_kwargs)
                    db.add(estimate)
                    try:
                        db.flush()
                        created_id = estimate.id
                        break
                    except IntegrityError:
                        db.rollback()
                        continue
                if created_id is None:
                    raise ValueError("Could not generate a unique estimate code")
                for li in line_items:
                    li.estimate_id = created_id
                    db.add(li)
                db.commit()
                db.refresh(estimate)
                log_action(db, request, user_id=auth.get("user_id"), action="import_create_estimate",
                           module_name="estimates", record_id=estimate.id,
                           new_value={"client_id": client.id, "estimate_code": estimate.estimate_code,
                                      "total_cost": float(estimate.total_cost or 0)})
                created_count += 1
                results.append(EstimateImportCommitResultRow(
                    estimate_id=estimate.id, estimate_code=estimate.estimate_code, created=True))

        except (ValueError, HTTPException) as e:
            db.rollback()
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_count += 1
            results.append(EstimateImportCommitResultRow(error=detail))

    return EstimateImportCommitResult(
        created_count=created_count, updated_count=updated_count,
        skipped_count=skipped_count, error_count=error_count, results=results,
    )


# --- payments.py ---
logger = logging.getLogger(__name__)


payments_router = APIRouter(prefix="/api/payments", tags=["payments"])


PAYMENT_DOC_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


PAYMENT_DOC_ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}


@payments_router.get("/", response_model=List[PaymentResponse])
def list_payments(order_id: Optional[int] = Query(None), client_id: Optional[int] = Query(None),
                   limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                   db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    if client_id:
        # One join instead of the caller fetching per-order and merging -
        # a client with many orders would otherwise mean many round trips.
        query = query.join(Order, Payment.order_id == Order.id).filter(Order.client_id == client_id)
    query = query.order_by(Payment.date.desc())
    if limit is not None:
        # Optional and unbounded by default on purpose - PaymentsPage
        # renders the full list with no client-side pagination of its
        # own, so a default limit here would silently truncate that
        # page. Only callers that explicitly ask (the dashboard) get a
        # bounded result.
        query = query.offset(offset).limit(limit)
    return query.all()


@payments_router.post("/", response_model=PaymentResponse, status_code=201)
def create_payment(data: PaymentCreate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payment = OrderService.record_payment(db, data)
    log_action(db, request, user_id=auth.get("user_id"), action="create_payment",
               module_name="payments", record_id=payment.id, new_value={"amount": str(payment.amount)})
    return payment


@payments_router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: int, db: Session = Depends(get_db),
                 auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@payments_router.get("/{payment_id}/email-preview", response_model=ClientEmailPreview)
def preview_payment_receipt_email(payment_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = payment.order
    client = order.client
    subject = f"Payment Receipt - {order.order_code} - Woodful Creations"
    body = (
        f"Dear {client.name},\n\n"
        f"Thank you for your payment of Rs {payment.amount:,.2f} against order {order.order_code}.\n\n"
        f"Please find the receipt attached.\n\n"
        f"Regards,\nWoodful Creations"
    )
    return ClientEmailPreview(
        recipient_email=client.email, client_has_email=bool(client.email),
        subject=subject, body=body,
        attachment_filename=f"Receipt-{payment.receipt_code or payment.id}.pdf",
    )


@payments_router.post("/{payment_id}/send-email", response_model=ClientEmailSendResult)
def send_payment_receipt_email(payment_id: int, data: ClientEmailSendRequest, request: Request,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not data.recipient_email or "@" not in data.recipient_email:
        raise HTTPException(status_code=400, detail="A valid recipient email is required")

    order = payment.order
    # Prefer the actual uploaded receipt scan if one exists for this
    # payment (the real proof of payment) - only fall back to the
    # invoice PDF (which shows payment/received-amount detail) when
    # nothing was ever uploaded.
    uploaded_receipt = db.query(PaymentDocument).filter(PaymentDocument.payment_id == payment.id).first()
    if uploaded_receipt:
        backend, storage_ref = get_storage_backend_for_record(uploaded_receipt)
        attachment_bytes = backend.read(storage_ref)
        attachment_filename = uploaded_receipt.original_filename
    else:
        all_payments = db.query(Payment).filter(Payment.order_id == order.id).order_by(Payment.date).all()
        pdf_buffer = generate_invoice_pdf(order, all_payments)
        attachment_bytes = pdf_buffer.read()
        attachment_filename = f"Receipt-{payment.receipt_code or payment.id}.pdf"

    email_service = EmailService()
    sent = email_service.send_email(
        to_email=data.recipient_email, subject=data.subject, body=data.body, is_html=False,
        attachment_bytes=attachment_bytes, attachment_filename=attachment_filename,
    )

    db.add(ClientActivity(
        client_id=order.client_id, activity_type="Email",
        summary=f"Emailed payment receipt for {order.order_code} to {data.recipient_email} - amount Rs {payment.amount:,.2f}"
                + ("" if sent else " (SEND FAILED - see server logs)"),
        logged_by=auth.get("email") or "system",
    ))
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="send_payment_receipt_email",
               module_name="payments", record_id=payment.id,
               new_value={"recipient": data.recipient_email, "sent": sent,
                          "sender": email_service.sender_email, "attachment_filename": attachment_filename})

    if not sent:
        reason_text = {
            "missing_configuration": "Email sending is not configured on this server (SENDER_EMAIL/SENDER_PASSWORD/SMTP settings).",
            "authentication_failed": "The email account's login was rejected by the mail server - check the sender email and app password.",
            "connection_failed": "Could not reach the mail server - check SMTP_SERVER/SMTP_PORT and network/firewall settings.",
            "smtp_error": "The mail server rejected this message.",
            "unknown_error": "An unexpected error occurred while sending.",
        }.get(email_service.last_error, "email service unavailable or misconfigured")
        raise HTTPException(
            status_code=502,
            detail=f"The receipt could not be emailed right now ({reason_text}). "
                   f"The payment itself is unaffected - this only failed to send.",
        )
    return ClientEmailSendResult(sent=True, message=f"Receipt emailed to {data.recipient_email}.")


@payments_router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(payment_id: int, data: PaymentUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    updates = data.dict(exclude_unset=True)

    # Locked before validating, same as record_payment - a concurrent
    # update/create/delete against the same order must not be able to
    # observe a pre-lock total and let this update through based on
    # stale numbers.
    order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()

    if "amount" in updates:
        other_payments_total = sum(
            (p.amount for p in order.payments if p.id != payment.id), Decimal("0")
        )
        prospective_total = (order.advance or Decimal("0")) + other_payments_total + updates["amount"]
        if prospective_total > (order.order_value or Decimal("0")):
            raise HTTPException(
                status_code=400,
                detail=f"Changing this payment to Rs {updates['amount']} would bring total received to "
                       f"Rs {prospective_total}, which exceeds the order value of Rs {order.order_value}.",
            )

    old_value = serializable_fields(payment, updates.keys())
    for field, value in updates.items():
        setattr(payment, field, value)
    db.add(payment)
    order.recompute_totals()
    db.add(order)
    db.commit()
    db.refresh(payment)
    log_action(db, request, user_id=auth.get("user_id"), action="update_payment", module_name="payments",
               record_id=payment.id, old_value=old_value, new_value=serializable_fields(payment, updates.keys()))
    return payment


@payments_router.delete("/{payment_id}", status_code=204)
def delete_payment(payment_id: int, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Was entirely missing - a payment recorded in error (wrong order,
    duplicate entry, wrong amount typed in) had no way to actually be
    removed, only edited, which is not the same thing and leaves a
    phantom record. Recomputes the order's total_received/balance the
    same way record_payment and update_payment do, so a deleted
    payment can never leave a stale balance behind."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    old_value = {
        "receipt_code": payment.receipt_code, "order_id": payment.order_id,
        "amount": str(payment.amount), "payment_type": payment.payment_type,
        "payment_mode": payment.payment_mode, "date": str(payment.date),
    }
    # Locked before mutating, same as record_payment/update_payment -
    # a concurrent create/update against the same order must always
    # see this deletion's effect or be blocked until it commits, never
    # interleave with it.
    order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
    db.delete(payment)
    db.flush()
    order.recompute_totals()
    db.add(order)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_payment", module_name="payments",
               record_id=payment_id, old_value=old_value)


@payments_router.get("/{payment_id}/documents", response_model=List[PaymentDocumentResponse])
def list_payment_documents(payment_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    if not db.query(Payment).filter(Payment.id == payment_id).first():
        raise HTTPException(status_code=404, detail="Payment not found")
    return db.query(PaymentDocument).filter(PaymentDocument.payment_id == payment_id).order_by(
        PaymentDocument.created_at.desc()
    ).all()


@payments_router.post("/{payment_id}/documents", response_model=PaymentDocumentResponse, status_code=201)
def upload_payment_document(payment_id: int, file: UploadFile = File(...), description: Optional[str] = None,
                             request: Request = None, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    """Proof of payment - cheque scan, UPI screenshot, bank transfer
    receipt. Same validation discipline already established for
    client documents and candidate resumes: extension allowlist, MIME
    check, a real streamed byte count against the size limit, and a
    random server-side filename never derived from user input."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    original_name = file.filename or "document"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in PAYMENT_DOC_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File must be a PDF, JPG, or PNG (got .{ext or 'unknown'}).")
    if file.content_type not in PAYMENT_DOC_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    backend = get_storage_backend()
    stored_filename = f"payment_documents/{secrets.token_hex(16)}.{ext}"

    size = 0
    first_chunk = True
    chunks = []
    try:
        while chunk := file.file.read(1024 * 1024):
            if first_chunk:
                if not validate_file_signature(ext, chunk):
                    raise HTTPException(
                        status_code=400,
                        detail="The file's contents don't match its extension. Please upload a genuine file of the stated type.",
                    )
                first_chunk = False
            size += len(chunk)
            if size > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
                )
            chunks.append(chunk)
        storage_ref = backend.save(stored_filename, b"".join(chunks))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save the uploaded file.")

    document = PaymentDocument(
        payment_id=payment_id, original_filename=original_name, stored_filename=stored_filename,
        content_type=file.content_type, description=description, uploaded_by=str(auth.get("user_id", "")),
        storage_backend=storage_ref.backend, drive_file_id=storage_ref.drive_file_id,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            backend.delete(storage_ref)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to save the document record.")
    db.refresh(document)
    if request is not None:
        log_action(db, request, user_id=auth.get("user_id"), action="upload_payment_document", module_name="payments",
                   record_id=document.id, new_value={"payment_id": payment_id, "filename": original_name})
    return document


@payments_router.get("/{payment_id}/documents/{document_id}/download")
def download_payment_document(payment_id: int, document_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """Object-level check: the document must actually belong to the
    payment_id in the URL, not just exist by document_id - the same
    IDOR protection already established for client documents."""
    document = db.query(PaymentDocument).filter(
        PaymentDocument.id == document_id, PaymentDocument.payment_id == payment_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    backend, storage_ref = get_storage_backend_for_record(document)
    if not backend.exists(storage_ref):
        raise HTTPException(status_code=404, detail="The stored file could not be found.")
    file_bytes = backend.read(storage_ref)
    return Response(
        content=file_bytes, media_type=document.content_type or "application/octet-stream",
        headers={
            "Cache-Control": "no-store, private",
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
        },
    )


@payments_router.delete("/{payment_id}/documents/{document_id}", status_code=204)
def delete_payment_document(payment_id: int, document_id: int, request: Request, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    document = db.query(PaymentDocument).filter(
        PaymentDocument.id == document_id, PaymentDocument.payment_id == payment_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    backend, storage_ref = get_storage_backend_for_record(document)
    old_value = {"payment_id": payment_id, "filename": document.original_filename}
    db.delete(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete the document record.")
    try:
        backend.delete(storage_ref)
    except Exception:
        logger.error(f"Orphaned file after payment document {document_id} delete: {storage_ref}")
    log_action(db, request, user_id=auth.get("user_id"), action="delete_payment_document", module_name="payments",
               record_id=document_id, old_value=old_value)


# --- reports.py ---
"""Sales-domain report exports: payments, estimates, orders,
order profitability, and the estimate/order/invoice PDFs. Split out of
the former monolithic reports.py - see modules/inventory/api/reports.py's
docstring for why."""

reports_router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@reports_router.get("/payments.xlsx")
def export_payments(
    order_id: Optional[int] = None, client_id: Optional[int] = None,
    payment_mode: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    query = db.query(Payment)
    filters_applied = []
    if order_id:
        query = query.filter(Payment.order_id == order_id)
        filters_applied.append(f"Order #{order_id}")
    if client_id:
        query = query.join(Order, Payment.order_id == Order.id).filter(Order.client_id == client_id)
        filters_applied.append(f"Client #{client_id}")
    if payment_mode:
        query = query.filter(Payment.payment_mode == payment_mode)
        filters_applied.append(f"Mode: {payment_mode}")
    if start_date:
        query = query.filter(Payment.date >= datetime.fromisoformat(start_date))
        filters_applied.append(f"From {start_date}")
    if end_date:
        query = query.filter(Payment.date <= datetime.fromisoformat(end_date))
        filters_applied.append(f"To {end_date}")

    payments = query.options(
        selectinload(Payment.order).selectinload(Order.client)
    ).order_by(Payment.date.desc()).all()
    rows = [{
        # Per spec section 2A, "Receipt ID" is the 10-character business ID
        # (e.g. A7K92P4XQ1) - receipt_code (RCPT-001) is kept as a secondary
        # human-scannable sequential reference, same distinction used
        # everywhere else business_id coexists with a *_code field.
        "receipt_id": p.business_id or "", "receipt_code": p.receipt_code,
        "payment_reference": p.reference_number or "",
        "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "order": p.order.order_code if p.order else "",
        "client_id": p.order.client.business_id if p.order and p.order.client else "",
        "client": p.order.client.name if p.order and p.order.client else "",
        "project": p.order.project_type if p.order else "",
        "payment_type": p.payment_type, "payment_mode": p.payment_mode, "amount": float(p.amount),
        "received_by": p.received_by or "", "notes": p.remarks or "",
    } for p in payments]
    columns = ["receipt_id", "receipt_code", "payment_reference", "date", "order", "client_id", "client",
               "project", "payment_type", "payment_mode", "amount", "received_by", "notes"]
    headers = ["Receipt ID", "Receipt Code", "Payment Reference", "Date", "Order ID", "Client ID", "Client Name",
               "Project", "Payment Type", "Payment Mode", "Amount", "Received By", "Notes"]

    total_amount = sum(float(p.amount) for p in payments)
    by_mode = {}
    for p in payments:
        by_mode[p.payment_mode] = by_mode.get(p.payment_mode, 0) + float(p.amount)
    summary = [("Total Payments", f"{len(payments)}"), ("Total Amount", f"Rs {total_amount:,.2f}")]
    summary += [(f"  {mode}", f"Rs {amt:,.2f}") for mode, amt in sorted(by_mode.items())]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Payments", "title": "CLIENT PAYMENT REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": ["amount"], "subtitle": subtitle, "summary": summary,
    }])
    filename = f"payment_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/estimates.xlsx")
def export_estimates(
    client_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    query = db.query(Estimate).options(selectinload(Estimate.client))
    filters_applied = []
    if client_id:
        query = query.filter(Estimate.client_id == client_id)
        client = db.query(Client).filter(Client.id == client_id).first()
        filters_applied.append(f"Client: {client.name if client else client_id}")
    if status:
        query = query.filter(Estimate.status == status)
        filters_applied.append(f"Status: {status}")

    estimates = query.order_by(Estimate.created_at.desc()).all()
    rows = [{
        "estimate_id": e.business_id or "", "estimate_code": e.estimate_code,
        "client": e.client.name if e.client else "", "version": e.version,
        "material_cost": float(e.material_cost or 0), "labor_cost": float(e.labor_cost or 0),
        "discount": float(e.discount or 0), "tax_percent": float(e.tax_percent or 0),
        "tax_amount": float(e.tax_amount or 0), "total_cost": float(e.total_cost or 0),
        "status": e.status, "converted_to_order": "Yes" if e.order_id else "No",
        "valid_until": e.valid_until.strftime("%d-%m-%Y") if e.valid_until else "",
    } for e in estimates]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Estimates", str(len(estimates))),
        ("Approved", str(sum(1 for e in estimates if e.status == "approved"))),
        ("Converted to Orders", str(sum(1 for e in estimates if e.order_id))),
        ("Total Value", f"Rs {sum(float(e.total_cost or 0) for e in estimates):,.2f}"),
    ]

    buffer = build_workbook([{
        "sheet_name": "Estimates", "title": "ESTIMATES & QUOTATIONS REPORT",
        "columns": ["estimate_id", "estimate_code", "client", "version", "material_cost", "labor_cost",
                    "discount", "tax_percent", "tax_amount", "total_cost", "status", "converted_to_order", "valid_until"],
        "headers": ["Estimate ID", "Code", "Client", "Version", "Material Cost", "Labor Cost",
                    "Discount", "Tax %", "Tax Amount", "Total Cost", "Status", "Converted to Order", "Valid Until"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"estimates_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/order-profitability.xlsx")
def export_order_profitability(db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    orders = db.query(Order).order_by(Order.order_date.desc()).all()
    profitability_by_order = OrderService.profitability_bulk(db, orders)
    rows = []
    for o in orders:
        p = profitability_by_order[o.id]
        rows.append({
            "order_id": p["order_id"], "business_id": p["business_id"], "client": p["client"], "project_type": p["project_type"],
            "order_value": p["order_value"], "total_received": p["total_received"],
            "pending_payment": p["pending_payment"], "project_expenses": p["project_expenses"],
            "material_cost": p["material_cost"],
            "estimated_gross_profit": p["estimated_gross_profit"],
            "gross_margin_ratio": p["gross_margin_ratio"], "status": p["status"],
        })
    columns = ["order_id", "business_id", "client", "project_type", "order_value", "total_received",
               "pending_payment", "project_expenses", "material_cost", "estimated_gross_profit",
               "gross_margin_ratio", "status"]
    headers = ["Order ID", "Business ID", "Client", "Project Type", "Order Value", "Total Received",
               "Pending Payment", "Project Expenses", "Material Cost", "Estimated Gross Profit",
               "Gross Margin %", "Status"]
    buffer = build_workbook([{"sheet_name": "Order Profitability", "title": "ORDER-WISE PROFITABILITY REPORT",
                               "columns": columns, "headers": headers, "rows": rows,
                               "total_columns": ["order_value", "total_received", "pending_payment",
                                                  "project_expenses", "material_cost", "estimated_gross_profit"]}])
    return xlsx_response(buffer, "order-profitability.xlsx")


@reports_router.get("/orders.xlsx")
def export_orders(
    status: Optional[str] = Query(None), client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Sales/Orders Register export. Mirrors GET /api/orders/'s
    status/client_id filters. Financial columns (order value, received,
    balance) are master-only, exactly matching the redaction
    _serialize_orders already applies on-screen for a non-master viewer -
    export inherits the same scope as the list view, never more."""
    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Order).options(selectinload(Order.client))
    filters_applied = []
    if status:
        query = query.filter(Order.project_status == status)
        filters_applied.append(f"Status: {status}")
    if client_id:
        query = query.filter(Order.client_id == client_id)
        client_obj = db.query(Client).filter(Client.id == client_id).first()
        filters_applied.append(f"Client: {client_obj.name if client_obj else client_id}")

    orders = query.order_by(Order.order_date.desc()).all()
    risk_flags = OrderService.bulk_attention_flags(db, [o.id for o in orders]) if orders else {}
    rows = []
    for o in orders:
        flag = risk_flags.get(o.id, {})
        row = {
            "order_id": o.business_id or "", "order_code": o.order_code,
            "client": o.client.name if o.client else "", "project_type": o.project_type or "",
            "order_date": o.order_date.strftime("%d-%m-%Y") if o.order_date else "",
            "delivery_date": o.delivery_date.strftime("%d-%m-%Y") if o.delivery_date else "",
            "status": o.project_status, "progress_percent": o.progress_percent,
            "risk_level": flag.get("risk_level", ""), "risk_reason": flag.get("reason") or "",
        }
        if is_privileged:
            row["order_value"] = float(o.order_value or 0)
            row["total_received"] = float(o.total_received or 0)
            row["balance"] = float(o.balance or 0)
        rows.append(row)

    columns = ["order_id", "order_code", "client", "project_type", "order_date", "delivery_date",
               "status", "progress_percent", "risk_level", "risk_reason"]
    headers = ["Order ID", "Order Code", "Client", "Project Type", "Order Date", "Delivery Date",
               "Status", "Progress %", "Delivery Risk", "Risk Reason"]
    total_columns = []
    if is_privileged:
        columns[6:6] = ["order_value", "total_received", "balance"]
        headers[6:6] = ["Order Value", "Total Received", "Balance"]
        total_columns = ["order_value", "total_received", "balance"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [("Total Orders", str(len(orders)))]
    critical_count = sum(1 for f in risk_flags.values() if f.get("risk_level") == "CRITICAL")
    at_risk_count = sum(1 for f in risk_flags.values() if f.get("risk_level") == "AT_RISK")
    if critical_count or at_risk_count:
        summary.append(("Critical / At Risk", f"{critical_count} / {at_risk_count}"))
    if is_privileged:
        summary.append(("Total Order Value", f"Rs {sum(r['order_value'] for r in rows):,.2f}"))
        summary.append(("Total Outstanding", f"Rs {sum(r['balance'] for r in rows):,.2f}"))

    buffer = build_workbook([{
        "sheet_name": "Orders", "title": "SALES / ORDERS REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": total_columns, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"orders_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/orders/{order_id}/estimate.pdf")
def export_order_estimate_pdf(order_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """This PDF includes order_value/total_received -
    the exact fields _serialize_orders() nulls for non-master in the
    JSON API (orders.py). It was previously exportable by any
    authenticated role via get_current_user, letting a USER bypass the
    redaction entirely. Master-only now, matching invoice.pdf below."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    buffer = generate_order_estimate_pdf(order)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        # "order-estimate-", not just "estimate-": this and
        # /estimates/{id}/quote.pdf below both produce an
        # estimate-styled document, but for two different underlying
        # records (an order vs. an actual Estimate) with two different
        # code formats (order_code vs estimate_code) - sharing the same
        # "estimate-{code}.pdf" filename pattern made the two
        # genuinely hard to tell apart once both are sitting in a
        # downloads folder.
        headers={"Content-Disposition": f'attachment; filename="order-estimate-{order.order_code}.pdf"', "Cache-Control": "no-store, private"},
    )


@reports_router.get("/estimates/{estimate_id}/quote.pdf")
def export_estimate_quote_pdf(estimate_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """This PDF includes per-line-item rate/amount -
    the same line-item pricing test_financial_rbac.py already
    proves is nulled for non-master via the JSON API. It was previously
    exportable by any authenticated role via get_current_user. Master-only
    now, matching every other estimate-mutation endpoint in estimates.py."""
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    buffer = generate_estimate_pdf(estimate)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estimate-{estimate.estimate_code}.pdf"', "Cache-Control": "no-store, private"},
    )


@reports_router.get("/orders/{order_id}/invoice.pdf")
def export_order_invoice_pdf(order_id: int, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.date).all()
    buffer = generate_invoice_pdf(order, payments)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{order.order_code}.pdf"', "Cache-Control": "no-store, private"},
    )
