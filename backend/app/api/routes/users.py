from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role, hash_password
from app.core.audit import log_action
from app.models.user import User
from app.schemas.user_admin import UserCreateAdmin, UserUpdateAdmin, UserAdminResponse

router = APIRouter(prefix="/api/users", tags=["users"])

ALLOWED_ROLES = {"master", "user"}


@router.get("/", response_model=List[UserAdminResponse])
def list_users(role: Optional[str] = Query(None), db: Session = Depends(get_db),
                auth=Depends(require_role("master"))):
    query = db.query(User).filter(User.is_deleted.is_(False))
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.username).all()


@router.post("/", response_model=UserAdminResponse, status_code=201)
def create_user(data: UserCreateAdmin, request: Request, db: Session = Depends(get_db),
                 auth=Depends(require_role("master"))):
    if data.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ALLOWED_ROLES}")
    if db.query(User).filter((User.username == data.username) | (User.email == data.email)).first():
        raise HTTPException(status_code=400, detail="Username or email already exists")

    user = User(
        username=data.username, email=data.email, full_name=data.full_name, phone=data.phone,
        role=data.role, employee_id=data.employee_id, password_hash=hash_password(data.password), is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, request, user_id=auth.get("user_id"), action="create_user", module_name="users", record_id=user.id)
    return user


@router.get("/{user_id}", response_model=UserAdminResponse)
def get_user(user_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserAdminResponse)
def update_user(user_id: int, data: UserUpdateAdmin, request: Request, db: Session = Depends(get_db),
                 auth=Depends(require_role("master"))):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.dict(exclude_unset=True)
    if "role" in update_data and update_data["role"] not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ALLOWED_ROLES}")
    if user.cannot_be_deleted and update_data.get("is_active") is False:
        raise HTTPException(status_code=403, detail="This account is protected and cannot be deactivated")

    for field, value in update_data.items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, request, user_id=auth.get("user_id"), action="update_user", module_name="users", record_id=user.id, new_value=update_data)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.cannot_be_deleted:
        raise HTTPException(status_code=403, detail="This account is protected and cannot be deleted")
    if user.id == auth.get("user_id"):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    user.is_deleted = True
    user.is_active = False
    db.add(user)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_user", module_name="users", record_id=user.id)
