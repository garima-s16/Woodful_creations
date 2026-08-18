from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey

from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(500), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(50), default="user", nullable=False)
    # Links a login account to the real Employee record it belongs to -
    # not every user account is necessarily an employee (e.g. an
    # external accountant), so this is nullable. "My tasks" and similar
    # self-service features resolve through this FK, never by matching
    # full_name against Employee.name.
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    profile_picture = Column(String(500), nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    otp_secret = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)
    cannot_be_deleted = Column(Boolean, default=False, nullable=False)  # protects seeded master accounts
