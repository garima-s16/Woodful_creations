from sqlalchemy import Column, Integer, String, DateTime, Float
from datetime import datetime, date
from app.core.database import Base

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, index=True)
    attendance_date = Column(DateTime, index=True)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    hours_worked = Column(Float, default=0.0)
    status = Column(String, default="present")
    created_at = Column(DateTime, default=datetime.utcnow)