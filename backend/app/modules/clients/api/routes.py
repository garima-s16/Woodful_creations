from typing import List, Optional
from decimal import Decimal
import secrets
import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, UploadFile, File
from app.platform.audit.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy import func

from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.configuration.config import settings
from app.modules.clients.models import Client, ClientActivity, ClientDocument
from app.modules.sales.models import Order, Estimate
from app.modules.clients.schemas import ClientCreate, ClientUpdate, ClientResponse, ClientWithStats, ClientDocumentResponse
from app.platform.database.id_generator import generate_unique_code, generate_business_id
from app.modules.clients.matching import find_fuzzy_name_matches

# A broader allowlist than resumes (candidates.py) - client documents
# genuinely include contracts/ID proofs (PDF/DOC) as well as site
# photos (JPG/PNG), not just one narrow document type.
CLIENT_DOC_ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}
CLIENT_DOC_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg", "image/png",
}

from app.shared.validators import validate_file_signature
from app.platform.storage.storage import get_storage_backend, get_storage_backend_for_record


router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("/", response_model=List[ClientResponse])
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


@router.post("/", response_model=ClientResponse, status_code=201)
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


@router.get("/check-duplicates")
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


@router.get("/{client_id}", response_model=ClientWithStats)
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


@router.put("/{client_id}", response_model=ClientResponse)
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


@router.delete("/{client_id}", status_code=204)
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


@router.get("/{client_id}/documents", response_model=List[ClientDocumentResponse])
def list_client_documents(client_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    if not db.query(Client).filter(Client.id == client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")
    return db.query(ClientDocument).filter(ClientDocument.client_id == client_id).order_by(
        ClientDocument.created_at.desc()
    ).all()


@router.post("/{client_id}/documents", response_model=ClientDocumentResponse, status_code=201)
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


@router.get("/{client_id}/documents/{document_id}/download")
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


@router.delete("/{client_id}/documents/{document_id}", status_code=204)
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
