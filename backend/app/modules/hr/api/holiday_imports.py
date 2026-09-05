from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from app.platform.database.database import get_db
from app.platform.configuration.config import settings
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action
from app.modules.hr.models import CompanyHoliday
from app.modules.hr.imports.holiday_schemas import (
    HolidayImportPreviewResponse, HolidayImportRowPreview,
    HolidayImportCommitRequest, HolidayImportCommitResult,
)
from app.modules.hr.imports.holiday_import import build_import_template, parse_uploaded_workbook, validate_row

router = APIRouter(prefix="/api/holiday-imports", tags=["holiday-imports"])


@router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Company_Holiday_Import_Template.xlsx"},
    )


@router.post("/preview", response_model=HolidayImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file only - never writes to
    the database. A date that already has a holiday is flagged as a
    duplicate (not an error) so the commit step can offer update-or-skip,
    supporting the Export -> Edit -> Import workflow."""
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

    existing_dates = {h.date for h in db.query(CompanyHoliday.date).all()}
    seen_dates_in_file = set()

    preview_rows = []
    new_count = 0
    duplicate_count = 0
    error_count = 0
    for idx, row in enumerate(raw_rows, start=1):
        parsed, errors = validate_row(row, existing_dates, seen_dates_in_file)
        if errors:
            error_count += 1
        elif parsed["is_duplicate"]:
            duplicate_count += 1
        else:
            new_count += 1
        preview_rows.append(HolidayImportRowPreview(row_number=idx, **parsed, errors=errors))

    return HolidayImportPreviewResponse(
        total_rows=len(raw_rows), new_rows=new_count,
        duplicate_rows=duplicate_count, error_rows=error_count, rows=preview_rows,
    )


@router.post("/error-report")
def download_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the logic /preview
    uses) and returns a real .xlsx listing only the rejected rows, each
    with its original row number and the specific reason(s) it was
    rejected - matching the established pattern from client_imports.py."""
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

    existing_dates = {h.date for h in db.query(CompanyHoliday.date).all()}
    seen_dates_in_file = set()
    error_rows = []
    for idx, row in enumerate(raw_rows, start=1):
        parsed, errors = validate_row(row, existing_dates, seen_dates_in_file)
        if errors:
            error_rows.append({
                "row": idx, "date": str(row.get("Date *") or ""), "name": row.get("Holiday Name *") or "",
                "type": row.get("Type *") or "", "reason": "; ".join(errors),
            })

    from app.shared.exporters import build_workbook
    from fastapi.responses import StreamingResponse
    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Holiday Import Error Report",
        "subtitle": f"{len(error_rows)} of {len(raw_rows)} row(s) rejected. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["row", "date", "name", "type", "reason"],
        "headers": ["Excel Row", "Date", "Holiday Name", "Type", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Holiday_Import_Errors.xlsx"},
    )


@router.post("/commit", response_model=HolidayImportCommitResult)
def commit_import(data: HolidayImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """A row whose date already exists is only ever touched if the
    caller explicitly set overwrite_existing (the user confirmed this
    during preview) - otherwise it's safely skipped, never silently
    duplicated or silently overwritten."""
    created = 0
    updated = 0
    skipped = 0
    error_message = None

    for i, row in enumerate(data.rows):
        if row.skip:
            skipped += 1
            continue
        try:
            existing = db.query(CompanyHoliday).filter(CompanyHoliday.date == row.date).first()
            if existing:
                if not row.overwrite_existing:
                    skipped += 1
                    continue
                existing.name = row.name
                existing.is_working = row.is_working
                existing.remarks = row.remarks
                db.add(existing)
                db.commit()
                updated += 1
            else:
                holiday = CompanyHoliday(date=row.date, name=row.name, is_working=row.is_working, remarks=row.remarks)
                db.add(holiday)
                db.commit()
                created += 1
        except Exception as e:
            db.rollback()
            error_message = f"Stopped at row {i + 1}: {str(e)}"
            break

    log_action(
        db, request, user_id=auth.get("user_id"), action="import_company_holidays", module_name="working_calendar",
        new_value={"created": created, "updated": updated, "skipped": skipped},
    )

    return HolidayImportCommitResult(created=created, updated=updated, skipped=skipped, error=error_message)
