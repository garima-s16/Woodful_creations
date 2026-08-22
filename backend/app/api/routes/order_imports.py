from decimal import Decimal
from datetime import datetime
import zipfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update as sa_update
from fastapi.responses import StreamingResponse

from app.core.database import get_db
from app.core.config import settings
from app.core.security import require_role
from app.core.audit import log_action
from app.models.client import Client
from app.models.product import Product
from app.models.estimate import Estimate
from app.models.order import Order
from app.models.order_item import OrderItem
from app.utils.id_generator import generate_unique_code, generate_business_id
from app.utils.calculations import compute_totals
from app.utils.order_import import (
    build_import_template, parse_uploaded_workbook,
    validate_header_row, validate_item_row, normalize_match_key, normalize_phone_key,
    ORDER_LOCKED_STATUSES,
)
from app.schemas.order_import import (
    OrderImportPreviewResponse, OrderImportHeaderPreview, OrderImportItemPreview,
    OrderImportCommitRequest, OrderImportCommitResult, OrderImportCommitResultRow,
)

router = APIRouter(prefix="/api/order-imports", tags=["order-imports"])


@router.get("/template")
def download_template():
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Order_Import_Template.xlsx"},
    )


def _read_upload(file: UploadFile) -> bytes:
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


@router.post("/preview", response_model=OrderImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    try:
        file_bytes = _read_upload(file)
        raw_headers, raw_items = parse_uploaded_workbook(file_bytes)
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
    for idx, row in enumerate(raw_headers, start=1):
        result, errors = validate_header_row(row, idx, orders_by_code, clients_by_key, estimates_by_code)
        header_previews.append(OrderImportHeaderPreview(**result, errors=errors, items=[]))
        ref_to_header_idx[idx] = len(header_previews) - 1

    orphan_items = []
    for idx, row in enumerate(raw_items, start=1):
        result, errors = validate_item_row(row, idx, products_by_code)
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


@router.post("/commit", response_model=OrderImportCommitResult)
def commit_import(data: OrderImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Creates/updates one Order per confirmed row - each commits as its
    own all-or-nothing transaction, same discipline as
    estimate_imports.commit_import. An order with from_estimate_id set
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

            if source_estimate and source_estimate.line_items:
                order_items = [
                    OrderItem(
                        description=li.description, category=li.category, quantity=li.quantity,
                        unit=li.unit, rate=li.rate, amount=li.amount,
                        source_estimate_item_id=li.id, sort_order=i, product_id=li.product_id,
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
                order = db.query(Order).filter(Order.id == row.matched_order_id).first()
                if not order:
                    raise ValueError("Order no longer exists")
                if order.project_status in ORDER_LOCKED_STATUSES:
                    raise ValueError(
                        f'Order {order.order_code} is "{order.project_status}" and can no longer be edited by re-import.'
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
