import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.audit import log_action, serializable_fields
from app.models.order import Order
from app.models.client import Client
from app.models.order_comment import OrderComment
from app.models.ai_workspace_report import AIWorkspaceReport
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.estimate import Estimate
from app.models.daily_task import DailyTask
from app.models.task_comment import TaskComment
from app.models.milestone import Milestone
from app.models.notification import Notification
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.schemas.order_comment import OrderCommentCreate, OrderCommentResponse
from app.services.order_service import OrderService
from app.services.notification_service import NotificationService
from app.services.mention_service import notify_mentions
from app.utils.id_generator import generate_unique_code, generate_business_id
from app.utils.status_rules import validate_order_status_value, ORDER_PROJECT_STATUSES
from app.utils.calculations import compute_totals
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _serialize_orders(orders, role: str):
    """Employees can see order status/progress/client/project info, but
    not money - order_value, discount, tax_percent, tax_amount, advance,
    other_received, total_received, balance, items_subtotal, and
    payment_status are genuinely nulled here, including each order
    item's rate/amount (redacting only the order-level total while
    leaving line-item pricing visible would let anyone just sum the
    items back to the real total)."""
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
    return responses


def _serialize_order(order, role: str):
    return _serialize_orders([order], role)[0]


@router.get("/", response_model=List[OrderResponse])
def list_orders(response: Response, status: Optional[str] = Query(None), client_id: Optional[int] = Query(None),
                 overdue_only: bool = Query(False),
                 limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Order)
    if status:
        query = query.filter(Order.project_status == status)
    if client_id:
        query = query.filter(Order.client_id == client_id)
    if overdue_only:
        # Same rule the frontend used to apply client-side: balance still
        # outstanding and the order was placed more than 30 days ago.
        # There is no due-date field on Order, so this is a stated
        # approximation, not a precise "overdue" status - kept in SQL now
        # so it composes correctly with pagination below.
        cutoff = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Order.balance > 0, Order.order_date < cutoff)

    query = query.order_by(Order.order_date.desc())
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if limit is not None:
        query = query.offset(offset).limit(limit)
    return _serialize_orders(query.all(), auth.get("role", "user"))


def _build_order_items(db, items_data, order_id: int = None):
    """Computes amount = quantity * rate server-side for each item -
    never trusted from client input directly, matching the estimate
    line items pattern (including ROUND_HALF_UP - Python's default
    quantize rounding is banker's rounding, which would silently
    disagree with how estimate amounts are computed for the exact same
    calculation).

    Also validates every supplied product_id actually references a
    real, active Product Master row (Family 102 Test 2 / Product ID
    requirement: order line items must reference "the actual Product
    records ... used by the ERP", not just any integer, and product_id
    is now mandatory - Pydantic already rejects a missing one with
    "Product ID is required" before this function ever runs)."""
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


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, request: Request, db: Session = Depends(get_db),
                  auth=Depends(require_role("master"))):
    from decimal import Decimal
    from app.utils.client_matching import find_or_create_client

    payload = data.dict(exclude={
        "order_code", "advance", "items", "from_estimate_id",
        "client_name", "client_phone", "client_email", "client_contact_person",
        "client_address", "client_city", "client_lead_source",
    })

    client_was_created = False
    if data.client_id is not None:
        client = db.query(Client).filter(Client.id == data.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
    else:
        # Client recognition intake (see app/utils/client_matching.py):
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

    if source_estimate and source_estimate.line_items:
        # Copy items from the estimate's line items rather than re-enter
        # them - each new OrderItem stays traceable back to the
        # estimate line it came from via source_estimate_item_id.
        order_items = [
            OrderItem(
                description=li.description, category=li.category, quantity=li.quantity,
                unit=li.unit, rate=li.rate, amount=li.amount,
                source_estimate_item_id=li.id, sort_order=idx, product_id=li.product_id,
            )
            for idx, li in enumerate(source_estimate.line_items)
        ]
    elif data.items:
        order_items = _build_order_items(db, data.items)
    else:
        order_items = []

    # Discount/tax_percent: when converting from an estimate, inherit
    # the estimate's own values unless the caller explicitly overrode
    # them (Family 102 Test 1: "Discount is preserved... GST is
    # preserved... from the Estimate"). model_fields_set distinguishes
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


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _serialize_order(order, auth.get("role", "user"))


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(order_id: int, data: OrderUpdate, request: Request, db: Session = Depends(get_db),
                  auth=Depends(require_role("master"))):
    from decimal import Decimal

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    update_fields = data.dict(exclude_unset=True, exclude={"items"})

    for field_name in ("project_status", "design_status", "execution_status", "delivery_status"):
        if field_name in update_fields:
            error = validate_order_status_value(field_name, update_fields[field_name])
            if error:
                raise HTTPException(status_code=400, detail=error)

    old_value = serializable_fields(order, update_fields.keys())
    for field, value in update_fields.items():
        setattr(order, field, value)

    recompute_needed = (
        data.items is not None or "discount" in update_fields
        or "tax_percent" in update_fields or "order_value" in update_fields
    )

    if data.items is not None:
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
    else:
        # A bare lump-sum order with no line items at all - the
        # caller's order_value IS the subtotal input to discount/tax,
        # same as the equivalent branch in create_order.
        subtotal_base = order.order_value or Decimal("0")

    if recompute_needed:
        tax_amount, grand_total = compute_totals(subtotal_base, order.discount, order.tax_percent)
        order.tax_amount = tax_amount
        order.order_value = grand_total

    order.recompute_totals()

    db.add(order)
    db.commit()
    db.refresh(order)
    new_value = serializable_fields(order, update_fields.keys())
    if data.items is not None:
        new_value["items_changed"] = True
    action = "cancel_order" if update_fields.get("project_status") == "Cancelled" else (
        "change_order_status" if "project_status" in update_fields else "update_order"
    )
    log_action(db, request, user_id=auth.get("user_id"), action=action, module_name="orders",
               record_id=order.id, old_value=old_value, new_value=new_value)
    return order


@router.get("/{order_id}/profitability")
def get_order_profitability(order_id: int, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderService.profitability(db, order)


@router.get("/{order_id}/ai-reports")
def list_order_ai_reports(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Persisted AI workspace reports for this order (Section 10 -
    "artifacts must be viewable"). Open to any role, matching "everyone
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


# --------------------------------------------------------------------- #
# Family 11 - project communication (order-level comments) and the
# order's activity timeline (comments + task comments for its tasks +
# milestone events + relevant notifications, merged and time-ordered).
# --------------------------------------------------------------------- #
@router.get("/{order_id}/comments", response_model=List[OrderCommentResponse])
def list_order_comments(order_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(Order).filter(Order.id == order_id).first():
        raise HTTPException(status_code=404, detail="Order not found")
    return db.query(OrderComment).filter(OrderComment.order_id == order_id).order_by(OrderComment.date.asc()).all()


@router.post("/{order_id}/comments", response_model=OrderCommentResponse, status_code=201)
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


@router.get("/{order_id}/activity")
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
