from sqlalchemy import Column, String, Boolean, DateTime
from app.models.base import BaseModel
from datetime import datetime

class User(BaseModel):
    __tablename__ = "users"
    
    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(500), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(50), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    profile_picture = Column(String(500), nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    otp_secret = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)