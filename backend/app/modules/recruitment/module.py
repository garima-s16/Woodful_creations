"""Recruitment domain models: Candidate and Interview.

Consolidated from candidate.py + interview.py. Kept as a single small domain module since Interview has a hard
foreign-key dependency on Candidate and both are always used together.
"""
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.platform.database import BaseModel
from pydantic import BaseModel as PydanticBaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re
from typing import List, Optional
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Response
from app.platform.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import require_role
from app.platform.config import settings
from app.platform.ids import generate_business_id
from app.shared import validate_file_signature
from app.platform.storage import get_storage_backend, get_storage_backend_for_record
from fastapi import APIRouter, Depends, HTTPException, Query


class Candidate(BaseModel):
    __tablename__ = "candidates"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    position = Column(String(100), nullable=True)
    experience = Column(String(100), nullable=True)
    # Backward-compatible free-text URL, still accepted if a candidate's
    # resume genuinely lives externally (e.g. a LinkedIn/portfolio link)
    # rather than being uploaded as a file.
    resume_url = Column(String(500), nullable=True)
    # An actually-uploaded file (P7) - stored under a random server-side
    # filename (never the user-supplied one, to avoid any path/overwrite
    # risk), with the real original filename kept separately for display
    # and for the Content-Disposition header on download.
    resume_stored_filename = Column(String(255), nullable=True)
    resume_original_filename = Column(String(255), nullable=True)
    resume_content_type = Column(String(100), nullable=True)
    storage_backend = Column(String(20), nullable=False, default="local")
    drive_file_id = Column(String(255), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="Applied", index=True)  # Applied/Shortlisted/Selected/Rejected
    remarks = Column(Text, nullable=True)

    interviews = relationship("Interview", back_populates="candidate")


class Interview(BaseModel):
    __tablename__ = "interviews"

    business_id = Column(String(10), unique=True, index=True, nullable=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    round = Column(String(50), nullable=True)
    scheduled_date = Column(DateTime, nullable=False, index=True)
    interviewer = Column(String(255), nullable=True)
    feedback = Column(Text, nullable=True)  # free-form notes, kept alongside the structured fields below
    status = Column(String(20), nullable=False, default="Scheduled", index=True)  # Scheduled/Completed/Rescheduled/Cancelled

    # Structured feedback (P8) - was a single free-text box; a real
    # hiring decision needs more than one paragraph to be useful to
    # whoever reads it later.
    overall_rating = Column(Integer, nullable=True)  # 1-5
    technical_rating = Column(Integer, nullable=True)  # 1-5
    communication_rating = Column(Integer, nullable=True)  # 1-5
    culture_fit_rating = Column(Integer, nullable=True)  # 1-5
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)
    recommendation = Column(String(20), nullable=True)  # Strong Hire/Hire/Hold/Reject

    candidate = relationship("Candidate", back_populates="interviews")


"""Recruitment domain schemas - candidates and their interviews.
Consolidated from separate candidate.py/interview.py modules: the two
are tightly coupled (an interview always references a candidate) and
together form one small, coherent "recruitment" feature area, not two
independent concerns."""


EXPERIENCE_OPTIONS = ["Fresher", "< 1 year", "1-2 years", "2-5 years", "5-10 years", "10+ years"]


INDIAN_MOBILE_PATTERN = re.compile(r"^[6-9][0-9]{9}$")


class CandidateBase(PydanticBaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    experience: Optional[str] = None
    # Backward-compatible free-text URL (e.g. a LinkedIn/portfolio link);
    # the actual uploaded file is tracked separately via
    # resume_stored_filename/resume_original_filename, set only through
    # the dedicated upload endpoint, never through this create/update body.
    resume_url: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_indian_mobile(cls, v):
        if v is None or v == "":
            return v
        if not INDIAN_MOBILE_PATTERN.match(v):
            raise ValueError("Mobile number must be a valid 10-digit Indian number (starting 6-9)")
        return v

    @field_validator("experience")
    @classmethod
    def validate_experience_option(cls, v):
        if v is None or v == "":
            return v
        if v not in EXPERIENCE_OPTIONS:
            raise ValueError(f"Experience must be one of: {', '.join(EXPERIENCE_OPTIONS)}")
        return v


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(PydanticBaseModel):
    status: Optional[str] = None
    remarks: Optional[str] = None


class CandidateResponse(CandidateBase):
    id: int
    business_id: str
    status: str
    resume_original_filename: Optional[str] = None
    resume_content_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


RECOMMENDATION_OPTIONS = ["Strong Hire", "Hire", "Hold", "Reject"]


class InterviewBase(PydanticBaseModel):
    candidate_id: int
    round: Optional[str] = None
    scheduled_date: datetime
    interviewer: Optional[str] = None


class InterviewCreate(InterviewBase):
    pass


class InterviewFeedbackFields(PydanticBaseModel):
    """Shared by InterviewUpdate (feedback is entered via the same
    update endpoint as scheduling changes - there's one interview
    record, not a separate feedback resource) and validated the same
    way wherever it's set."""
    overall_rating: Optional[int] = None
    technical_rating: Optional[int] = None
    communication_rating: Optional[int] = None
    culture_fit_rating: Optional[int] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    observations: Optional[str] = None
    recommendation: Optional[str] = None

    @field_validator("overall_rating", "technical_rating", "communication_rating", "culture_fit_rating")
    @classmethod
    def validate_rating_range(cls, v):
        if v is None:
            return v
        if not (1 <= v <= 5):
            raise ValueError("Ratings must be between 1 and 5")
        return v

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v):
        if v is None or v == "":
            return v
        if v not in RECOMMENDATION_OPTIONS:
            raise ValueError(f"Recommendation must be one of: {', '.join(RECOMMENDATION_OPTIONS)}")
        return v


class InterviewUpdate(InterviewFeedbackFields):
    status: Optional[str] = None
    feedback: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class InterviewResponse(InterviewBase, InterviewFeedbackFields):
    id: int
    business_id: str
    status: str
    feedback: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- api/routes.py (candidates + interviews) ---
"""Recruitment domain API routes: candidates (candidates_router,
incl. resume upload/download) and interviews (interviews_router).
Combines the former candidates.py and interviews.py."""

logger = logging.getLogger(__name__)


candidates_router = APIRouter(prefix="/api/candidates", tags=["candidates"])


RESUME_ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}


RESUME_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}


@candidates_router.get("/", response_model=List[CandidateResponse])
def list_candidates(status: Optional[str] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    query = db.query(Candidate)
    if status:
        query = query.filter(Candidate.status == status)
    return query.order_by(Candidate.created_at.desc()).all()


@candidates_router.post("/", response_model=CandidateResponse, status_code=201)
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


@candidates_router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@candidates_router.put("/{candidate_id}", response_model=CandidateResponse)
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


@candidates_router.post("/{candidate_id}/resume", response_model=CandidateResponse)
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


@candidates_router.get("/{candidate_id}/resume")
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


@candidates_router.delete("/{candidate_id}/resume", response_model=CandidateResponse)
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


interviews_router = APIRouter(prefix="/api/interviews", tags=["interviews"])


@interviews_router.get("/", response_model=List[InterviewResponse])
def list_interviews(candidate_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    query = db.query(Interview)
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    return query.order_by(Interview.scheduled_date.desc()).all()


@interviews_router.post("/", response_model=InterviewResponse, status_code=201)
def schedule_interview(data: InterviewCreate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master"))):
    for _ in range(5):
        interview = Interview(**data.dict(), business_id=generate_business_id(db))
        db.add(interview)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(interview)
        return interview
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@interviews_router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(interview_id: int, data: InterviewUpdate, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(interview, field, value)
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview
