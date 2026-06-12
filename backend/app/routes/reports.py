"""
Reports and Analytics Routes
Generate various business reports and analytics
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import (
    get_db, User, InventoryItem, ClientPayment, 
    ClientProduct, Client, InventoryStatus
)
from app.routes.auth import get_current_user

router = APIRouter()

@router.get("/inventory/summary", tags=["Reports"])
async def inventory_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get inventory summary report"""
    
    total_items = db.query(InventoryItem).filter(
        InventoryItem.status == InventoryStatus.ACTIVE
    ).count()
    
    total_value = db.query(func.sum(
        InventoryItem.quantity * InventoryItem.unit_cost
    )).filter(InventoryItem.status == InventoryStatus.ACTIVE).scalar() or 0
    
    low_stock = db.query(InventoryItem).filter(
        InventoryItem.quantity <= InventoryItem.min_stock,
        InventoryItem.status == InventoryStatus.ACTIVE
    ).count()
    
    categories = db.query(
        InventoryItem.category, 
        func.count(InventoryItem.id).label("count")
    ).filter(InventoryItem.status == InventoryStatus.ACTIVE).group_by(
        InventoryItem.category
    ).all()
    
    return {
        "total_items": total_items,
        "total_inventory_value": float(total_value),
        "low_stock_items": low_stock,
        "categories": [{"name": c[0], "count": c[1]} for c in categories]
    }

@router.get("/clients/summary", tags=["Reports"])
async def clients_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get clients summary report"""
    
    total_clients = db.query(Client).filter(Client.is_active == True).count()
    
    top_clients = db.query(
        Client.name,
        func.count(ClientProduct.id).label("products_count")
    ).outerjoin(ClientProduct).filter(
        Client.is_active == True
    ).group_by(Client.id).order_by(
        func.count(ClientProduct.id).desc()
    ).limit(5).all()
    
    return {
        "total_clients": total_clients,
        "top_clients": [{"name": c[0], "products": c[1]} for c in top_clients]
    }

@router.get("/payments/summary", tags=["Reports"])
async def payments_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payments summary"""
    
    total_received = db.query(func.sum(ClientPayment.amount)).filter(
        ClientPayment.status.in_(["completed", "partial"])
    ).scalar() or 0
    
    pending_payments = db.query(func.sum(ClientPayment.amount)).filter(
        ClientPayment.status.in_(["pending", "overdue"])
    ).scalar() or 0
    
    return {
        "total_received": float(total_received),
        "pending_amount": float(pending_payments),
        "payment_mode_breakdown": {}
    }

@router.get("/dashboard", tags=["Reports"])
async def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete dashboard summary"""
    
    # Inventory stats
    total_items = db.query(InventoryItem).filter(
        InventoryItem.status == InventoryStatus.ACTIVE
    ).count()
    
    total_value = db.query(func.sum(
        InventoryItem.quantity * InventoryItem.unit_cost
    )).filter(InventoryItem.status == InventoryStatus.ACTIVE).scalar() or 0
    
    low_stock = db.query(InventoryItem).filter(
        InventoryItem.quantity <= InventoryItem.min_stock,
        InventoryItem.status == InventoryStatus.ACTIVE
    ).count()
    
    # Client stats
    total_clients = db.query(Client).filter(Client.is_active == True).count()
    
    # Payment stats
    total_received = db.query(func.sum(ClientPayment.amount)).filter(
        ClientPayment.status.in_(["completed"])
    ).scalar() or 0
    
    return {
        "inventory": {
            "total_items": total_items,
            "total_value": float(total_value),
            "low_stock_items": low_stock
        },
        "clients": {
            "total": total_clients
        },
        "payments": {
            "total_received": float(total_received)
        }
    }