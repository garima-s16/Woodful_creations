from typing import List, Optional
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.core.config import settings
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateUpdate, CandidateResponse
from app.utils.id_generator import generate_short_id

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
RESUME_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIRECTORY, "resumes")


@router.get("/", response_model=List[CandidateResponse])
def list_candidates(status: Optional[str] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    query = db.query(Candidate)
    if status:
        query = query.filter(Candidate.status == status)
    return query.order_by(Candidate.created_at.desc()).all()


@router.post("/", response_model=CandidateResponse, status_code=201)
def create_candidate(data: CandidateCreate, db: Session = Depends(get_db),
                      auth=Depends(require_role("master", "manager"))):
    for _ in range(5):
        candidate = Candidate(**data.dict(), business_id=generate_short_id())
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
                   auth=Depends(require_role("master", "manager"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(candidate_id: int, data: CandidateUpdate, db: Session = Depends(get_db),
                      auth=Depends(require_role("master", "manager"))):
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
        old_path = os.path.join(RESUME_UPLOAD_DIR, candidate.resume_stored_filename)
        if os.path.exists(old_path):
            os.remove(old_path)


@router.post("/{candidate_id}/resume", response_model=CandidateResponse)
def upload_resume(candidate_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                   auth=Depends(require_role("master", "manager"))):
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

    os.makedirs(RESUME_UPLOAD_DIR, exist_ok=True)
    # A random server-side filename - never the user-supplied one, which
    # could otherwise be used to attempt a path-traversal or to collide
    # with/overwrite another candidate's stored file.
    stored_filename = f"{secrets.token_hex(16)}.{ext}"
    stored_path = os.path.join(RESUME_UPLOAD_DIR, stored_filename)

    size = 0
    try:
        with open(stored_path, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.MAX_UPLOAD_SIZE:
                    out.close()
                    os.remove(stored_path)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(stored_path):
            os.remove(stored_path)
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
                     auth=Depends(require_role("master", "manager"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate or not candidate.resume_stored_filename:
        raise HTTPException(status_code=404, detail="No resume file uploaded for this candidate.")
    file_path = os.path.join(RESUME_UPLOAD_DIR, candidate.resume_stored_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resume file is missing from storage.")
    return FileResponse(
        file_path, media_type=candidate.resume_content_type or "application/octet-stream",
        filename=candidate.resume_original_filename or "resume",
    )


@router.delete("/{candidate_id}/resume", response_model=CandidateResponse)
def delete_resume(candidate_id: int, db: Session = Depends(get_db),
                   auth=Depends(require_role("master", "manager"))):
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
    return candidate
