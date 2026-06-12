"""User model"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base

class UserRole(str, enum.Enum):
    """User role enumeration"""
    MASTER = "master"
    HR = "hr"
    SALES = "sales"
    DELIVERY = "delivery"
    USER = "user"

class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, index=True)
    is_active = Column(Boolean, default=True)
    is_master = Column(Boolean, default=False)  # True for Nikhil & Garima
    phone = Column(String(20), nullable=True)
    profile_image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    deletion_status = Column(String(20), default="active")  # 'active', 'soft_deleted'
    
    # Relationships
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    
    class Config:
        from_attributes = True

class UserPermission(Base):
    """User permissions model"""
    __tablename__ = "user_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    module_name = Column(String(100), nullable=False)  # 'inventory', 'estimates', etc.
    permission_level = Column(String(50), nullable=False)  # 'view', 'edit', 'delete', 'admin'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="permissions")
    
    class Config:
        from_attributes = True
