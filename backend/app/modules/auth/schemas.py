"""Auth module schemas: self-service (register/login/password-reset)
and admin (create/update/list users) request/response shapes."""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str


class UserLogin(BaseModel):
    identifier: str  # email OR username
    password: str


class ForgotPasswordRequest(BaseModel):
    identifier: str  # email OR username


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserResponse(UserBase):
    id: int
    role: str
    employee_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Web login response. The JWT itself lives only in the HttpOnly cookie -
    it is never included here, so it's never visible to page JavaScript."""
    user: UserResponse


class MobileLoginResponse(BaseModel):
    """Native app login response. No cookie is usable by a native HTTP
    client in the same way a browser uses one, so the token is returned
    directly here for the app to store in the OS keychain (Keychain on iOS,
    Keystore on Android) - never in plain app storage or localStorage."""
    token: str
    user: UserResponse


class UserCreateAdmin(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    role: str = "user"
    employee_id: Optional[int] = None


class UserUpdateAdmin(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserAdminResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    employee_id: Optional[int] = None
    is_active: bool
    cannot_be_deleted: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
