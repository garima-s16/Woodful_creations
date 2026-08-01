from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.schemas.interview import InterviewCreate, InterviewUpdate, InterviewResponse
from app.models.interview import Interview
from app.core.database import get_db
from app.core.security import verify_token
from typing import List

router = APIRouter(prefix="/api/interviews", tags=["recruitment"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[InterviewResponse])
def get_interviews(candidate_id: int = Query(None), db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(Interview)
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    return query.all()

@router.post("/", response_model=InterviewResponse)
def schedule_interview(interview: InterviewCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_interview = Interview(**interview.dict())
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    return db_interview

@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(interview_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview

@router.patch("/{interview_id}", response_model=InterviewResponse)
def update_interview(interview_id: int, interview: InterviewUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    update_data = interview.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_interview, key, value)
    
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    return db_interview

@router.delete("/{interview_id}")
def cancel_interview(interview_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    db.delete(interview)
    db.commit()
    return {"message": "Interview cancelled"}