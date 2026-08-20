from typing import List, Optional
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from app.core.audit import log_action
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import require_role
from app.core.config import settings
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateUpdate, CandidateResponse
from app.utils.id_generator import generate_short_id

from app.utils.validators import validate_file_signature
from app.core.storage import get_storage_backend


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
        candidate = Candidate(**data.dict(), business_id=generate_short_id(db))
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


def _delete_stored_resume_file(candidate: Candidate) -> None:
    if candidate.resume_stored_filename:
        get_storage_backend().delete(candidate.resume_stored_filename)


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
        backend.save(stored_filename, b"".join(chunks))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save the uploaded file.")

    _delete_stored_resume_file(candidate)  # replace, not accumulate, if one already existed

    candidate.resume_stored_filename = stored_filename
    candidate.resume_original_filename = original_name
    candidate.resume_content_type = file.content_type
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/{candidate_id}/resume")
def download_resume(candidate_id: int, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate or not candidate.resume_stored_filename:
        raise HTTPException(status_code=404, detail="No resume file uploaded for this candidate.")
    backend = get_storage_backend()
    if not backend.exists(candidate.resume_stored_filename):
        raise HTTPException(status_code=404, detail="Resume file is missing from storage.")
    file_path = backend.local_path_for_serving(candidate.resume_stored_filename)
    return FileResponse(
        file_path, media_type=candidate.resume_content_type or "application/octet-stream",
        filename=candidate.resume_original_filename or "resume",
    )


@router.delete("/{candidate_id}/resume", response_model=CandidateResponse)
def delete_resume(candidate_id: int, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    _delete_stored_resume_file(candidate)
    candidate.resume_stored_filename = None
    candidate.resume_original_filename = None
    candidate.resume_content_type = None
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    log_action(db, request, user_id=auth.get("user_id"), action="delete_resume", module_name="candidates",
               record_id=candidate_id)
    return candidate
