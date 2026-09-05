from decimal import Decimal
import zipfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.responses import StreamingResponse

from app.platform.database.database import get_db
from app.platform.configuration.config import settings
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action
from app.modules.clients.models import Client
from app.modules.catalog.models import Product
from app.modules.sales.models import Estimate, EstimateLineItem, Order
from app.platform.database.id_generator import generate_unique_code, generate_business_id
from app.modules.sales.calculations import compute_totals
from app.modules.sales.status_rules import ESTIMATE_FINALIZED_STATUSES
from app.modules.sales.imports.estimate_import import (
    build_import_template, parse_uploaded_workbook,
    validate_header_row, validate_item_row, normalize_match_key, normalize_phone_key,
)
from app.modules.sales.imports.estimate_schemas import (
    EstimateImportPreviewResponse, EstimateImportHeaderPreview, EstimateImportItemPreview,
    EstimateImportCommitRequest, EstimateImportCommitResult, EstimateImportCommitResultRow,
)

router = APIRouter(prefix="/api/estimate-imports", tags=["estimate-imports"])


@router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Estimate_Import_Template.xlsx"},
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


@router.post("/preview", response_model=EstimateImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates both sheets, matches Estimate ID / Client /
    Product ID against real records, and groups item rows under their
    header row by Estimate Row #. Never writes to the database - see
    module docstring in app/modules/sales/imports/estimate_import.py."""
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
        result, errors = validate_header_row(row, idx, db, estimates_by_code, clients_by_key)
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
        result, errors = validate_item_row(row, idx, products_by_code)
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


@router.post("/error-report")
def download_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the header+item
    grouping logic /preview uses) and returns a real .xlsx listing
    every rejected header row and every rejected item row, each
    labeled with its source sheet so a person can find and fix it -
    matching the established pattern from client_imports.py (Section
    23), adapted for this import's two-sheet structure."""
    file_bytes = _read_upload(file)
    try:
        raw_headers, raw_items = parse_uploaded_workbook(file_bytes)
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
        result, errors = validate_header_row(row, idx, db, estimates_by_code, clients_by_key)
        if errors:
            error_rows.append({
                "sheet": "Estimate Header", "row": idx, "reference": result.get("client_name") or "",
                "reason": "; ".join(errors),
            })
    for idx, row in enumerate(raw_items, start=1):
        result, errors = validate_item_row(row, idx, products_by_code)
        if errors:
            error_rows.append({
                "sheet": "Estimate Items", "row": idx, "reference": result.get("description") or "",
                "reason": "; ".join(errors),
            })

    from app.shared.exporters import build_workbook
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


@router.post("/commit", response_model=EstimateImportCommitResult)
def commit_import(data: EstimateImportCommitRequest, request: Request, db: Session = Depends(get_db),
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
