from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import require_role, hash_password
from app.platform.audit.audit import log_action
from app.modules.auth.models import User
from app.modules.hr.models import Employee
from app.modules.auth.schemas import UserCreateAdmin, UserUpdateAdmin, UserAdminResponse

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
    if data.role != "master":
        # Every RBAC "own records only" check across the app (attendance,
        # leaves, salary slips, tasks, analytics, dashboard) resolves
        # "own" via auth.employee_id. A non-master account with no
        # employee_id doesn't just lack data of its own - the resulting
        # None makes several of those same filters no-op, returning
        # EVERY employee's records instead of none. Enforcing the link
        # here, at the one place User rows are created, is what makes
        # "non-master implies employee_id is set" an actual invariant
        # rather than an assumption those endpoints depend on.
        if not data.employee_id:
            raise HTTPException(status_code=400, detail="A non-master account must be linked to an employee.")
        if not db.query(Employee).filter(Employee.id == data.employee_id).first():
            raise HTTPException(status_code=400, detail="employee_id does not match an existing employee.")

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


def _active_master_count(db: Session, exclude_user_id: Optional[int] = None) -> int:
    query = db.query(User).filter(User.role == "master", User.is_active.is_(True), User.is_deleted.is_(False))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


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

    # Same invariant as create_user: whatever this update leaves the
    # account as (role may change, employee_id may change, or neither),
    # a non-master result must end up with a real employee_id - never
    # silently demoted-and-unlinked, or unlinked-in-place, since every
    # "own records only" filter elsewhere depends on it being set.
    final_role = update_data.get("role", user.role)
    final_employee_id = update_data.get("employee_id", user.employee_id)
    if final_role != "master":
        if not final_employee_id:
            raise HTTPException(status_code=400, detail="A non-master account must be linked to an employee.")
        if not db.query(Employee).filter(Employee.id == final_employee_id).first():
            raise HTTPException(status_code=400, detail="employee_id does not match an existing employee.")

    # The actual requirement is - never allow the LAST active
    # master to be deactivated or demoted, for ANY master account, not
    # just ones someone remembered to flag cannot_be_deleted on. The
    # count excludes THIS user, so "the only other master is also
    # being deactivated in the same request" still correctly blocks -
    # what matters is how many would remain active afterward.
    is_deactivating = user.role == "master" and update_data.get("is_active") is False
    is_demoting = user.role == "master" and "role" in update_data and update_data["role"] != "master"
    if (is_deactivating or is_demoting) and _active_master_count(db, exclude_user_id=user.id) == 0:
        action = "deactivated" if is_deactivating else "demoted from Master"
        raise HTTPException(status_code=403, detail=f"This is the last active Master account and cannot be {action}.")

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
    # Master accounts are never deletable through this endpoint, full
    # stop - not just the last one. A Master who genuinely needs
    # removing should be deactivated instead (via update_user), the
    # same pattern this app already uses elsewhere for anything with
    # real significance rather than hard-deleting it.
    if user.role == "master":
        raise HTTPException(status_code=403, detail="Master accounts cannot be deleted. Deactivate the account instead.")

    user.is_deleted = True
    user.is_active = False
    db.add(user)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_user", module_name="users", record_id=user.id)
