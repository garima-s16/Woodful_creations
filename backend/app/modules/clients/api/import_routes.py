from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from app.platform.database.database import get_db
from app.platform.configuration.config import settings
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action
from app.modules.clients.models import Client
from app.modules.clients.schemas import (
    ClientImportPreviewResponse, ClientImportRowPreview,
    ClientImportCommitRequest, ClientImportCommitResult,
)
from app.platform.database.id_generator import generate_unique_code, generate_business_id
from app.shared.exporters import build_workbook
from app.modules.clients.import_utils import (
    build_import_template, parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)

router = APIRouter(prefix="/api/client-imports", tags=["client-imports"])


def _read_and_parse_upload(file: UploadFile):
    """Shared by /preview and /error-report so the two can never
    disagree about what counts as an error - both parse and validate
    the uploaded file exactly the same way."""
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
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
            )
    try:
        return parse_uploaded_workbook(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Couldn't read this file - please upload a valid .xlsx file using the downloaded template.",
        )


def _validate_rows(raw_rows, db: Session):
    """Runs the same validation + in-file duplicate detection /preview
    uses, returning (preview_rows, new_count, duplicate_count, error_count)."""
    all_clients = db.query(Client).all()
    existing_by_key = {}
    for c in all_clients:
        existing_by_key[normalize_match_key(c.name, c.phone)] = c

    preview_rows = []
    new_count = 0
    duplicate_count = 0
    error_count = 0
    seen_in_file = {}
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(row, existing_by_key, fuzzy_candidates=all_clients)
        if not errors and not result["is_duplicate"]:
            match_key = normalize_match_key(result.get("name"), result.get("phone"))
            if match_key in seen_in_file:
                errors = errors + [f"Duplicate of row {seen_in_file[match_key]} in this file (same name + phone)"]
            else:
                seen_in_file[match_key] = idx
        if errors:
            error_count += 1
        elif result["is_duplicate"]:
            duplicate_count += 1
        else:
            new_count += 1
        preview_rows.append(ClientImportRowPreview(row_number=idx, **result, errors=errors))
    return preview_rows, new_count, duplicate_count, error_count


@router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Client_Import_Template.xlsx"},
    )


@router.post("/preview", response_model=ClientImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file only - never writes to the
    database. The user reviews this (including any flagged possible
    duplicates) and only then calls /commit."""
    raw_rows = _read_and_parse_upload(file)
    preview_rows, new_count, duplicate_count, error_count = _validate_rows(raw_rows, db)
    return ClientImportPreviewResponse(
        total_rows=len(raw_rows), new_rows=new_count,
        duplicate_rows=duplicate_count, error_rows=error_count, rows=preview_rows,
    )


@router.post("/error-report")
def download_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the same logic
    /preview uses - see _validate_rows) and returns a real, professionally
    formatted Woodful .xlsx listing only the rejected rows, each with
    its original row number, the values supplied, and the specific
    reason(s) it was rejected - so a person can fix those rows and
    re-upload, rather than guessing from a generic failure message."""
    raw_rows = _read_and_parse_upload(file)
    preview_rows, _, _, error_count = _validate_rows(raw_rows, db)
    error_rows = [r for r in preview_rows if r.errors]

    rows = [{
        "row": r.row_number, "name": r.name or "", "phone": r.phone or "",
        "email": r.email or "", "reason": "; ".join(r.errors),
    } for r in error_rows]

    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Client Import Error Report",
        "subtitle": f"{len(error_rows)} of {len(raw_rows)} row(s) rejected. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["row", "name", "phone", "email", "reason"],
        "headers": ["Excel Row", "Client Name", "Phone", "Email", "Reason Rejected"],
        "rows": rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Client_Import_Errors.xlsx"},
    )


@router.post("/commit", response_model=ClientImportCommitResult)
def commit_import(data: ClientImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Creates a Client Master row per confirmed row that is genuinely
    new. A row carrying matched_client_id (from the preview step, per
    the Client Recognition rule: name AND phone both matched an
    existing client) is never re-created - it's counted as
    "matched existing" and no new Client ID is generated, exactly like
    the same recognition rule applied during order intake. Not fully
    atomic across the whole batch by design (same as the purchase/
    product import commits): each row commits individually, so if one
    fails the response reflects exactly what succeeded before the
    failure - re-upload just the rows that didn't go through, rather
    than the whole batch silently failing with no partial progress
    preserved."""
    created = 0
    matched_existing = 0
    skipped = 0
    client_ids = []
    error_message = None

    for i, row in enumerate(data.rows):
        if row.skip:
            skipped += 1
            continue
        if row.matched_client_id:
            # Revalidate rather than trust the client-supplied ID -
            # confirm the referenced client genuinely exists and that
            # its stored name+phone genuinely still satisfy the same
            # Client Recognition rule the preview step used to
            # determine this was a match in the first place. A stale
            # or manipulated matched_client_id must never silently
            # associate imported data with the wrong client.
            existing_client = db.query(Client).filter(Client.id == row.matched_client_id).first()
            if not existing_client or normalize_match_key(existing_client.name, existing_client.phone) != normalize_match_key(row.name, row.phone):
                error_message = f"Stopped at row {i + 1}: the matched client no longer matches this row's data - please re-run preview."
                break
            # Reuse - the Client Recognition rule (name AND phone both
            # matched) means this is the same client returning, not a
            # new one. No write, no new Client ID.
            matched_existing += 1
            client_ids.append(row.matched_client_id)
            continue
        try:
            client_id = None
            for _ in range(5):
                code = generate_unique_code(db, Client, "client_code", "CL-")
                client = Client(
                    client_code=code, business_id=generate_business_id(db),
                    name=row.name, client_type=row.client_type, contact_person=row.contact_person, phone=row.phone,
                    alternate_phone=row.alternate_phone, email=row.email, address=row.address,
                    site_address=row.site_address, city=row.city, state=row.state, pincode=row.pincode,
                    gstin=row.gstin, lead_source=row.lead_source, remarks=row.remarks,
                )
                db.add(client)
                try:
                    db.flush()
                    client_id = client.id
                    break
                except Exception:
                    db.rollback()
            if client_id is None:
                raise ValueError("Could not generate a unique client code")
            db.commit()
            created += 1
            client_ids.append(client_id)
        except (ValueError, HTTPException) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_message = f"Stopped at row {i + 1}: {detail}"
            break

    log_action(db, request, user_id=auth.get("user_id"), action="import_clients", module_name="clients",
               new_value={
                   "total_rows": len(data.rows), "created": created,
                   "matched_existing": matched_existing, "skipped": skipped,
                   "error": error_message,
               })
    return ClientImportCommitResult(
        created_clients=created, matched_existing=matched_existing, skipped=skipped,
        client_ids=client_ids, error=error_message,
    )
