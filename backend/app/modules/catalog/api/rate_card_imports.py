from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from app.platform.database.database import get_db
from app.platform.configuration.config import settings
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action
from app.modules.catalog.models import RateCard
from app.modules.catalog.imports.rate_card_schemas import (
    RateCardImportPreviewResponse, RateCardImportRowPreview,
    RateCardImportCommitRequest, RateCardImportCommitResult,
)
from app.platform.database.id_generator import generate_unique_code, generate_business_id
from app.modules.catalog.imports.rate_card_import import build_import_template, parse_uploaded_workbook, validate_row
from app.shared.exporters import build_workbook

router = APIRouter(prefix="/api/rate-card-imports", tags=["rate-card-imports"])


@router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Rate_Master_Import_Template.xlsx"},
    )


@router.post("/preview", response_model=RateCardImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
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
        raw_rows = parse_uploaded_workbook(bytes(file_bytes))
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


@router.post("/commit", response_model=RateCardImportCommitResult)
def commit_import(data: RateCardImportCommitRequest, request: Request, db: Session = Depends(get_db),
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
