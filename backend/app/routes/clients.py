"""
Client Management Routes
CRUD operations for clients and their products
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, User, Client, ClientProduct, ClientPayment
from app.routes.auth import get_current_user
from app.config import settings
from app.schemas import ClientCreate, ClientResponse, ClientProductResponse

router = APIRouter()

# ===================== CLIENT CRUD =====================

@router.post("/", response_model=ClientResponse, tags=["Clients"])
async def create_client(
    client: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new client"""
    
    # Check if client with email already exists
    existing = db.query(Client).filter(Client.email == client.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this email already exists"
        )
    
    db_client = Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    
    return db_client

@router.get("/", response_model=List[ClientResponse], tags=["Clients"])
async def get_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, le=settings.MAX_PAGE_SIZE),
    search: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all clients"""
    
    query = db.query(Client)
    
    if search:
        query = query.filter(
            (Client.name.ilike(f"%{search}%")) |
            (Client.email.ilike(f"%{search}%"))
        )
    
    return query.offset(skip).limit(limit).all()

@router.get("/{client_id}", response_model=ClientResponse, tags=["Clients"])
async def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific client with all details"""
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    return client

@router.put("/{client_id}", response_model=ClientResponse, tags=["Clients"])
async def update_client(
    client_id: int,
    client_update: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a client"""
    
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    update_data = client_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_client, field, value)
    
    db.commit()
    db.refresh(db_client)
    
    return db_client

@router.delete("/{client_id}", tags=["Clients"])
async def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft delete a client"""
    
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    db_client.is_active = False
    db.commit()
    
    return {"message": "Client deleted"}

# ===================== CLIENT PRODUCTS =====================

@router.get("/{client_id}/products", response_model=List[ClientProductResponse], tags=["Clients"])
async def get_client_products(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all products for a client"""
    
    products = db.query(ClientProduct).filter(
        ClientProduct.client_id == client_id
    ).all()
    
    return products

# ===================== CLIENT PAYMENTS =====================

@router.get("/{client_id}/payments", tags=["Clients"])
async def get_client_payments(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payment history for a client"""
    
    payments = db.query(ClientPayment).filter(
        ClientPayment.client_id == client_id
    ).all()
    
    total_paid = sum(p.amount for p in payments if p.status.value == "completed")
    
    return {
        "client_id": client_id,
        "payments": payments,
        "total_paid": total_paid
    }