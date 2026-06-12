"""
Payment Tracking Routes - Admin Only
Track payments Woodful Creations owes to suppliers/vendors
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, User, UserRole
from app.routes.auth import get_current_user, get_master_user

router = APIRouter()

# ===================== ADMIN-ONLY PAYMENT ROUTES =====================

@router.get("/", tags=["Payments"])
async def get_payments(
    master_user: User = Depends(get_master_user),
    db: Session = Depends(get_db)
):
    """Get all payments (master users only)"""
    
    return {
        "message": "Payments endpoint - admin only",
        "status": "upcoming"
    }

@router.post("/", tags=["Payments"])
async def create_payment(
    master_user: User = Depends(get_master_user),
    db: Session = Depends(get_db)
):
    """Create a new payment entry (master users only)"""
    
    return {
        "message": "Payment creation - admin only",
        "status": "upcoming"
    }