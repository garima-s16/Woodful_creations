from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.models.client import Client
from app.core.database import get_db
from app.core.security import verify_token
from typing import List

router = APIRouter(prefix="/api/clients", tags=["clients"])
security = HTTPBearer()

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

@router.get("/", response_model=List[ClientResponse])
def get_clients(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    clients = db.query(Client).filter(Client.is_active == True).all()
    return clients

@router.post("/", response_model=ClientResponse)
def create_client(client: ClientCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    existing_client = db.query(Client).filter(Client.email == client.email).first()
    if existing_client:
        raise HTTPException(status_code=400, detail="Client with this email already exists")
    
    db_client = Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.patch("/{client_id}", response_model=ClientResponse)
def update_client(client_id: int, client: ClientUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = client.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_client, key, value)
    
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.delete("/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.is_active = False
    db.add(client)
    db.commit()
    return {"message": "Client deactivated"}