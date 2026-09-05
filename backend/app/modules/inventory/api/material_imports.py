from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from app.platform.database.database import get_db
from app.platform.configuration.config import settings
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action
from app.modules.inventory.models import Material, MaterialCategory, MaterialSubcategory, Supplier, Location
from app.modules.inventory.imports.material_schemas import (
    MaterialImportPreviewResponse, MaterialImportRowPreview,
    MaterialImportCommitRequest, MaterialImportCommitResult,
)
from app.platform.database.id_generator import generate_unique_code, generate_business_id
from app.modules.inventory.imports.material_import import (
    build_import_template, parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)

router = APIRouter(prefix="/api/material-imports", tags=["material-imports"])


@router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Material_Import_Template.xlsx"},
    )


@router.post("/preview", response_model=MaterialImportPreviewResponse)
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

    from app.shared.exporters import build_workbook
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


@router.post("/commit", response_model=MaterialImportCommitResult)
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
