import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password, get_current_user
from app.core.rate_limit import rate_limit
from app.core.audit import log_action
from app.core.config import settings
from app.models.user import User
from app.schemas.user import LoginResponse, MobileLoginResponse, UserLogin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _authenticate(request: UserLogin, db: Session) -> User:
    user = db.query(User).filter(
        (User.email == request.identifier) | (User.username == request.identifier),
        User.is_deleted.is_(False),
    ).first()

    if not user:
        logger.info("Login failed: no account for identifier %r", request.identifier)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not verify_password(request.password, user.password_hash):
        logger.info("Login failed: wrong password for user_id %s", user.id)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    return user


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "employee_id": user.employee_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(rate_limit("login", settings.RATE_LIMIT_LOGIN_PER_MINUTE))])
def login(request: UserLogin, response: Response, http_request: Request, db: Session = Depends(get_db)):
    """Web login. The token is set as an HttpOnly cookie only - it is never
    present in this JSON response, so page JavaScript can never read it."""
    user = _authenticate(request, db)

    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "employee_id": user.employee_id})
    _set_auth_cookie(response, token)
    log_action(db, http_request, user_id=user.id, action="login", module_name="auth")

    return LoginResponse(user=_user_payload(user))


@router.post("/login/mobile", response_model=MobileLoginResponse, dependencies=[Depends(rate_limit("login", settings.RATE_LIMIT_LOGIN_PER_MINUTE))])
def login_mobile(request: UserLogin, http_request: Request, db: Session = Depends(get_db)):
    """Native app login. Returns the token directly for the app to store in
    the OS keychain (Keychain/Keystore) and send back as a Bearer header -
    no HttpOnly cookie is set here since a native HTTP client can't rely on
    browser cookie handling the same way."""
    user = _authenticate(request, db)

    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "employee_id": user.employee_id})
    log_action(db, http_request, user_id=user.id, action="login", module_name="auth")

    return MobileLoginResponse(token=token, user=_user_payload(user))


@router.post("/logout")
def logout(response: Response, http_request: Request, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")
    log_action(db, http_request, user_id=user.get("user_id"), action="logout", module_name="auth")
    return {"message": "Logged out"}


@router.get("/me")
def me(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_user = db.query(User).filter(User.id == user.get("user_id"), User.is_deleted.is_(False)).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username,
        "full_name": db_user.full_name,
        "role": db_user.role,
        "employee_id": db_user.employee_id,
        "is_active": db_user.is_active,
    }
