from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from app.platform.database.database import get_db
from app.platform.configuration.config import settings
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action
from app.modules.catalog.models import Product
from app.modules.catalog.imports.product_schemas import (
    ProductImportPreviewResponse, ProductImportRowPreview,
    ProductImportCommitRequest, ProductImportCommitResult,
)
from app.platform.database.id_generator import generate_unique_code, generate_business_id
from app.modules.catalog.imports.product_import import (
    build_import_template, parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)

router = APIRouter(prefix="/api/product-imports", tags=["product-imports"])


@router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Product_Import_Template.xlsx"},
    )


@router.post("/preview", response_model=ProductImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
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


@router.post("/error-report")
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

    from app.shared.exporters import build_workbook
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


@router.post("/commit", response_model=ProductImportCommitResult)
def commit_import(data: ProductImportCommitRequest, request: Request, db: Session = Depends(get_db),
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
