"""Inventory domain API routes: materials, material categories,
material imports, locations, stock transactions, and exports.
Combines the former materials.py, material_categories.py,
material_imports.py, locations.py, stock_transactions.py, and
reports.py."""
from typing import List, Optional
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from app.platform.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.modules.inventory.models import Material, MaterialSubcategory, MaterialAttributeValue, Location
from app.modules.procurement.models import Purchase
from app.modules.operations.models import Issue
from app.modules.inventory.schemas import MaterialCreate, MaterialUpdate, MaterialResponse, MaterialNameInterpretResponse
from app.modules.inventory.schemas import DeadStockItem, DeadStockMatch, DeadStockMatchesResponse
from app.modules.inventory.imports import interpret_material_name
from app.platform.ids import generate_unique_code, generate_business_id
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from app.modules.inventory.models import MaterialCategory, MaterialSubcategory, MaterialAttributeDefinition
from app.modules.inventory.schemas import MaterialCategoryCreate, MaterialCategoryResponse, MaterialCategoryWithSubcategories, MaterialSubcategoryCreate, MaterialSubcategoryResponse, MaterialAttributeDefinitionCreate, MaterialAttributeDefinitionResponse
from app.platform.ids import generate_business_id
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from fastapi.responses import StreamingResponse
from app.platform.config import settings
from app.platform.security import require_role
from app.modules.inventory.models import Material, MaterialCategory, MaterialSubcategory, Location
from app.modules.procurement.models import Supplier
from app.modules.inventory.imports import (
    MaterialImportPreviewResponse, MaterialImportRowPreview,
    MaterialImportCommitRequest, MaterialImportCommitResult,
)
from app.modules.inventory.imports import (
    build_import_template, parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from app.modules.inventory.models import Location
from app.modules.inventory.schemas import LocationCreate, LocationResponse, LocationTreeResponse
from fastapi import APIRouter, Depends, Query
from app.modules.inventory.models import StockTransfer, StockAdjustment, StockLedgerEntry
from app.modules.inventory.schemas import StockTransferCreate, StockTransferResponse, StockAdjustmentCreate, StockAdjustmentResponse, MaterialLocationStockResponse
from app.modules.inventory.schemas import StockLedgerEntryResponse
from app.modules.inventory.services import StockService
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from app.platform.security import rate_limit
from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase, Supplier
from app.shared import build_workbook, xlsx_response


# --- materials.py ---
def _serialize_materials(materials, role: str):
    """Employees can see stock quantities/status/material info, but not
    financial data (average_rate, stock_value) - genuinely nulled here,
    server-side, before the response is built, not merely hidden by the
    frontend. Master accounts get the real figures unchanged."""
    responses = [MaterialResponse.model_validate(m) for m in materials]
    if role not in ("master",):
        for r in responses:
            r.average_rate = None
            r.stock_value = None
    return responses


materials_router = APIRouter(prefix="/api/materials", tags=["materials"])


def _try_decimal(value):
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@materials_router.get("/", response_model=List[MaterialResponse])
def list_materials(response: Response, category: Optional[str] = Query(None), search: Optional[str] = Query(None),
                    low_stock_only: bool = Query(False), active_only: bool = Query(False),
                    subcategory_id: Optional[int] = Query(None),
                    attribute_filters: Optional[str] = Query(
                        None, description='JSON object mapping attribute_definition_id to the desired value, '
                                           'e.g. {"5": "18", "7": "White"} - matched against either the numeric '
                                           'or text value depending on the attribute\'s own data type.'),
                    limit: int = Query(500, ge=1, le=500),
                    offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Material)
    if category:
        query = query.filter(Material.category == category)
    if subcategory_id:
        query = query.filter(Material.subcategory_id == subcategory_id)
    if active_only:
        query = query.filter(Material.is_active.is_(True))
    if search:
        like = f"%{search}%"
        query = query.filter((Material.name.ilike(like)) | (Material.material_code.ilike(like)))
    if low_stock_only:
        # Was previously filtered in Python after fetching everything -
        # moved into SQL so it composes correctly with pagination below
        # (filtering after paginating would silently return wrong pages).
        query = query.filter(Material.current_stock <= Material.minimum_stock)
    if attribute_filters:
        try:
            filters = json.loads(attribute_filters)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="attribute_filters must be a valid JSON object")
        for attr_def_id_str, desired_value in filters.items():
            try:
                attr_def_id = int(attr_def_id_str)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid attribute_definition_id: {attr_def_id_str}")
            numeric_value = _try_decimal(desired_value)
            match_conditions = [MaterialAttributeValue.value_text == str(desired_value)]
            if numeric_value is not None:
                match_conditions.append(MaterialAttributeValue.value_number == numeric_value)
            matching_material_ids = db.query(MaterialAttributeValue.material_id).filter(
                MaterialAttributeValue.attribute_definition_id == attr_def_id,
                or_(*match_conditions),
            )
            # Each attribute filter narrows the result further (AND
            # across filters) - a material must match every selected
            # attribute value, not just any one of them.
            query = query.filter(Material.id.in_(matching_material_ids))

    query = query.order_by(Material.name)
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    return _serialize_materials(query.offset(offset).limit(limit).all(), auth.get("role", "user"))


def _serialize_material(material, role: str):
    return _serialize_materials([material], role)[0]


def _resolve_category_name(db: Session, subcategory_id):
    """The legacy category string stays in sync with the subcategory's
    parent category name whenever subcategory_id is set - this is what
    keeps every existing consumer (dashboard, chatbot, PDF/Excel,
    low-stock filtering) correct without needing to touch them."""
    if not subcategory_id:
        return None
    subcategory = db.query(MaterialSubcategory).filter(MaterialSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return subcategory.category.name


def _resolve_location_path(db: Session, location_id):
    """Same sync pattern as category - the legacy location string stays
    in sync with the new Location's full_path whenever location_id is set."""
    if not location_id:
        return None
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location.full_path


def _apply_attribute_values(db: Session, material: Material, attribute_values):
    """Replaces the material's full attribute value set - matching the
    same "submit the current complete list" semantics already used for
    estimate/order line items, not an incremental patch."""
    for existing in list(material.attribute_values):
        db.delete(existing)
    db.flush()
    for item in attribute_values:
        db.add(MaterialAttributeValue(
            material_id=material.id, attribute_definition_id=item.attribute_definition_id,
            value_text=item.value_text, value_number=item.value_number,
        ))


@materials_router.get("/interpret-name", response_model=MaterialNameInterpretResponse)
def interpret_name(name: str = Query(..., min_length=1), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    """Material name -> suggested thickness/category/subcategory, for the
    material creation form's "intelligent defaults" - typing "HDHMR 6mm"
    suggests a category if one genuinely matches; never a guess dressed
    up as a fact (confidence "none" means the form shows nothing)."""
    return interpret_material_name(db, name)


@materials_router.get("/dead-stock-matches", response_model=DeadStockMatchesResponse)
def get_dead_stock_matches(
    idle_days: int = Query(90, ge=1, description="A material with no stock movement in at least this many days counts as idle."),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Family 137, feature 7 - Dead-Stock / Material-to-Design Matching.

    Finds materials with real stock on hand that haven't moved
    (no Receipt/Issue/Adjustment/Transfer ledger entry) in at least
    idle_days, and cross-checks them against line items on estimates
    that are still open (draft/sent - not yet accepted, converted, or
    rejected) whose category matches the idle material's category, so
    a design already being quoted might genuinely be able to use this
    stock instead of buying fresh material.

    This is read-only and purely informational - it never allocates,
    reserves, or moves any material. The human reviews the matches and
    decides whether to actually use the stock, the same DATA ->
    INSIGHT -> OPTIONS -> HUMAN DECISION shape as every other Family
    137 intelligence feature."""
    from app.modules.sales.models import Estimate, EstimateLineItem
    from app.modules.catalog.models import Product

    cutoff = datetime.utcnow() - timedelta(days=idle_days)

    candidates = db.query(Material).filter(Material.current_stock > 0, Material.is_active.is_(True)).all()
    if not candidates:
        return DeadStockMatchesResponse(idle_threshold_days=idle_days, items=[])

    material_ids = [m.id for m in candidates]
    # Most recent ledger entry per material, in one query rather than
    # one-query-per-material.
    latest_entries = dict(
        db.query(StockLedgerEntry.material_id, func.max(StockLedgerEntry.created_at))
        .filter(StockLedgerEntry.material_id.in_(material_ids))
        .group_by(StockLedgerEntry.material_id)
        .all()
    )

    # Open (still-quotable) estimates only - an accepted/converted or
    # rejected estimate is no longer a real opportunity to redirect
    # material toward.
    open_line_items = (
        db.query(EstimateLineItem, Estimate, Product)
        .join(Estimate, EstimateLineItem.estimate_id == Estimate.id)
        .outerjoin(Product, EstimateLineItem.product_id == Product.id)
        .filter(Estimate.status.in_(["draft", "sent"]))
        .all()
    )

    items = []
    for material in candidates:
        last_movement = latest_entries.get(material.id) or material.created_at
        idle_since = last_movement
        actual_idle_days = (datetime.utcnow() - idle_since).days
        if actual_idle_days < idle_days:
            continue
        if not material.category:
            continue

        matches = []
        seen_estimates = set()
        for line_item, estimate, product in open_line_items:
            product_category = (product.subcategory or product.category) if product else None
            if not product_category or product_category != material.category:
                continue
            if estimate.id in seen_estimates:
                continue
            seen_estimates.add(estimate.id)
            matches.append(DeadStockMatch(
                estimate_id=estimate.id, estimate_code=estimate.estimate_code,
                client_name=estimate.client.name if estimate.client else None,
                line_item_description=line_item.description, line_item_quantity=line_item.quantity,
            ))

        if not matches:
            continue  # idle, but nothing currently open could use it - not worth surfacing

        items.append(DeadStockItem(
            material_id=material.id, material_name=material.name, category=material.category,
            idle_days=actual_idle_days, quantity=material.current_stock, unit=material.unit,
            location=material.location, average_rate=material.average_rate,
            estimated_value=(material.current_stock * material.average_rate).quantize(Decimal("0.01")),
            potential_matches=matches[:5],
        ))

    items.sort(key=lambda i: i.estimated_value, reverse=True)
    return DeadStockMatchesResponse(idle_threshold_days=idle_days, items=items)


@materials_router.post("/", response_model=MaterialResponse, status_code=201)
def create_material(data: MaterialCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"material_code", "attribute_values"})
    payload["current_stock"] = payload["opening_stock"]
    # Snapshotted once, now - never implicitly re-derived from
    # location_id later, since location_id can be edited afterwards and
    # opening_stock's original location must not drift with it.
    payload["opening_stock_location_id"] = data.location_id
    if data.subcategory_id:
        payload["category"] = _resolve_category_name(db, data.subcategory_id)
    if data.location_id:
        payload["location"] = _resolve_location_path(db, data.location_id)

    for _ in range(5):
        code = generate_unique_code(db, Material, "material_code", "MAT-")
        material = Material(**payload, material_code=code, business_id=generate_business_id(db))
        db.add(material)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        if data.attribute_values:
            _apply_attribute_values(db, material, data.attribute_values)
        db.commit()
        db.refresh(material)
        return material
    raise HTTPException(status_code=500, detail="Unable to generate a unique material code, please try again")


@materials_router.get("/{material_id}", response_model=MaterialResponse)
def get_material(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return _serialize_material(material, auth.get("role", "user"))


@materials_router.put("/{material_id}", response_model=MaterialResponse)
def update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    update_data = data.dict(exclude_unset=True, exclude={"attribute_values"})
    if "subcategory_id" in update_data:
        update_data["category"] = _resolve_category_name(db, update_data["subcategory_id"])
    if "location_id" in update_data:
        update_data["location"] = _resolve_location_path(db, update_data["location_id"])
        # opening_stock_location_id is set once at creation (see
        # create_material) and normally never touched again - a
        # material genuinely moved after its opening stock already had
        # a real ledger history should NOT have that history's
        # location silently rewritten. But a material created with NO
        # location at all leaves opening_stock permanently unlocated:
        # _location_balance can never find it at any location (it only
        # ever counts opening_stock where opening_stock_location_id
        # matches), so a location-specific adjustment/issue/transfer
        # against genuinely-available opening stock is wrongly
        # rejected forever, with no way to fix it - exactly the "shows
        # 10 available but every location shows 0" bug this closes.
        # Only ever fills in a currently-missing value, never
        # overwrites an already-set one.
        if material.opening_stock_location_id is None:
            update_data["opening_stock_location_id"] = update_data["location_id"]
    for field, value in update_data.items():
        setattr(material, field, value)

    if data.attribute_values is not None:
        _apply_attribute_values(db, material, data.attribute_values)

    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@materials_router.delete("/{material_id}", status_code=204)
def delete_material(material_id: int, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    if db.query(Purchase).filter(Purchase.material_id == material_id).first():
        raise HTTPException(status_code=400, detail="This material has purchase history and cannot be deleted. Mark it inactive instead.")
    if db.query(Issue).filter(Issue.material_id == material_id).first():
        raise HTTPException(status_code=400, detail="This material has issue history and cannot be deleted. Mark it inactive instead.")
    material_name = material.name
    db.delete(material)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_material", module_name="materials",
               record_id=material_id, old_value={"name": material_name})


# --- material_categories.py ---
material_categories_router = APIRouter(prefix="/api/material-categories", tags=["material-categories"])


@material_categories_router.get("/", response_model=List[MaterialCategoryWithSubcategories])
def list_categories(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    return db.query(MaterialCategory).order_by(MaterialCategory.name).all()


@material_categories_router.post("/", response_model=MaterialCategoryResponse, status_code=201)
def create_category(data: MaterialCategoryCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    if db.query(MaterialCategory).filter(MaterialCategory.name == data.name).first():
        raise HTTPException(status_code=400, detail=f'A category named "{data.name}" already exists.')
    category = MaterialCategory(**data.dict(), business_id=generate_business_id(db))
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'A category named "{data.name}" already exists.')
    db.refresh(category)
    return category


@material_categories_router.post("/subcategories", response_model=MaterialSubcategoryResponse, status_code=201)
def create_subcategory(data: MaterialSubcategoryCreate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    category = db.query(MaterialCategory).filter(MaterialCategory.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if db.query(MaterialSubcategory).filter(
        MaterialSubcategory.category_id == data.category_id, MaterialSubcategory.name == data.name
    ).first():
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under {category.name}.')

    subcategory = MaterialSubcategory(**data.dict(), business_id=generate_business_id(db))
    db.add(subcategory)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under {category.name}.')
    db.refresh(subcategory)
    return subcategory


@material_categories_router.get("/subcategories/{subcategory_id}", response_model=MaterialSubcategoryResponse)
def get_subcategory(subcategory_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    subcategory = db.query(MaterialSubcategory).filter(MaterialSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return subcategory


@material_categories_router.post("/subcategories/{subcategory_id}/attributes",
             response_model=MaterialAttributeDefinitionResponse, status_code=201)
def create_attribute_definition(subcategory_id: int, data: MaterialAttributeDefinitionCreate,
                                 db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Defines a specification field for this subcategory - e.g. adding
    "Voltage" (number, unit "V") to a new "LED Strip" subcategory. Every
    material later created under this subcategory can then have a real
    value for it, filterable via value_number, not a free-text guess."""
    subcategory = db.query(MaterialSubcategory).filter(MaterialSubcategory.id == subcategory_id).first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    if db.query(MaterialAttributeDefinition).filter(
        MaterialAttributeDefinition.subcategory_id == subcategory_id, MaterialAttributeDefinition.name == data.name
    ).first():
        raise HTTPException(status_code=400, detail=f'An attribute named "{data.name}" already exists here.')

    definition = MaterialAttributeDefinition(subcategory_id=subcategory_id, **data.dict())
    db.add(definition)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'An attribute named "{data.name}" already exists here.')
    db.refresh(definition)
    return definition


# --- material_imports.py ---
material_imports_router = APIRouter(prefix="/api/material-imports", tags=["material-imports"])


@material_imports_router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Material_Import_Template.xlsx"},
    )


@material_imports_router.post("/preview", response_model=MaterialImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file only - never writes to the
    database. The user reviews this (including any flagged possible
    duplicates, and any Subcategory/Supplier/Location name that didn't
    resolve to an existing record) and only then calls /commit."""
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

    existing_materials = db.query(Material).all()
    existing_by_name = {normalize_match_key(m.name): m for m in existing_materials}
    categories_by_name = {normalize_match_key(c.name): c for c in db.query(MaterialCategory).all()}
    subcategories_by_name = {normalize_match_key(s.name): s for s in db.query(MaterialSubcategory).all()}
    suppliers_by_name = {normalize_match_key(s.name): s for s in db.query(Supplier).all()}
    locations_by_name = {normalize_match_key(l.name): l for l in db.query(Location).all()}

    preview_rows = []
    new_count = 0
    duplicate_count = 0
    error_count = 0
    seen_in_file = {}
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(
            row, existing_by_name, categories_by_name, subcategories_by_name,
            suppliers_by_name, locations_by_name, fuzzy_candidates=existing_materials,
        )
        if not errors and not result["is_duplicate"]:
            match_key = normalize_match_key(result.get("name"))
            if match_key in seen_in_file:
                errors = errors + [f"Duplicate of row {seen_in_file[match_key]} in this file (same material name)"]
            else:
                seen_in_file[match_key] = idx
        if errors:
            error_count += 1
        elif result["is_duplicate"]:
            duplicate_count += 1
        else:
            new_count += 1
        preview_rows.append(MaterialImportRowPreview(row_number=idx, **result, errors=errors))

    return MaterialImportPreviewResponse(
        total_rows=len(raw_rows), new_rows=new_count,
        duplicate_rows=duplicate_count, error_rows=error_count, rows=preview_rows,
    )


@material_imports_router.post("/error-report")
def download_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
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

    existing_materials = db.query(Material).all()
    existing_by_name = {normalize_match_key(m.name): m for m in existing_materials}
    categories_by_name = {normalize_match_key(c.name): c for c in db.query(MaterialCategory).all()}
    subcategories_by_name = {normalize_match_key(s.name): s for s in db.query(MaterialSubcategory).all()}
    suppliers_by_name = {normalize_match_key(s.name): s for s in db.query(Supplier).all()}
    locations_by_name = {normalize_match_key(l.name): l for l in db.query(Location).all()}

    error_rows = []
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(
            row, existing_by_name, categories_by_name, subcategories_by_name,
            suppliers_by_name, locations_by_name, fuzzy_candidates=existing_materials,
        )
        if errors:
            error_rows.append({
                "row": idx, "name": result.get("name") or "", "category": result.get("category") or "",
                "unit": result.get("unit") or "", "reason": "; ".join(errors),
            })

    from app.shared import build_workbook
    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Material Import Error Report",
        "subtitle": f"{len(error_rows)} of {len(raw_rows)} row(s) rejected. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["row", "name", "category", "unit", "reason"],
        "headers": ["Excel Row", "Material Name", "Category", "Unit", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Material_Import_Errors.xlsx"},
    )


@material_imports_router.post("/commit", response_model=MaterialImportCommitResult)
def commit_import(data: MaterialImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Creates a Material Master row per confirmed row that is genuinely
    new. A row carrying matched_material_id (the user resolved a
    possible match during preview as "Use Existing") is never
    re-created - counted as matched instead, exactly like the Product
    importer's matched_product_id handling. Same not-fully-atomic
    behavior as the other importers: each row commits individually, and
    if one fails the response reflects exactly what succeeded before
    the failure - re-upload just the rows that didn't go through."""
    created = 0
    matched_existing = 0
    skipped = 0
    material_ids = []
    error_message = None

    # Batch every needed Location once instead of querying by id for
    # each row inside the loop below - a large import previously ran
    # one Location lookup per row (up to 5x if a material_code
    # collision forced a retry).
    needed_location_ids = {row.location_id for row in data.rows if row.location_id}
    locations_by_id = {
        l.id: l for l in db.query(Location).filter(Location.id.in_(needed_location_ids)).all()
    } if needed_location_ids else {}

    for i, row in enumerate(data.rows):
        if row.skip:
            skipped += 1
            continue
        if row.matched_material_id:
            matched_existing += 1
            material_ids.append(row.matched_material_id)
            continue
        try:
            material_id = None
            for _ in range(5):
                code = generate_unique_code(db, Material, "material_code", "MAT-")
                # Same sync pattern as create_material (materials.py): the
                # legacy `location` string stays in sync with the
                # resolved Location's full_path whenever location_id is
                # set - left unset here before this fix, so an imported
                # material's legacy location string silently stayed
                # blank even though location_id was populated.
                location = locations_by_id.get(row.location_id) if row.location_id else None
                location_path = location.full_path if location else None
                material = Material(
                    material_code=code, business_id=generate_business_id(db),
                    name=row.name, category=row.category, subcategory_id=row.subcategory_id,
                    brand_grade=row.brand_grade, thickness_size=row.thickness_size, unit=row.unit,
                    opening_stock=row.opening_stock, current_stock=row.opening_stock,
                    minimum_stock=row.minimum_stock, supplier_id=row.supplier_id,
                    location=location_path,
                    # Snapshotted once at creation, same as the regular (non-import)
                    # create_material route - never implicitly re-derived from
                    # location_id later, since location_id can be edited afterwards
                    # and opening_stock's original location must not drift with it.
                    # See migration 0061.
                    location_id=row.location_id, opening_stock_location_id=row.location_id,
                    is_active=row.is_active,
                )
                db.add(material)
                try:
                    db.flush()
                    material_id = material.id
                    break
                except Exception:
                    db.rollback()
            if material_id is None:
                raise ValueError("Could not generate a unique material code")
            db.commit()
            created += 1
            material_ids.append(material_id)
        except (ValueError, HTTPException) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_message = f"Stopped at row {i + 1}: {detail}"
            break

    log_action(
        db, request, user_id=auth.get("user_id"), action="import_materials", module_name="materials",
        new_value={"created": created, "matched_existing": matched_existing, "skipped": skipped},
    )

    return MaterialImportCommitResult(
        created_materials=created, matched_existing=matched_existing, skipped=skipped,
        material_ids=material_ids, error=error_message,
    )


# --- locations.py ---
locations_router = APIRouter(prefix="/api/locations", tags=["locations"])


@locations_router.get("/", response_model=List[LocationResponse])
def list_locations(parent_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    """Flat list, optionally filtered to one parent's direct children -
    what a "choose a location" dropdown actually needs. Use /tree for
    the full nested structure."""
    query = db.query(Location)
    if parent_id is not None:
        query = query.filter(Location.parent_id == parent_id)
    return query.order_by(Location.name).all()


@locations_router.get("/tree", response_model=List[LocationTreeResponse])
def get_location_tree(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Every top-level location (no parent) with its full descendant
    tree nested inside - what the warehouse browser view needs."""
    return db.query(Location).filter(Location.parent_id.is_(None)).order_by(Location.name).all()


@locations_router.post("/", response_model=LocationResponse, status_code=201)
def create_location(data: LocationCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    if data.parent_id is not None:
        if not db.query(Location).filter(Location.id == data.parent_id).first():
            raise HTTPException(status_code=404, detail="Parent location not found")
    if db.query(Location).filter(Location.parent_id == data.parent_id, Location.name == data.name).first():
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under this parent.')

    location = Location(**data.dict(), business_id=generate_business_id(db))
    db.add(location)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f'"{data.name}" already exists under this parent.')
    db.refresh(location)
    return location


@locations_router.get("/{location_id}", response_model=LocationResponse)
def get_location(location_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


# --- stock_transactions.py ---
stock_transactions_router = APIRouter(prefix="/api/stock", tags=["stock-transactions"])


@stock_transactions_router.post("/transfers", response_model=StockTransferResponse, status_code=201)
def create_transfer(data: StockTransferCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    return StockService.record_transfer(db, data)


@stock_transactions_router.get("/transfers", response_model=List[StockTransferResponse])
def list_transfers(material_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(StockTransfer)
    if material_id:
        query = query.filter(StockTransfer.material_id == material_id)
    return query.order_by(StockTransfer.created_at.desc()).limit(100).all()


@stock_transactions_router.post("/adjustments", response_model=StockAdjustmentResponse, status_code=201)
def create_adjustment(data: StockAdjustmentCreate, db: Session = Depends(get_db),
                       auth=Depends(require_role("master"))):
    return StockService.record_adjustment(db, data)


@stock_transactions_router.get("/adjustments", response_model=List[StockAdjustmentResponse])
def list_adjustments(material_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                      auth=Depends(get_current_user)):
    query = db.query(StockAdjustment)
    if material_id:
        query = query.filter(StockAdjustment.material_id == material_id)
    return query.order_by(StockAdjustment.created_at.desc()).limit(100).all()


@stock_transactions_router.get("/ledger", response_model=List[StockLedgerEntryResponse])
def list_ledger_entries(material_id: int = Query(...), db: Session = Depends(get_db),
                         auth=Depends(get_current_user)):
    """The real, immutable transaction history for a material - every
    Receipt/Issue/Adjustment that has ever affected its stock, in
    order, each traceable back to the actual Purchase/Issue/
    StockAdjustment record that caused it."""
    return db.query(StockLedgerEntry).filter(
        StockLedgerEntry.material_id == material_id
    ).order_by(StockLedgerEntry.created_at.asc()).all()


@stock_transactions_router.get("/locations/{material_id}", response_model=MaterialLocationStockResponse)
def get_material_location_stock(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The genuine per-location breakdown for one material - e.g.
    Rack A2 -> 12, Rack B1 -> 6, Total -> 18 - derived from the ledger,
    never a second stored total."""
    return StockService.get_location_balances(db, material_id)


@stock_transactions_router.get("/verify/{material_id}")
def verify_stock(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Proves whether Material.current_stock genuinely reconciles with
    the ledger (opening_stock + every ledger entry) - the actual
    verification this architecture is built to support."""
    return StockService.verify_stock_matches_ledger(db, material_id)


# --- reports.py ---
"""Inventory-domain report exports: purchases, material issues,
suppliers, materials, and the combined stock dashboard. Split out of
the former monolithic reports.py, which mixed every domain's exports
(inventory, sales, HR, operations, clients, catalog) into one 1350-line
file grouped by "this is a report" rather than by actual product
domain."""

reports_router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@reports_router.get("/purchases.xlsx")
def export_purchases(db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    purchases = db.query(Purchase).options(
        selectinload(Purchase.supplier), selectinload(Purchase.material)
    ).order_by(Purchase.date.desc()).all()
    rows = [{
        "purchase_code": p.purchase_code, "business_id": p.business_id or "",
        "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "supplier": p.supplier.name if p.supplier else "", "material": p.material.name if p.material else "",
        "quantity": float(p.quantity), "unit": p.unit, "rate": float(p.rate),
        "taxable_value": float(p.taxable_value), "gst_percent": float(p.gst_percent),
        "gst_amount": float(p.gst_amount), "invoice_total": float(p.invoice_total),
        "payment_status": p.payment_status,
    } for p in purchases]
    columns = ["purchase_code", "business_id", "date", "supplier", "material", "quantity", "unit", "rate",
               "taxable_value", "gst_percent", "gst_amount", "invoice_total", "payment_status"]
    headers = ["Purchase ID", "Business ID", "Date", "Supplier", "Material", "Quantity", "Unit", "Rate",
               "Taxable Value", "GST %", "GST Amount", "Invoice Total", "Payment Status"]
    buffer = build_workbook([{"sheet_name": "Purchases", "title": "PURCHASE REGISTER",
                               "columns": columns, "headers": headers, "rows": rows,
                               "total_columns": ["taxable_value", "gst_amount", "invoice_total"]}])
    return xlsx_response(buffer, "purchases.xlsx")


@reports_router.get("/issues.xlsx")
def export_issues(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    issues = db.query(Issue).options(
        selectinload(Issue.order), selectinload(Issue.material)
    ).order_by(Issue.date.desc()).all()
    rows = [{
        "issue_code": i.issue_code, "date": i.date.strftime("%d-%m-%Y") if i.date else "",
        "order": i.order.order_code if i.order else "", "material": i.material.name if i.material else "",
        "quantity_issued": float(i.quantity_issued), "unit": i.unit, "issued_to": i.issued_to,
        "department": i.department, "purpose": i.purpose, "approved_by": i.approved_by,
    } for i in issues]
    columns = ["issue_code", "date", "order", "material", "quantity_issued", "unit",
               "issued_to", "department", "purpose", "approved_by"]
    headers = ["Issue ID", "Date", "Order", "Material", "Quantity Issued", "Unit",
               "Issued To", "Department", "Purpose", "Approved By"]
    buffer = build_workbook([{"sheet_name": "Issues", "title": "MATERIAL ISSUE REGISTER",
                               "columns": columns, "headers": headers, "rows": rows}])
    return xlsx_response(buffer, "issues.xlsx")


@reports_router.get("/suppliers.xlsx")
def export_suppliers(
    search: Optional[str] = Query(None), category: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Supplier Master export, matching export_products'/export_materials'
    established pattern. No privileged-gating - Supplier itself carries
    no financial field (per-material pricing lives on the separate
    SupplierMaterial table, not exported here)."""
    from app.modules.procurement.models import Supplier

    query = db.query(Supplier)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Supplier.name.ilike(like), Supplier.supplier_code.ilike(like),
                                  Supplier.business_id.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if category:
        query = query.filter(Supplier.category == category)
        filters_applied.append(f"Category: {category}")

    suppliers = query.order_by(Supplier.name).all()
    rows = [{
        "supplier_id": s.business_id or "", "supplier_code": s.supplier_code, "name": s.name,
        "category": s.category or "", "contact_person": s.contact_person or "", "phone": s.phone or "",
        "gstin": s.gstin or "", "payment_terms": s.payment_terms or "",
    } for s in suppliers]

    columns = ["supplier_id", "supplier_code", "name", "category", "contact_person", "phone",
               "gstin", "payment_terms"]
    headers = ["Supplier ID", "Supplier Code", "Supplier Name", "Category", "Contact Person", "Phone",
               "GSTIN", "Payment Terms"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Suppliers", "title": "SUPPLIER MASTER",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": [("Total Suppliers", str(len(suppliers)))],
    }])
    filename = f"supplier_master_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/materials.xlsx")
def export_materials(
    search: Optional[str] = Query(None), category: Optional[str] = Query(None),
    low_stock_only: bool = Query(False), active_only: bool = Query(False),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Material Master export, matching export_products' established
    pattern. Filters mirror GET /api/materials/'s main params."""
    from app.modules.inventory.models import Material

    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Material)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Material.name.ilike(like), Material.material_code.ilike(like),
                                  Material.business_id.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if category:
        query = query.filter(Material.category == category)
        filters_applied.append(f"Category: {category}")
    if low_stock_only:
        query = query.filter(Material.current_stock <= Material.minimum_stock)
        filters_applied.append("Low stock only")
    if active_only:
        query = query.filter(Material.is_active == True)  # noqa: E712
        filters_applied.append("Active only")

    materials = query.order_by(Material.name).all()
    rows = []
    for m in materials:
        row = {
            "material_id": m.business_id or "", "material_code": m.material_code, "name": m.name,
            "category": m.category or "", "subcategory": m.subcategory.name if m.subcategory else "",
            "unit": m.unit, "current_stock": float(m.current_stock), "minimum_stock": float(m.minimum_stock),
            "location": m.location_ref.name if m.location_ref else (m.location or ""),
            "supplier": m.primary_supplier.name if m.primary_supplier else "",
            "status": "Active" if m.is_active else "Inactive",
        }
        if is_privileged:
            row["average_rate"] = float(m.average_rate) if m.average_rate is not None else None
        rows.append(row)

    columns = ["material_id", "material_code", "name", "category", "subcategory", "unit",
               "current_stock", "minimum_stock", "location", "supplier", "status"]
    headers = ["Material ID", "Material Code", "Material Name", "Category", "Subcategory", "Unit",
               "Current Stock", "Minimum Stock", "Location", "Supplier", "Status"]
    if is_privileged:
        columns += ["average_rate"]
        headers += ["Average Rate"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([{
        "sheet_name": "Materials", "title": "MATERIAL MASTER",
        "columns": columns, "headers": headers, "rows": rows,
        "subtitle": subtitle, "summary": [("Total Materials", str(len(materials)))],
    }])
    filename = f"material_master_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/stock-dashboard.xlsx")
def export_stock_dashboard(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    is_privileged = auth.get("role", "user") in ("master",)
    materials = db.query(Material).options(selectinload(Material.primary_supplier)).all()
    suppliers = db.query(Supplier).all()
    issues = db.query(Issue).options(selectinload(Issue.material)).order_by(Issue.date.desc()).all()

    material_columns = ["material_id", "business_id", "name", "category", "brand_grade", "thickness_size", "unit",
                         "opening_stock", "total_purchased", "total_issued", "current_stock",
                         "minimum_stock", "stock_status", "primary_supplier", "location"]
    material_headers = ["Material ID", "Business ID", "Name", "Category", "Brand/Grade", "Thickness/Size", "Unit",
                         "Opening Stock", "Total Purchased", "Total Issued", "Current Stock",
                         "Minimum Stock", "Stock Status", "Primary Supplier", "Location"]
    if is_privileged:
        # Financial columns only exist in the privileged version - not
        # present-but-blank in the employee version, genuinely absent.
        material_columns[13:13] = ["average_rate", "stock_value"]
        material_headers[13:13] = ["Average Rate", "Stock Value"]

    material_rows = [{
        "material_id": m.material_code, "business_id": m.business_id or "", "name": m.name, "category": m.category,
        "brand_grade": m.brand_grade, "thickness_size": m.thickness_size, "unit": m.unit,
        "opening_stock": m.opening_stock, "total_purchased": m.total_purchased,
        "total_issued": m.total_issued, "current_stock": m.current_stock,
        "minimum_stock": m.minimum_stock, "stock_status": m.stock_status,
        **({"average_rate": float(m.average_rate), "stock_value": m.stock_value} if is_privileged else {}),
        "primary_supplier": m.primary_supplier.name if m.primary_supplier else "",
        "location": m.location,
    } for m in materials]

    issue_rows = [{
        "issue_code": i.issue_code, "date": i.date.strftime("%d-%m-%Y") if i.date else "",
        "material": i.material.name if i.material else "", "quantity_issued": float(i.quantity_issued),
        "issued_to": i.issued_to, "department": i.department,
    } for i in issues]

    supplier_rows = [{
        "supplier_code": s.supplier_code, "business_id": s.business_id or "", "name": s.name, "category": s.category,
        "contact_person": s.contact_person, "phone": s.phone, "payment_terms": s.payment_terms,
    } for s in suppliers]

    sheets = []
    if is_privileged:
        purchases = db.query(Purchase).options(
            selectinload(Purchase.supplier), selectinload(Purchase.material)
        ).order_by(Purchase.date.desc()).all()
        dashboard_rows = [{
            "metric": "Total Stock Value", "value": round(sum(m.stock_value for m in materials), 2),
        }, {
            "metric": "Low Stock Items", "value": len([m for m in materials if 0 < m.current_stock <= m.minimum_stock]),
        }, {
            "metric": "Out of Stock Items", "value": len([m for m in materials if m.current_stock <= 0]),
        }, {
            "metric": "Purchase Value", "value": round(sum(float(p.invoice_total or 0) for p in purchases), 2),
        }]
        purchase_rows = [{
            "purchase_code": p.purchase_code, "business_id": p.business_id or "",
            "date": p.date.strftime("%d-%m-%Y") if p.date else "",
            "supplier": p.supplier.name if p.supplier else "", "material": p.material.name if p.material else "",
            "quantity": float(p.quantity), "invoice_total": float(p.invoice_total), "payment_status": p.payment_status,
        } for p in purchases]
        sheets.append({"sheet_name": "Dashboard", "title": "STOCK DASHBOARD", "columns": ["metric", "value"],
                        "headers": ["Metric", "Value"], "rows": dashboard_rows})

    sheets.append({"sheet_name": "Material Master", "title": "LIVE MATERIAL STOCK MASTER",
                    "columns": material_columns, "headers": material_headers, "rows": material_rows,
                    "total_columns": ["stock_value"] if is_privileged else []})

    if is_privileged:
        sheets.append({"sheet_name": "Purchases", "title": "STOCK IN - PURCHASE REGISTER",
                        "columns": ["purchase_code", "business_id", "date", "supplier", "material", "quantity", "invoice_total", "payment_status"],
                        "headers": ["Purchase ID", "Business ID", "Date", "Supplier", "Material", "Quantity", "Invoice Total", "Payment Status"],
                        "rows": purchase_rows})

    sheets.append({"sheet_name": "Issues", "title": "STOCK OUT - MATERIAL ISSUE REGISTER",
                    "columns": ["issue_code", "date", "material", "quantity_issued", "issued_to", "department"],
                    "headers": ["Issue ID", "Date", "Material", "Quantity Issued", "Issued To", "Department"],
                    "rows": issue_rows})
    sheets.append({"sheet_name": "Suppliers", "title": "SUPPLIER MASTER",
                    "columns": ["supplier_code", "business_id", "name", "category", "contact_person", "phone", "payment_terms"],
                    "headers": ["Supplier ID", "Business ID", "Supplier Name", "Category", "Contact Person", "Phone", "Payment Terms"],
                    "rows": supplier_rows})

    buffer = build_workbook(sheets)
    return xlsx_response(buffer, "stock-dashboard.xlsx")
