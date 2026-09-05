from typing import List, Optional
import secrets
import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Response
from app.platform.audit.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import require_role
from app.platform.configuration.config import settings
from app.modules.recruitment.models import Candidate
from app.modules.recruitment.schemas import CandidateCreate, CandidateUpdate, CandidateResponse
from app.platform.database.id_generator import generate_business_id

from app.shared.validators import validate_file_signature
from app.platform.storage.storage import get_storage_backend, get_storage_backend_for_record


router = APIRouter(prefix="/api/candidates", tags=["candidates"])

# Resume uploads use their own narrower allowlist (P7: "PDF, DOC, DOCX")
# rather than the app-wide ALLOWED_EXTENSIONS in config.py, which also
# includes image/spreadsheet types that make no sense for a resume.
RESUME_ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
RESUME_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}


@router.get("/", response_model=List[CandidateResponse])
def list_candidates(status: Optional[str] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    query = db.query(Candidate)
    if status:
        query = query.filter(Candidate.status == status)
    return query.order_by(Candidate.created_at.desc()).all()


@router.post("/", response_model=CandidateResponse, status_code=201)
def create_candidate(data: CandidateCreate, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    for _ in range(5):
        candidate = Candidate(**data.dict(), business_id=generate_business_id(db))
        db.add(candidate)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(candidate)
        return candidate
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(candidate_id: int, data: CandidateUpdate, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(candidate, field, value)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


class _ResumeStorageRecord:
    """Adapts Candidate's resume_* column names to the plain
    stored_filename/storage_backend/drive_file_id shape
    get_storage_backend_for_record expects - Candidate genuinely uses
    a different naming convention from the other three document
    tables (it has one resume per candidate, not a list of documents),
    so this is a thin, local view rather than a schema change."""
    def __init__(self, candidate: Candidate):
        self.stored_filename = candidate.resume_stored_filename
        self.storage_backend = candidate.storage_backend
        self.drive_file_id = candidate.drive_file_id


@router.post("/{candidate_id}/resume", response_model=CandidateResponse)
def upload_resume(candidate_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Upload (or replace) a candidate's resume file. Validates the file
    extension, the browser-reported MIME type, and the actual size read
    from disk (a Content-Length header can be spoofed or absent - the
    real byte count read while streaming to disk cannot)."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    original_name = file.filename or "resume"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in RESUME_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Resume must be a PDF, DOC, or DOCX file (got .{ext or 'unknown'}).",
        )
    if file.content_type not in RESUME_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    backend = get_storage_backend()
    # A random server-side filename - never the user-supplied one, which
    # could otherwise be used to attempt a path-traversal or to collide
    # with/overwrite another candidate's stored file.
    stored_filename = f"resumes/{secrets.token_hex(16)}.{ext}"

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

    # Capture the OLD file's reference now, while candidate still holds
    # the old values - once the fields below are overwritten, this is
    # the only chance to know what the old file even was.
    had_old_resume = bool(candidate.resume_stored_filename)
    if had_old_resume:
        old_backend, old_storage_ref = get_storage_backend_for_record(_ResumeStorageRecord(candidate))

    candidate.resume_stored_filename = stored_filename
    candidate.resume_original_filename = original_name
    candidate.resume_content_type = file.content_type
    candidate.storage_backend = storage_ref.backend
    candidate.drive_file_id = storage_ref.drive_file_id
    db.add(candidate)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # DB never actually pointed to the new file - clean it up. The
        # old file was never touched, so it's still exactly where it
        # was; the candidate record (after rollback) still correctly
        # references it.
        try:
            backend.delete(storage_ref)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to save the resume record.")
    db.refresh(candidate)

    # Only now, after the DB durably points to the new file, remove the
    # old one. A failure here just orphans a file - the DB is already
    # consistent, so this is never surfaced as a request failure.
    if had_old_resume:
        try:
            old_backend.delete(old_storage_ref)
        except Exception:
            logger.error(f"Orphaned old resume after candidate {candidate_id} resume replacement: {old_storage_ref}")
    return candidate


@router.get("/{candidate_id}/resume")
def download_resume(candidate_id: int, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate or not candidate.resume_stored_filename:
        raise HTTPException(status_code=404, detail="No resume file uploaded for this candidate.")
    backend, storage_ref = get_storage_backend_for_record(_ResumeStorageRecord(candidate))
    if not backend.exists(storage_ref):
        raise HTTPException(status_code=404, detail="Resume file is missing from storage.")
    file_bytes = backend.read(storage_ref)
    return Response(
        content=file_bytes, media_type=candidate.resume_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{candidate.resume_original_filename or "resume"}"'},
    )


@router.delete("/{candidate_id}/resume", response_model=CandidateResponse)
def delete_resume(candidate_id: int, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    had_resume = bool(candidate.resume_stored_filename)
    if had_resume:
        backend, storage_ref = get_storage_backend_for_record(_ResumeStorageRecord(candidate))
    candidate.resume_stored_filename = None
    candidate.resume_original_filename = None
    candidate.resume_content_type = None
    db.add(candidate)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete the resume record.")
    db.refresh(candidate)
    if had_resume:
        try:
            backend.delete(storage_ref)
        except Exception:
            logger.error(f"Orphaned resume file after candidate {candidate_id} resume delete: {storage_ref}")
    log_action(db, request, user_id=auth.get("user_id"), action="delete_resume", module_name="candidates",
               record_id=candidate_id)
    return candidate
