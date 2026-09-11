"""Client domain API routes: core CRUD/documents (clients_router),
activity log/follow-ups (activity_router), Excel import
(client_imports_router), product-rate overrides (product_rate_router),
and Excel/PDF exports (reports_router). Combines the former routes.py,
activity_routes.py, import_routes.py, product_rate_routes.py, and
reports.py."""
from typing import List, Optional
from decimal import Decimal
import secrets
import logging
import zipfile
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.platform.audit import log_action
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role, rate_limit
from app.platform.config import settings
from app.platform.ids import generate_unique_code, generate_business_id
from app.platform.storage import get_storage_backend, get_storage_backend_for_record
from app.shared import validate_file_signature, build_workbook, xlsx_response
from app.modules.clients.models import Client, ClientActivity, ClientDocument, ClientProductRate
from app.modules.sales.models import Order, Estimate
from app.modules.catalog.models import Product
from app.modules.catalog.pricing import resolve_selling_rate
from app.modules.clients.services import ClientCreate, ClientUpdate, ClientResponse, ClientWithStats, ClientDocumentResponse
from app.modules.clients.services import find_fuzzy_name_matches
from app.modules.clients.services import ClientActivityCreate, ClientActivityUpdate, ClientActivityResponse
from app.modules.clients.services import ClientImportPreviewResponse, ClientImportRowPreview, ClientImportCommitRequest, ClientImportCommitResult
from app.modules.clients.services import (
    build_import_template, parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)
from app.modules.clients.services import ClientProductRateCreate, ClientProductRateUpdate, ClientProductRateResponse, PricingResolveRequest, PricingResolveResponse
from app.modules.clients.services import generate_client_pdf
from app.modules.clients.services import client_relationship_timeline


# --- routes.py ---
logger = logging.getLogger(__name__)


CLIENT_DOC_ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}


CLIENT_DOC_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg", "image/png",
}


clients_router = APIRouter(prefix="/api/clients", tags=["clients"])


@clients_router.get("/", response_model=List[ClientResponse])
def list_clients(response: Response, search: Optional[str] = Query(None),
                  limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Client)
    if search:
        like = f"%{search}%"
        query = query.filter((Client.name.ilike(like)) | (Client.client_code.ilike(like)) | (Client.phone.ilike(like)))

    query = query.order_by(Client.name)
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    return query.offset(offset).limit(limit).all()


@clients_router.post("/", response_model=ClientResponse, status_code=201)
def create_client(data: ClientCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    payload = data.dict(exclude={"client_code"})
    for _ in range(5):
        code = generate_unique_code(db, Client, "client_code", "CL-")
        client = Client(**payload, client_code=code, business_id=generate_business_id(db))
        db.add(client)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(client)
        return client
    raise HTTPException(status_code=500, detail="Unable to generate a unique client code, please try again")


@clients_router.get("/check-duplicates")
def check_duplicate_clients(name: str = Query(..., min_length=2), db: Session = Depends(get_db),
                             auth=Depends(get_current_user)):
    """Non-blocking by design - flags possible duplicates for the
    caller to review, never prevents creating a client who genuinely
    shares a name with someone else (e.g. two different "Sanket"s are
    a real possibility, not necessarily a mistake). Catches both
    substring matches and typo-variants via fuzzy similarity."""
    matches = find_fuzzy_name_matches(db, name)
    return {
        "possible_duplicates": [
            {"id": c.id, "name": c.name, "client_code": c.client_code, "phone": c.phone, "email": c.email}
            for c in matches
        ],
    }


@clients_router.get("/{client_id}", response_model=ClientWithStats)
def get_client(client_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    is_privileged = auth.get("role", "user") in ("master",)
    order_count, order_sum = db.query(
        func.count(Order.id), func.sum(Order.order_value)
    ).filter(Order.client_id == client_id).one()
    total_sales = order_sum or Decimal("0")
    return ClientWithStats(
        **ClientResponse.model_validate(client).model_dump(),
        total_orders=order_count or 0,
        total_sales=float(total_sales) if is_privileged else None,
    )


@clients_router.get("/{client_id}/relationship-timeline")
def get_client_relationship_timeline(client_id: int, limit: int = Query(200, ge=1, le=500),
                                      db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Family 137 feature 5 - Unified Client Relationship Timeline. See
    client_relationship_timeline's own docstring for the real sources
    aggregated. is_privileged gates payment amounts and financial
    notification types, matching every other financial-confidentiality
    rule in this codebase."""
    is_privileged = auth.get("role", "user") in ("master",)
    timeline = client_relationship_timeline(db, client_id, limit=limit, is_privileged=is_privileged)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return timeline


@clients_router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: int, data: ClientUpdate, db: Session = Depends(get_db),
                   auth=Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(client, field, value)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@clients_router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if db.query(Order).filter(Order.client_id == client_id).first():
        raise HTTPException(status_code=400, detail="This client has orders and cannot be deleted.")
    if db.query(Estimate).filter(Estimate.client_id == client_id).first():
        raise HTTPException(status_code=400, detail="This client has estimates and cannot be deleted.")
    client_name = client.name
    db.query(ClientActivity).filter(ClientActivity.client_id == client_id).delete()
    db.delete(client)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_client", module_name="clients",
               record_id=client_id, old_value={"name": client_name})


@clients_router.get("/{client_id}/documents", response_model=List[ClientDocumentResponse])
def list_client_documents(client_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(Client).filter(Client.id == client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")
    return db.query(ClientDocument).filter(ClientDocument.client_id == client_id).order_by(
        ClientDocument.created_at.desc()
    ).all()


@clients_router.post("/{client_id}/documents", response_model=ClientDocumentResponse, status_code=201)
def upload_client_document(client_id: int, file: UploadFile = File(...), description: Optional[str] = None,
                            request: Request = None, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    """Same validation discipline as candidate resume uploads: extension
    allowlist, MIME check, and a real streamed byte count against the
    size limit (never trusting Content-Length). A random server-side
    filename - never the user-supplied one - so this can never be used
    for path traversal or to collide with another client's file."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    original_name = file.filename or "document"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in CLIENT_DOC_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File must be a PDF, DOC, DOCX, JPG, or PNG (got .{ext or 'unknown'}).",
        )
    if file.content_type not in CLIENT_DOC_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    backend = get_storage_backend()
    stored_filename = f"client_documents/{secrets.token_hex(16)}.{ext}"

    size = 0
    first_chunk = True
    chunks = []
    try:
        while chunk := file.file.read(1024 * 1024):
            if first_chunk:
                if not validate_file_signature(ext, chunk):
                    raise HTTPException(
                        status_code=400,
                        detail="The file's contents don't match its extension. Please upload a genuine file of the stated type.",
                    )
                first_chunk = False
            size += len(chunk)
            if size > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
                )
            chunks.append(chunk)
        storage_ref = backend.save(stored_filename, b"".join(chunks))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save the uploaded file.")

    document = ClientDocument(
        client_id=client_id, original_filename=original_name, stored_filename=stored_filename,
        content_type=file.content_type, description=description, uploaded_by=str(auth.get("user_id", "")),
        storage_backend=storage_ref.backend, drive_file_id=storage_ref.drive_file_id,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # The file was genuinely saved (Drive or local) but has no
        # Woodful record now - clean it up rather than leave an
        # orphaned, untracked file. Best-effort: if cleanup itself
        # fails, the original DB error is still what the caller sees,
        # not this secondary failure.
        try:
            backend.delete(storage_ref)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to save the document record.")
    db.refresh(document)
    if request is not None:
        log_action(db, request, user_id=auth.get("user_id"), action="upload_client_document", module_name="clients",
                   record_id=document.id, new_value={"client_id": client_id, "filename": original_name})
    return document


@clients_router.get("/{client_id}/documents/{document_id}/download")
def download_client_document(client_id: int, document_id: int, db: Session = Depends(get_db),
                              auth=Depends(get_current_user)):
    """Object-level check: the document must actually belong to the
    client_id in the URL, not just exist by document_id - otherwise a
    valid document_id from one client could be used to probe/access a
    document under a different, unrelated client_id in the path."""
    document = db.query(ClientDocument).filter(
        ClientDocument.id == document_id, ClientDocument.client_id == client_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    backend, storage_ref = get_storage_backend_for_record(document)
    if not backend.exists(storage_ref):
        raise HTTPException(status_code=404, detail="The stored file could not be found.")
    file_bytes = backend.read(storage_ref)
    return Response(
        content=file_bytes, media_type=document.content_type or "application/octet-stream",
        headers={
            "Cache-Control": "no-store, private",
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
        },
    )


@clients_router.delete("/{client_id}/documents/{document_id}", status_code=204)
def delete_client_document(client_id: int, document_id: int, request: Request, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    document = db.query(ClientDocument).filter(
        ClientDocument.id == document_id, ClientDocument.client_id == client_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    backend, storage_ref = get_storage_backend_for_record(document)
    old_value = {"client_id": client_id, "filename": document.original_filename}
    db.delete(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete the document record.")
    try:
        backend.delete(storage_ref)
    except Exception:
        logger.error(f"Orphaned file after client document {document_id} delete: {storage_ref}")
    log_action(db, request, user_id=auth.get("user_id"), action="delete_client_document", module_name="clients",
               record_id=document_id, old_value=old_value)


# --- activity_routes.py ---
activity_router = APIRouter(prefix="/api/client-activities", tags=["client-activities"])


@activity_router.get("/", response_model=List[ClientActivityResponse])
def list_client_activities(client_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                            auth=Depends(get_current_user)):
    query = db.query(ClientActivity)
    if client_id:
        query = query.filter(ClientActivity.client_id == client_id)
    return query.order_by(ClientActivity.date.desc()).all()


@activity_router.get("/follow-ups")
def list_pending_follow_ups(
    within_days: int = Query(7, ge=0, le=365, description="Include follow-ups due within this many days (overdue always included)"),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Overdue-or-upcoming, not-yet-completed follow-ups, with the
    client name/code so a dashboard widget doesn't need a second
    round trip per row."""
    cutoff = datetime.utcnow() + timedelta(days=within_days)
    activities = (
        db.query(ClientActivity)
        .options(selectinload(ClientActivity.client))
        .filter(
            ClientActivity.follow_up_date.isnot(None),
            ClientActivity.follow_up_date <= cutoff,
            ClientActivity.follow_up_done.is_(False),
        )
        .order_by(ClientActivity.follow_up_date.asc())
        .all()
    )
    now = datetime.utcnow()
    return [
        {
            "id": a.id,
            "client_id": a.client_id,
            "client_name": a.client.name if a.client else None,
            "client_code": a.client.client_code if a.client else None,
            "activity_type": a.activity_type,
            "summary": a.summary,
            "follow_up_date": a.follow_up_date,
            "overdue": a.follow_up_date < now if a.follow_up_date else False,
        }
        for a in activities
    ]


@activity_router.post("/", response_model=ClientActivityResponse, status_code=201)
def log_client_activity(data: ClientActivityCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(Client).filter(Client.id == data.client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")
    activity = ClientActivity(**data.dict())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@activity_router.patch("/{activity_id}/complete-follow-up", response_model=ClientActivityResponse)
def complete_follow_up(activity_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.follow_up_date is None:
        raise HTTPException(status_code=400, detail="This activity has no follow-up to complete")
    activity.follow_up_done = True
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@activity_router.get("/{activity_id}", response_model=ClientActivityResponse)
def get_client_activity(activity_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@activity_router.put("/{activity_id}", response_model=ClientActivityResponse)
def update_client_activity(activity_id: int, data: ClientActivityUpdate, db: Session = Depends(get_db),
                            auth=Depends(get_current_user)):
    """A mis-logged call/meeting note (wrong date, typo'd summary) had
    no way to ever be corrected before this - only re-logged as a new,
    separate entry, leaving the wrong one sitting in the client's
    history permanently."""
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(activity, field, value)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@activity_router.delete("/{activity_id}", status_code=204)
def delete_client_activity(activity_id: int, request: Request, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    activity = db.query(ClientActivity).filter(ClientActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    old_value = {"client_id": activity.client_id, "summary": activity.summary, "date": str(activity.date)}
    db.delete(activity)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_client_activity", module_name="clients",
               record_id=activity_id, old_value=old_value)


# --- import_routes.py ---
client_imports_router = APIRouter(prefix="/api/client-imports", tags=["client-imports"])


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


@client_imports_router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Client_Import_Template.xlsx"},
    )


@client_imports_router.post("/preview", response_model=ClientImportPreviewResponse)
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


@client_imports_router.post("/error-report")
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


@client_imports_router.post("/commit", response_model=ClientImportCommitResult)
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


# --- product_rate_routes.py ---
product_rate_router = APIRouter(prefix="/api/client-product-rates", tags=["client-product-rates"])


@product_rate_router.get("/", response_model=List[ClientProductRateResponse])
def list_client_product_rates(
    client_id: Optional[int] = Query(None), product_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    # Master-only even to VIEW - these are negotiated commercial terms
    # per client, same sensitivity as any other pricing/cost data here.
    query = db.query(ClientProductRate)
    if client_id:
        query = query.filter(ClientProductRate.client_id == client_id)
    if product_id:
        query = query.filter(ClientProductRate.product_id == product_id)
    return query.all()


@product_rate_router.post("/", response_model=ClientProductRateResponse, status_code=201)
def create_client_product_rate(data: ClientProductRateCreate, request: Request,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    if data.product_id is not None and not db.query(Product).filter(Product.id == data.product_id).first():
        raise HTTPException(status_code=400, detail="Invalid Product ID")
    from app.modules.clients.models import Client
    if not db.query(Client).filter(Client.id == data.client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")

    if data.product_id is None:
        existing_default = db.query(ClientProductRate).filter(
            ClientProductRate.client_id == data.client_id, ClientProductRate.product_id.is_(None),
        ).first()
        if existing_default:
            raise HTTPException(status_code=409, detail="This client already has a client-wide default margin - edit it instead.")

    rate = ClientProductRate(**data.dict(), created_by=auth.get("username") or str(auth.get("user_id")))
    db.add(rate)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A rate override for this client and product already exists - edit it instead.")
    db.refresh(rate)
    log_action(db, request, user_id=auth.get("user_id"), action="create_client_product_rate",
               module_name="client_product_rates", record_id=rate.id,
               new_value={"client_id": rate.client_id, "product_id": rate.product_id})
    return rate


@product_rate_router.put("/{rate_id}", response_model=ClientProductRateResponse)
def update_client_product_rate(rate_id: int, data: ClientProductRateUpdate, request: Request,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    rate = db.query(ClientProductRate).filter(ClientProductRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate override not found")
    updates = data.dict(exclude_unset=True)
    final_margin = updates.get("margin_percent", rate.margin_percent)
    final_fixed = updates.get("fixed_selling_price", rate.fixed_selling_price)
    if final_margin is not None and final_fixed is not None:
        raise HTTPException(status_code=422, detail="Set either margin_percent or fixed_selling_price, not both.")
    if final_margin is None and final_fixed is None:
        raise HTTPException(status_code=422, detail="Set either margin_percent or fixed_selling_price.")
    for field, value in updates.items():
        setattr(rate, field, value)
    db.add(rate)
    db.commit()
    db.refresh(rate)
    log_action(db, request, user_id=auth.get("user_id"), action="update_client_product_rate",
               module_name="client_product_rates", record_id=rate.id, new_value={k: str(v) for k, v in updates.items()})
    return rate


@product_rate_router.delete("/{rate_id}", status_code=204)
def delete_client_product_rate(rate_id: int, request: Request, db: Session = Depends(get_db),
                                auth=Depends(require_role("master"))):
    rate = db.query(ClientProductRate).filter(ClientProductRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate override not found")
    db.delete(rate)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_client_product_rate",
               module_name="client_product_rates", record_id=rate_id)


@product_rate_router.post("/resolve", response_model=PricingResolveResponse)
def resolve_pricing(data: PricingResolveRequest, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    """Preview what rate/rule would apply for a given product+client(+
    estimate) combination, without saving anything - lets the Estimate
    UI show "Calculated Price" before the person commits to it."""
    if not data.product_id:
        raise HTTPException(status_code=400, detail="product_id is required to resolve a price")
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=400, detail="Invalid Product ID")

    cost = product.cost_price or product.suggested_cost_price
    if cost is None:
        cost = Decimal("0")
    cost = Decimal(str(cost))

    customer_fixed = None
    customer_margin = None
    if data.client_id:
        override = db.query(ClientProductRate).filter(
            ClientProductRate.client_id == data.client_id, ClientProductRate.product_id == data.product_id,
        ).first()
        if not override:
            override = db.query(ClientProductRate).filter(
                ClientProductRate.client_id == data.client_id, ClientProductRate.product_id.is_(None),
            ).first()
        if override:
            customer_fixed = override.fixed_selling_price
            customer_margin = override.margin_percent

    estimate_margin = None
    if data.estimate_id:
        estimate = db.query(Estimate).filter(Estimate.id == data.estimate_id).first()
        if estimate:
            estimate_margin = estimate.margin_percent_override

    result = resolve_selling_rate(
        cost=cost, explicit_override=data.explicit_override,
        customer_product_fixed_price=customer_fixed, customer_margin_percent=customer_margin,
        estimate_margin_percent=estimate_margin, product_margin_percent=product.margin_percent,
    )
    return PricingResolveResponse(
        selling_rate=result.selling_rate, pricing_rule_applied=result.pricing_rule_applied,
        margin_percent_used=result.margin_percent_used, cost_used=cost,
    )


# --- reports.py ---
"""Client-domain report exports: client export and client profile
PDF. Split out of the former monolithic reports.py - see
modules/inventory/api/reports.py's docstring for why."""

reports_router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@reports_router.get("/clients.xlsx")
def export_clients(
    search: Optional[str] = Query(None), status: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """Client Register - the complete client list without opening each
    client individually (P4). `search`/`status` mirror the filters on
    GET /api/clients/ exactly, so "search Mhow -> export only Mhow
    clients" produces the same set the user is already looking at."""
    is_privileged = auth.get("role", "user") in ("master",)
    query = db.query(Client)
    filters_applied = []
    if search:
        like = f"%{search}%"
        query = query.filter((Client.name.ilike(like)) | (Client.client_code.ilike(like)) | (Client.phone.ilike(like)))
        filters_applied.append(f'Search: "{search}"')
    if status:
        query = query.filter(Client.status == status)
        filters_applied.append(f"Status: {status}")

    clients = query.order_by(Client.name).all()
    rows = []
    for c in clients:
        orders = c.orders or []
        latest_order = max(orders, key=lambda o: o.order_date) if orders else None
        row = {
            "client_id": c.business_id or "", "name": c.name, "contact_person": c.contact_person or "",
            "phone": c.phone or "", "email": c.email or "", "address": c.address or "",
            "site_address": c.site_address or "", "city": c.city or "", "gstin": c.gstin or "",
            "project_count": len(orders), "order_count": len(orders),
            "latest_order": latest_order.order_date.strftime("%d-%m-%Y") if latest_order else "",
            "status": c.status, "created_date": c.created_at.strftime("%d-%m-%Y") if c.created_at else "",
        }
        if is_privileged:
            total_order_value = sum((Decimal(o.order_value or 0) for o in orders), Decimal("0"))
            total_paid = sum((Decimal(o.total_received or 0) for o in orders), Decimal("0"))
            outstanding = sum((Decimal(o.balance or 0) for o in orders), Decimal("0"))
            row["total_order_value"] = float(total_order_value)
            row["total_paid"] = float(total_paid)
            row["outstanding"] = float(outstanding)
        rows.append(row)

    columns = ["client_id", "name", "contact_person", "phone", "email", "address", "site_address", "city",
               "gstin", "project_count", "order_count", "latest_order", "status", "created_date"]
    headers = ["Client ID", "Client Name", "Contact Person", "Phone", "Email", "Address", "Site Address", "City",
               "GSTIN", "Project Count", "Order Count", "Latest Order", "Status", "Created Date"]
    total_columns = []
    if is_privileged:
        idx = columns.index("project_count")
        columns[idx:idx] = ["total_order_value", "total_paid", "outstanding"]
        headers[idx:idx] = ["Total Order Value", "Total Paid", "Outstanding"]
        total_columns = ["total_order_value", "total_paid", "outstanding"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [("Total Clients", str(len(clients)))]
    if is_privileged:
        summary.append(("Total Order Value", f"Rs {sum(r['total_order_value'] for r in rows):,.2f}"))
        summary.append(("Total Outstanding", f"Rs {sum(r['outstanding'] for r in rows):,.2f}"))

    buffer = build_workbook([{
        "sheet_name": "Clients", "title": "CLIENT REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": total_columns,
        "subtitle": subtitle, "summary": summary,
    }])
    filename = f"client_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@reports_router.get("/clients/{client_id}/profile.pdf")
def export_client_pdf(client_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Client profile PDF - available to any authenticated role (client
    contact info isn't the financial data that's restricted elsewhere),
    but the sales-summary/order-value figures inside are genuinely
    gated by role, matching the same protection the normal JSON client
    API already applies for non-master users."""
    from app.modules.clients.models import Client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    is_privileged = auth.get("role", "user") in ("master",)
    buffer = generate_client_pdf(client, is_privileged)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="client-{client.client_code}.pdf"', "Cache-Control": "no-store, private"},
    )
