from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.schemas.candidate import CandidateCreate, CandidateUpdate, CandidateResponse
from app.models.candidate import Candidate
from app.core.database import get_db
from app.core.security import verify_token
from typing import List

router = APIRouter(prefix="/api/candidates", tags=["recruitment"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[CandidateResponse])
def get_candidates(status: str = None, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(Candidate)
    if status:
        query = query.filter(Candidate.status == status)
    return query.all()

@router.post("/", response_model=CandidateResponse)
def create_candidate(candidate: CandidateCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_candidate = Candidate(**candidate.model_dump())
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@router.patch("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(candidate_id: int, candidate: CandidateUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = candidate.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_candidate, key, value)
    
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted"}