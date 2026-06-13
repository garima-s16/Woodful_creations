from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.schemas.user import LoginResponse, UserLogin
from app.core.database import get_db
from app.core.security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

in_memory_users = {
    "nikhils@woodful.com": {"id": "1", "email": "nikhils@woodful.com", "password": "Nikhil*27", "username": "nikhils", "name": "Nikhil", "role": "master"},
    "garimas@woodful.com": {"id": "2", "email": "garimas@woodful.com", "password": "Gullak*16", "username": "garimas", "name": "Garima", "role": "master"},
    "shwetav@woodful.com": {"id": "3", "email": "shwetav@woodful.com", "password": "Shweta*05", "username": "shwetav", "name": "Shweta", "role": "user"}
}

@router.post("/login", response_model=LoginResponse)
def login(request: UserLogin, db: Session = Depends(get_db)):
    user = in_memory_users.get(request.email)
    
    if not user or user["password"] != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"user_id": user["id"], "email": user["email"], "role": user["role"]})
    
    return LoginResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "full_name": user["name"],
            "role": user["role"],
            "is_active": True,
            "created_at": "2026-01-01T00:00:00"
        }
    )