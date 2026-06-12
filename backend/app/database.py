"""
PostgreSQL Database Configuration and Session Management
"""

import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://woodful_user:password@localhost/woodful_creations")

# Create engine
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Dependency
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database
async def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

# Base model class
class BaseModel(Base):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# User Model
class User(BaseModel):
    __tablename__ = "users"
    
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_master = Column(Boolean, default=False)  # Master user: Nikhil, Garima
    role = Column(String, default="user")  # admin, manager, employee, user
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)

# Stock Item Model
class StockItem(BaseModel):
    __tablename__ = "stock_items"
    
    sku = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    description = Column(Text, nullable=True)
    quantity = Column(Integer, default=0)
    min_stock = Column(Integer, default=10)
    reorder_qty = Column(Integer, default=50)
    unit_cost = Column(Float)
    selling_price = Column(Float)
    supplier = Column(String, nullable=True)
    warehouse_location = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    
# Stock History Model
class StockHistory(BaseModel):
    __tablename__ = "stock_history"
    
    stock_item_id = Column(Integer, ForeignKey("stock_items.id"))
    transaction_type = Column(String)  # 'add', 'remove', 'adjustment', 'return'
    quantity_changed = Column(Integer)
    reason = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    performed_by = Column(Integer, ForeignKey("users.id"))

# Client Model
class Client(BaseModel):
    __tablename__ = "clients"
    
    name = Column(String, index=True)
    email = Column(String, unique=True)
    phone = Column(String)
    company = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    payment_terms = Column(String, default="Net 30")
    credit_limit = Column(Float, default=0)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))

# Estimate Model
class Estimate(BaseModel):
    __tablename__ = "estimates"
    
    estimate_number = Column(String, unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    status = Column(String, default="draft")  # draft, sent, approved, rejected
    total_amount = Column(Float)
    discount_percentage = Column(Float, default=0)
    tax_percentage = Column(Float, default=18)  # GST
    notes = Column(Text, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))

# Chat Message Model
class ChatMessage(BaseModel):
    __tablename__ = "chat_messages"
    
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(Text)
    response = Column(Text, nullable=True)
    message_type = Column(String, default="text")  # text, command, system
    is_processed = Column(Boolean, default=False)

# Alert Model
class Alert(BaseModel):
    __tablename__ = "alerts"
    
    user_id = Column(Integer, ForeignKey("users.id"))
    alert_type = Column(String)  # low_stock, eta_nearing, payment_due, etc
    title = Column(String)
    message = Column(Text)
    related_item_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False)
    priority = Column(String, default="normal")  # low, normal, high, urgent