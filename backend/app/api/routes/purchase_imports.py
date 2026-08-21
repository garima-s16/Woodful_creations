from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import zipfile
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from datetime import datetime

from app.core.database import get_db
from app.core.config import settings
from app.core.security import require_role
from app.models.material import Material
from app.models.supplier import Supplier
from app.schemas.purchase import PurchaseCreate
from app.schemas.purchase_import import (
    ImportPreviewResponse, ImportRowPreview, ImportCommitRequest, ImportCommitResult,
)
from app.services.stock_service import StockService
from app.utils.id_generator import generate_unique_code, generate_business_id
from app.utils.purchase_import import (
    build_import_template, parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)

router = APIRouter(prefix="/api/purchase-imports", tags=["purchase-imports"])


@router.get("/template")
def download_template():
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Purchase_Import_Template.xlsx"},
    )


@router.post("/preview", response_model=ImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file - never writes anything to
    the database. The user reviews this, resolves any unmatched
    materials, and only then calls /commit."""
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

    # Same normalize_match_key used when a row's typed name is looked up
    # (validate_and_match_row) - so whitespace/case differences on
    # either side never prevent a genuine match, without this ever
    # becoming fuzzy matching that could pick the wrong record.
    materials_by_name = {normalize_match_key(m.name): m for m in db.query(Material).all()}
    suppliers_by_name = {normalize_match_key(s.name): s for s in db.query(Supplier).all()}

    preview_rows = []
    matched_count = 0
    new_material_count = 0
    error_count = 0
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(row, db, materials_by_name, suppliers_by_name)
        if errors:
            error_count += 1
        elif result["is_new_material"]:
            new_material_count += 1
        else:
            matched_count += 1
        preview_rows.append(ImportRowPreview(row_number=idx, **result, errors=errors))

    return ImportPreviewResponse(
        total_rows=len(raw_rows), matched_rows=matched_count,
        new_material_rows=new_material_count, error_rows=error_count, rows=preview_rows,
    )


@router.post("/commit", response_model=ImportCommitResult)
def commit_import(data: ImportCommitRequest, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Actually creates records - only for rows the caller sends here,
    which should be exactly the rows the user reviewed and confirmed in
    the preview step. Each row commits individually (StockService.
    record_purchase commits internally, same as manual purchase entry) -
    this is NOT one atomic all-or-nothing transaction. If a row fails
    partway through the batch, earlier rows in this same request are
    already committed; the response's created_purchases count and
    purchase_ids reflect exactly what succeeded before the failure, and
    the remaining rows are simply not processed - re-upload just the
    rows that didn't go through rather than the whole file."""
    created_materials = 0
    purchase_ids = []
    error_message = None

    for i, row in enumerate(data.rows):
        try:
            material_id = row.matched_material_id
            if row.create_new_material:
                if not row.material_name:
                    raise ValueError("Cannot create a material with no name")
                material_id = None
                for _ in range(5):
                    code = generate_unique_code(db, Material, "material_code", "MAT-")
                    material = Material(
                        material_code=code, business_id=generate_business_id(db), name=row.material_name,
                        brand_grade=row.specification, unit=row.unit, opening_stock=0,
                        current_stock=0, minimum_stock=0, average_rate=row.rate,
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
                created_materials += 1

            if not material_id:
                raise ValueError(f'Row for "{row.material_name}" has no resolved material - not imported.')

            purchase = StockService.record_purchase(db, PurchaseCreate(
                date=row.invoice_date or datetime.utcnow(),
                supplier_id=row.matched_supplier_id, material_id=material_id,
                quantity=row.quantity, unit=row.unit, rate=row.rate,
                gst_percent=row.gst_percent, payment_status="Paid",
            ))
            purchase_ids.append(purchase.id)
        except (ValueError, HTTPException) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_message = f"Stopped at row {i + 1}: {detail}"
            break

    return ImportCommitResult(
        created_materials=created_materials, created_purchases=len(purchase_ids),
        purchase_ids=purchase_ids, error=error_message,
    )
