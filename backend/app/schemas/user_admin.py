from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreateAdmin(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    role: str = "user"


class UserUpdateAdmin(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserAdminResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    is_active: bool
    cannot_be_deleted: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
