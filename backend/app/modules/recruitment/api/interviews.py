from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.platform.database.database import get_db
from app.platform.security.security import require_role
from app.modules.recruitment.models import Interview
from app.modules.recruitment.schemas import InterviewCreate, InterviewUpdate, InterviewResponse
from app.platform.database.id_generator import generate_business_id

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


@router.get("/", response_model=List[InterviewResponse])
def list_interviews(candidate_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    query = db.query(Interview)
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    return query.order_by(Interview.scheduled_date.desc()).all()


@router.post("/", response_model=InterviewResponse, status_code=201)
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


@router.put("/{interview_id}", response_model=InterviewResponse)
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
