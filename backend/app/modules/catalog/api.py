"""Catalog domain API routes: products (products_router), product
imports (product_imports_router), rate cards (rate_cards_router),
rate-card imports (rate_card_imports_router), and Excel/PDF reports
(reports_router). Combines the former products.py, product_imports.py,
rate_cards.py, rate_card_imports.py, and reports.py."""
from typing import List, Optional
import zipfile
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role, rate_limit
from app.platform.audit import log_action
from app.platform.config import settings
from app.platform.ids import generate_unique_code, generate_business_id
from app.shared import build_workbook, xlsx_response
from app.modules.catalog.models import Product, ProductMaterial, RateCard
from app.modules.sales.models import OrderItem, EstimateLineItem
from app.modules.catalog.schemas import ProductCreate, ProductUpdate, ProductResponse
from app.modules.catalog.schemas import RateCardCreate, RateCardUpdate, RateCardOverride, RateCardResponse
from app.modules.catalog.services import generate_product_pdf
from app.modules.catalog.imports import (
    ProductImportPreviewResponse, ProductImportRowPreview,
    ProductImportCommitRequest, ProductImportCommitResult,
)
from app.modules.catalog.imports import (
    build_product_import_template as build_import_template, parse_product_uploaded_workbook as parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)
from app.modules.catalog.imports import (
    RateCardImportPreviewResponse, RateCardImportRowPreview,
    RateCardImportCommitRequest, RateCardImportCommitResult,
)
from app.modules.catalog.imports import build_rate_card_import_template as build_import_template2, parse_rate_card_uploaded_workbook as parse_uploaded_workbook2, validate_row


# --- products.py ---
products_router = APIRouter(prefix="/api/products", tags=["products"])


def _serialize_products(products, role: str):
    """Costing (every *_cost field, overhead/margin %, cost_price,
    suggested prices, margin) is financial data, same treatment as
    Material.average_rate/stock_value - genuinely nulled server-side for
    non-master roles, not merely hidden by the frontend. selling_price
    stays visible (that's the customer-facing catalog price, not an
    internal cost figure)."""
    responses = [ProductResponse.model_validate(p) for p in products]
    if role not in ("master",):
        for r in responses:
            r.material_cost = None
            r.hardware_cost = None
            r.labour_cost = None
            r.machine_cost = None
            r.finish_cost = None
            r.packing_cost = None
            r.transport_cost = None
            r.other_cost = None
            r.overhead_percent = None
            r.margin_percent = None
            r.cost_price = None
            r.suggested_cost_price = None
            r.suggested_selling_price = None
            r.margin = None
            r.actual_margin_percent = None
    return responses


def _apply_materials_used(db: Session, product: Product, materials_used):
    db.query(ProductMaterial).filter(ProductMaterial.product_id == product.id).delete()
    db.flush()
    for m in materials_used:
        db.add(ProductMaterial(
            product_id=product.id, material_id=m.material_id,
            quantity_required=m.quantity_required, unit=m.unit, notes=m.notes,
        ))


@products_router.get("/", response_model=List[ProductResponse])
def list_products(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    product_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    response: Response = None,
    limit: int = Query(500, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    query = db.query(Product).options(joinedload(Product.materials_used).joinedload(ProductMaterial.material))
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(like), Product.product_code.ilike(like),
                                  Product.business_id.ilike(like)))
    if category:
        query = query.filter(Product.category == category)
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    query = query.order_by(Product.name)
    total = query.count()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return _serialize_products(query.offset(offset).limit(limit).all(), auth.get("role", "user"))


@products_router.post("/", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, request: Request, confirm_duplicate: bool = Query(False),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    # Duplicate check (Product Master section 9): a warning, not an
    # automatic rejection - the same normalized name could legitimately
    # be two different real products (e.g. two custom one-offs that
    # happen to share a description). confirm_duplicate=true proceeds
    # anyway once the user has seen the warning and decided it's fine.
    # Duplicate check (Product Master section 9): a
    # warning, not an automatic rejection - the same normalized name could
    # legitimately be two different real products (e.g. two custom
    # one-offs that happen to share a description). confirm_duplicate=true
    # proceeds anyway once the user has seen the warning and decided it's
    # fine. Uses the same fuzzy matcher as the Product Excel importer
    # (app.modules.clients.services.find_fuzzy_name_matches) - an exact match
    # ("Custom Walk-in Wardrobe" typed twice) and a close typo ("Custom
    # Walk-in Wardrob") are both caught here, not just in Excel, so the UI
    # and the importer can never silently disagree about what counts as a
    # possible duplicate.
    if not confirm_duplicate:
        from app.modules.clients.services import find_fuzzy_name_matches
        active_products = db.query(Product).filter(Product.is_active == True).all()  # noqa: E712
        matches = find_fuzzy_name_matches(db=None, name=data.name, candidates=active_products, limit=5)
        if matches:
            raise HTTPException(status_code=409, detail={
                "warning": "Possible existing product found.",
                "matches": [{"id": p.id, "product_code": p.product_code, "name": p.name} for p in matches],
            })

    payload = data.dict(exclude={"product_code", "materials_used"})
    for _ in range(5):
        code = generate_unique_code(db, Product, "product_code", "PRD-")
        product = Product(**payload, product_code=code, business_id=generate_business_id(db))
        db.add(product)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        if data.materials_used:
            _apply_materials_used(db, product, data.materials_used)
        db.commit()
        db.refresh(product)
        log_action(db, request, user_id=auth.get("user_id"), action="create_product", module_name="products",
                   record_id=product.id, new_value={"product_code": product.product_code, "name": product.name})
        return product
    raise HTTPException(status_code=500, detail="Unable to generate a unique product code, please try again")


@products_router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    product = db.query(Product).options(joinedload(Product.materials_used).joinedload(ProductMaterial.material)).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_products([product], auth.get("role", "user"))[0]


@products_router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, data: ProductUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = data.dict(exclude_unset=True, exclude={"materials_used"})
    old_status = product.is_active
    for field, value in updates.items():
        setattr(product, field, value)
    if data.materials_used is not None:
        _apply_materials_used(db, product, data.materials_used)
    db.add(product)
    db.commit()
    db.refresh(product)

    if "is_active" in updates and updates["is_active"] != old_status:
        action = "activate_product" if product.is_active else "deactivate_product"
    else:
        action = "update_product"
    log_action(db, request, user_id=auth.get("user_id"), action=action, module_name="products",
               record_id=product.id, new_value={k: str(v) for k, v in updates.items()})
    return product


@products_router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db.query(OrderItem).filter(OrderItem.product_id == product_id).first():
        raise HTTPException(status_code=400, detail="This product has order history and cannot be deleted. Mark it inactive instead.")
    if db.query(EstimateLineItem).filter(EstimateLineItem.product_id == product_id).first():
        raise HTTPException(status_code=400, detail="This product is referenced by an estimate and cannot be deleted. Mark it inactive instead.")
    # Defect repair (F138 P2): ClientProductRate.product_id is a
    # nullable FK with no cascade/back-reference on Product - a
    # customer-specific rate override left dangling here once its
    # product no longer exists is meaningless, not preserved business
    # history (unlike OrderItem/EstimateLineItem, already blocked
    # above), so it's cleaned up rather than left orphaned.
    from app.modules.clients.models import ClientProductRate
    db.query(ClientProductRate).filter(ClientProductRate.product_id == product_id).delete()
    product_name = product.name
    db.delete(product)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_product", module_name="products",
               record_id=product_id, old_value={"name": product_name})


# --- product_imports.py ---
product_imports_router = APIRouter(prefix="/api/product-imports", tags=["product-imports"])


@product_imports_router.get("/template")
def download_product_import_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Product_Import_Template.xlsx"},
    )


@product_imports_router.post("/preview", response_model=ProductImportPreviewResponse)
def preview_product_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file only - never writes to the
    database. The user reviews this (including any flagged possible
    duplicates) and only then calls /commit."""
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
    try:
        raw_rows = parse_uploaded_workbook(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Couldn't read this file - please upload a valid .xlsx file using the downloaded template.",
        )

    existing_products = db.query(Product).filter(Product.is_active == True).all()  # noqa: E712
    existing_by_name = {normalize_match_key(p.name): p for p in existing_products}

    preview_rows = []
    new_count = 0
    duplicate_count = 0
    error_count = 0
    seen_in_file = {}
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(row, existing_by_name, fuzzy_candidates=existing_products)
        if not errors and not result["is_duplicate"]:
            match_key = normalize_match_key(result.get("name"))
            if match_key in seen_in_file:
                errors = errors + [f"Duplicate of row {seen_in_file[match_key]} in this file (same product name)"]
            else:
                seen_in_file[match_key] = idx
        if errors:
            error_count += 1
        elif result["is_duplicate"]:
            duplicate_count += 1
        else:
            new_count += 1
        preview_rows.append(ProductImportRowPreview(row_number=idx, **result, errors=errors))

    return ProductImportPreviewResponse(
        total_rows=len(raw_rows), new_rows=new_count,
        duplicate_rows=duplicate_count, error_rows=error_count, rows=preview_rows,
    )


@product_imports_router.post("/error-report")
def download_product_import_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the logic /preview
    uses) and returns a real .xlsx listing only the rejected rows,
    matching the established pattern from client_imports.py."""
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.")
    try:
        raw_rows = parse_uploaded_workbook(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Couldn't read this file - please upload a valid .xlsx file.")

    existing_products = db.query(Product).filter(Product.is_active == True).all()  # noqa: E712
    existing_by_name = {normalize_match_key(p.name): p for p in existing_products}
    error_rows = []
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(row, existing_by_name, fuzzy_candidates=existing_products)
        if errors:
            error_rows.append({
                "row": idx, "name": result.get("name") or "", "category": result.get("category") or "",
                "unit": result.get("unit") or "", "reason": "; ".join(errors),
            })

    from app.shared import build_workbook
    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Product Import Error Report",
        "subtitle": f"{len(error_rows)} of {len(raw_rows)} row(s) rejected. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["row", "name", "category", "unit", "reason"],
        "headers": ["Excel Row", "Product Name", "Category", "Unit", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Product_Import_Errors.xlsx"},
    )


@product_imports_router.post("/commit", response_model=ProductImportCommitResult)
def commit_product_import(data: ProductImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Creates a Product Master row per confirmed row that is genuinely
    new. A row carrying matched_product_id (the user resolved a possible
    match during preview as "Use Existing") is never re-created - counted
    as matched instead, exactly like the Client importer's
    matched_client_id handling. Same not-fully-atomic behavior as the
    purchase import commit: each row commits individually, and if one
    fails the response reflects exactly what succeeded before the
    failure - re-upload just the rows that didn't go through."""
    created = 0
    matched_existing = 0
    skipped = 0
    product_ids = []
    error_message = None

    for i, row in enumerate(data.rows):
        if row.skip:
            skipped += 1
            continue
        if row.matched_product_id:
            matched_existing += 1
            product_ids.append(row.matched_product_id)
            continue
        try:
            product_id = None
            for _ in range(5):
                code = generate_unique_code(db, Product, "product_code", "PRD-")
                product = Product(
                    product_code=code, business_id=generate_business_id(db),
                    name=row.name, product_type=row.product_type, category=row.category,
                    subcategory=row.subcategory, unit=row.unit, length=row.length, width=row.width,
                    height=row.height, dimension_unit=row.dimension_unit, primary_material=row.primary_material,
                    finish=row.finish, material_cost=row.material_cost, hardware_cost=row.hardware_cost,
                    labour_cost=row.labour_cost, machine_cost=row.machine_cost, finish_cost=row.finish_cost,
                    packing_cost=row.packing_cost, transport_cost=row.transport_cost, other_cost=row.other_cost,
                    overhead_percent=row.overhead_percent, margin_percent=row.margin_percent,
                    cost_price=row.cost_price, selling_price=row.selling_price, notes=row.notes,
                )
                db.add(product)
                try:
                    db.flush()
                    product_id = product.id
                    break
                except Exception:
                    db.rollback()
            if product_id is None:
                raise ValueError("Could not generate a unique product code")
            db.commit()
            created += 1
            product_ids.append(product_id)
        except (ValueError, HTTPException) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_message = f"Stopped at row {i + 1}: {detail}"
            break

    log_action(
        db, request, user_id=auth.get("user_id"), action="import_products", module_name="products",
        new_value={"created": created, "matched_existing": matched_existing, "skipped": skipped},
    )

    return ProductImportCommitResult(
        created_products=created, matched_existing=matched_existing, skipped=skipped,
        product_ids=product_ids, error=error_message,
    )


# --- rate_cards.py ---
rate_cards_router = APIRouter(prefix="/api/rate-cards", tags=["rate-cards"])


@rate_cards_router.get("/", response_model=List[RateCardResponse])
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


@rate_cards_router.get("/{rate_id}", response_model=RateCardResponse)
def get_rate_card(rate_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    rate = db.query(RateCard).filter(RateCard.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    return rate


@rate_cards_router.get("/{rate_id}/history", response_model=List[RateCardResponse])
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


@rate_cards_router.post("/", response_model=RateCardResponse, status_code=201)
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


@rate_cards_router.put("/{rate_id}", response_model=RateCardResponse)
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


@rate_cards_router.post("/{rate_id}/override", response_model=RateCardResponse)
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


@rate_cards_router.post("/{rate_id}/deactivate", response_model=RateCardResponse)
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


# --- rate_card_imports.py ---
rate_card_imports_router = APIRouter(prefix="/api/rate-card-imports", tags=["rate-card-imports"])


@rate_card_imports_router.get("/template")
def download_rate_card_import_template(auth=Depends(require_role("master"))):
    buffer = build_import_template2()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Rate_Master_Import_Template.xlsx"},
    )


@rate_card_imports_router.post("/preview", response_model=RateCardImportPreviewResponse)
def preview_rate_card_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    if file.content_type != "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400,
                                 detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.")
    try:
        raw_rows = parse_uploaded_workbook2(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400,
                             detail="Couldn't read this file - please upload a valid .xlsx using the downloaded template.")

    existing_by_code = {r.rate_code.upper(): r for r in db.query(RateCard).filter(RateCard.is_active == True).all()}  # noqa: E712

    preview_rows, new_count, update_count, error_count = [], 0, 0, 0
    for idx, row in enumerate(raw_rows, start=1):
        result, errors, is_update = validate_row(row, existing_by_code)
        if errors:
            error_count += 1
        elif is_update:
            update_count += 1
        else:
            new_count += 1
        preview_rows.append(RateCardImportRowPreview(row_number=idx, **result, is_update=is_update, errors=errors))

    return RateCardImportPreviewResponse(
        total_rows=len(raw_rows), new_rows=new_count, update_rows=update_count,
        error_rows=error_count, rows=preview_rows,
    )


@rate_card_imports_router.post("/error-report")
def download_rate_card_import_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the logic /preview
    uses) and returns a real .xlsx listing only the rejected rows,
    matching the established pattern from client_imports.py."""
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.")
    try:
        raw_rows = parse_uploaded_workbook2(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Couldn't read this file - please upload a valid .xlsx file.")

    existing_by_code = {r.rate_code.upper(): r for r in db.query(RateCard).filter(RateCard.is_active == True).all()}  # noqa: E712
    error_rows = []
    for idx, row in enumerate(raw_rows, start=1):
        result, errors, is_update = validate_row(row, existing_by_code)
        if errors:
            error_rows.append({
                "row": idx, "item_name": result.get("item_name") or "", "category": result.get("category") or "",
                "uom": result.get("uom") or "", "reason": "; ".join(errors),
            })

    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Rate Master Import Error Report",
        "subtitle": f"{len(error_rows)} of {len(raw_rows)} row(s) rejected. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["row", "item_name", "category", "uom", "reason"],
        "headers": ["Excel Row", "Item Name", "Category", "UOM", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Rate_Master_Import_Errors.xlsx"},
    )


@rate_card_imports_router.post("/commit", response_model=RateCardImportCommitResult)
def commit_rate_card_import(data: RateCardImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Every row - new or update - goes through the same
    create-new-version discipline as the UI: an update never mutates
    the matched row's price fields, it deactivates that row and
    creates a new one that supersedes it."""
    from datetime import datetime
    created = updated = skipped = 0
    rate_ids = []
    error_message = None

    for i, row in enumerate(data.rows):
        if row.skip:
            skipped += 1
            continue
        try:
            payload = row.dict(exclude={"matched_rate_id", "skip"})
            old = None
            if row.matched_rate_id:
                old = db.query(RateCard).filter(RateCard.id == row.matched_rate_id).first()
                if not old:
                    raise ValueError(f"Rate {row.matched_rate_id} not found")
                old.is_active = False
                old.effective_to = datetime.utcnow()
                db.add(old)

            rate_id = None
            for _ in range(5):
                code = generate_unique_code(db, RateCard, "rate_code", "RATE-")
                rate = RateCard(**payload, rate_code=code, business_id=generate_business_id(db),
                                 effective_from=datetime.utcnow(), is_active=True,
                                 supersedes_id=old.id if old else None)
                db.add(rate)
                try:
                    db.flush()
                    rate_id = rate.id
                    break
                except Exception:
                    db.rollback()
            if rate_id is None:
                raise ValueError("Could not generate a unique rate code")
            db.commit()
            rate_ids.append(rate_id)
            if old:
                updated += 1
            else:
                created += 1
        except (ValueError, HTTPException) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_message = f"Stopped at row {i + 1}: {detail}"
            break

    log_action(db, request, user_id=auth.get("user_id"), action="import_rate_cards", module_name="rate_cards",
               new_value={"created": created, "updated": updated, "skipped": skipped, "error": error_message})
    return RateCardImportCommitResult(created=created, updated=updated, skipped=skipped,
                                       rate_ids=rate_ids, error=error_message)


# --- reports.py ---
"""Catalog-domain report exports: product export and product PDF.
Split out of the former monolithic reports.py - see
modules/inventory/api/reports.py's docstring for why."""

reports_router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@reports_router.get("/products.xlsx")
def export_products(
    search: Optional[str] = Query(None), category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Product Master export. search/category/
    is_active mirror GET /api/products/ exactly, so the export matches
    whatever the person is currently looking at on the Products list."""
    from app.modules.catalog.models import Product

    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Product)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(like), Product.product_code.ilike(like),
                                  Product.business_id.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if category:
        query = query.filter(Product.category == category)
        filters_applied.append(f"Category: {category}")
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
        filters_applied.append(f"Status: {'Active' if is_active else 'Inactive'}")

    products = query.order_by(Product.name).all()
    rows = []
    for p in products:
        row = {
            "product_id": p.business_id or "", "product_code": p.product_code, "name": p.name,
            "type": p.product_type, "category": p.category or "", "subcategory": p.subcategory or "",
            "unit": p.unit, "selling_price": float(p.selling_price) if p.selling_price is not None else None,
            "gst_percent": float(p.gst_percent) if p.gst_percent is not None else None,
            "status": "Active" if p.is_active else "Inactive",
        }
        if is_privileged:
            row["cost_price"] = float(p.cost_price) if p.cost_price is not None else None
            row["margin"] = p.margin
        rows.append(row)

    columns = ["product_id", "product_code", "name", "type", "category", "subcategory", "unit",
               "selling_price", "gst_percent", "status"]
    headers = ["Product ID", "Product Code", "Product Name", "Type", "Category", "Subcategory", "Unit",
               "Default Rate", "GST %", "Status"]
    if is_privileged:
        columns += ["cost_price", "margin"]
        headers += ["Cost Price", "Margin"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Products", "title": "PRODUCT MASTER",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": [("Total Products", str(len(products)))],
    }])
    filename = f"product_master_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/products/{product_id}/product.pdf")
def export_product_pdf(product_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    from app.modules.catalog.models import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    buffer = generate_product_pdf(product)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="product-{product.product_code}.pdf"', "Cache-Control": "no-store, private"},
    )
