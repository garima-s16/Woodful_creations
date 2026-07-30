from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.schemas.user import LoginResponse, UserLogin, UserCreate, UserResponse
from app.core.database import get_db
from app.core.security import create_access_token, verify_token
from app.models.user import User
import logging

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


@router.post("/login", response_model=LoginResponse)
def login(request: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    token = create_access_token({"user_id": str(user.id), "email": user.email, "role": user.role})
    logger.info("User logged in: %s", user.username)

    return LoginResponse(
        token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(request: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.email == request.email) | (User.username == request.username)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )

    hashed_password = pwd_context.hash(request.password)
    new_user = User(
        email=request.email,
        username=request.username,
        full_name=request.full_name,
        password_hash=hashed_password,
        role="user",
        is_active=True,
        is_deleted=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("New user registered: %s", new_user.username)

    token = create_access_token({"user_id": str(new_user.id), "email": new_user.email, "role": new_user.role})

    return LoginResponse(
        token=token,
        user=UserResponse.model_validate(new_user)
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)