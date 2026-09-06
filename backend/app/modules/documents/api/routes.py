from typing import List, Optional
import secrets
import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi import Response
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.audit.audit import log_action
from app.platform.configuration.config import settings
from app.modules.documents.models import GenericDocument, DOCUMENT_PARENT_TYPES
from app.modules.sales.models import Order
from app.modules.procurement.models import Supplier, Purchase
from app.modules.hr.models import Employee
from app.modules.catalog.models import Product
from app.modules.documents.schemas import GenericDocumentResponse
from app.shared.validators import validate_file_signature
from app.platform.storage.storage import get_storage_backend, get_storage_backend_for_record

router = APIRouter(prefix="/api/documents", tags=["documents"])

DOC_ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "jpg", "jpeg", "png", "xlsx"}
DOC_ALLOWED_MIME_TYPES = {
    "application/pdf", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg", "image/png",
}

PARENT_MODELS = {"order": Order, "supplier": Supplier, "purchase": Purchase, "employee": Employee, "product": Product}
# Sensitive parent types (salary-adjacent or financial) require master
# to even read the document list/download - matching how those
# entities' own sensitive fields are already redacted/restricted
# elsewhere in this app. Less sensitive types match their entity's own
# open-read pattern.
SENSITIVE_PARENT_TYPES = {"employee", "purchase"}


def _validate_parent_type(parent_type: str) -> None:
    if parent_type not in DOCUMENT_PARENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported document type: {parent_type}")


def _get_parent_or_404(db: Session, parent_type: str, parent_id: int):
    model = PARENT_MODELS[parent_type]
    parent = db.query(model).filter(model.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail=f"{parent_type.capitalize()} not found")
    return parent


def _check_read_permission(parent_type: str, role: str) -> None:
    if parent_type in SENSITIVE_PARENT_TYPES and role not in ("master",):
        raise HTTPException(status_code=403, detail="This document type requires a master account.")


@router.get("/{parent_type}/{parent_id}", response_model=List[GenericDocumentResponse])
def list_documents(parent_type: str, parent_id: int, db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    _validate_parent_type(parent_type)
    _check_read_permission(parent_type, auth.get("role", "user"))
    _get_parent_or_404(db, parent_type, parent_id)
    return db.query(GenericDocument).filter(
        GenericDocument.parent_type == parent_type, GenericDocument.parent_id == parent_id,
    ).order_by(GenericDocument.created_at.desc()).all()


@router.post("/{parent_type}/{parent_id}", response_model=GenericDocumentResponse, status_code=201)
def upload_document(parent_type: str, parent_id: int, file: UploadFile = File(...),
                     description: Optional[str] = None, request: Request = None,
                     db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Same validation discipline as every other document type in this
    app: extension allowlist, MIME check, a real streamed byte count
    against the size limit (never trusting Content-Length), and a
    random server-side filename never derived from user input."""
    _validate_parent_type(parent_type)
    _get_parent_or_404(db, parent_type, parent_id)

    original_name = file.filename or "document"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in DOC_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File must be a PDF, DOC, DOCX, XLSX, JPG, or PNG (got .{ext or 'unknown'}).",
        )
    if file.content_type not in DOC_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    backend = get_storage_backend()
    stored_filename = f"documents/{parent_type}/{secrets.token_hex(16)}.{ext}"

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

    document = GenericDocument(
        parent_type=parent_type, parent_id=parent_id, original_filename=original_name,
        stored_filename=stored_filename, content_type=file.content_type, description=description,
        uploaded_by=str(auth.get("user_id", "")),
        storage_backend=storage_ref.backend, drive_file_id=storage_ref.drive_file_id,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            backend.delete(storage_ref)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to save the document record.")
    db.refresh(document)
    if request is not None:
        log_action(db, request, user_id=auth.get("user_id"), action="upload_document", module_name="documents",
                   record_id=document.id, new_value={"parent_type": parent_type, "parent_id": parent_id, "filename": original_name})
    return document


@router.get("/{parent_type}/{parent_id}/{document_id}/download")
def download_document(parent_type: str, parent_id: int, document_id: int, db: Session = Depends(get_db),
                       auth=Depends(get_current_user)):
    """Object-level check: the document must actually belong to BOTH
    parent_type and parent_id in the URL, not just exist by
    document_id - the same IDOR protection already established for
    every other document type in this app."""
    _validate_parent_type(parent_type)
    _check_read_permission(parent_type, auth.get("role", "user"))
    document = db.query(GenericDocument).filter(
        GenericDocument.id == document_id, GenericDocument.parent_type == parent_type,
        GenericDocument.parent_id == parent_id,
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


@router.delete("/{parent_type}/{parent_id}/{document_id}", status_code=204)
def delete_document(parent_type: str, parent_id: int, document_id: int, request: Request,
                     db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    _validate_parent_type(parent_type)
    document = db.query(GenericDocument).filter(
        GenericDocument.id == document_id, GenericDocument.parent_type == parent_type,
        GenericDocument.parent_id == parent_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    backend, storage_ref = get_storage_backend_for_record(document)
    old_value = {"parent_type": parent_type, "parent_id": parent_id, "filename": document.original_filename}
    db.delete(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete the document record.")
    try:
        backend.delete(storage_ref)
    except Exception:
        logger.error(f"Orphaned file after generic document {document_id} delete: {storage_ref}")
    log_action(db, request, user_id=auth.get("user_id"), action="delete_document", module_name="documents",
               record_id=document_id, old_value=old_value)
