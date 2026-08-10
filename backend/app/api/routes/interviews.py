from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models.interview import Interview
from app.schemas.interview import InterviewCreate, InterviewUpdate, InterviewResponse

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


@router.get("/", response_model=List[InterviewResponse])
def list_interviews(candidate_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(require_role("master", "manager"))):
    query = db.query(Interview)
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    return query.order_by(Interview.scheduled_date.desc()).all()


@router.post("/", response_model=InterviewResponse, status_code=201)
def schedule_interview(data: InterviewCreate, db: Session = Depends(get_db),
                        auth=Depends(require_role("master", "manager"))):
    interview = Interview(**data.dict())
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(interview_id: int, data: InterviewUpdate, db: Session = Depends(get_db),
                      auth=Depends(require_role("master", "manager"))):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(interview, field, value)
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview
