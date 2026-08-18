from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from app.core.audit import log_action
from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.client import Client
from app.models.order import Order
from app.models.estimate import Estimate
from app.models.client_activity import ClientActivity
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse, ClientWithStats
from app.utils.id_generator import generate_unique_code, generate_short_id

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("/", response_model=List[ClientResponse])
def list_clients(response: Response, search: Optional[str] = Query(None),
                  limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db), auth=Depends(get_current_user)):
    query = db.query(Client)
    if search:
        like = f"%{search}%"
        query = query.filter((Client.name.ilike(like)) | (Client.client_code.ilike(like)) | (Client.phone.ilike(like)))

    query = query.order_by(Client.name)
    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if limit is not None:
        query = query.offset(offset).limit(limit)
    return query.all()


@router.post("/", response_model=ClientResponse, status_code=201)
def create_client(data: ClientCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    payload = data.dict(exclude={"client_code"})
    for _ in range(5):
        code = generate_unique_code(db, Client, "client_code", "CL-")
        client = Client(**payload, client_code=code, business_id=generate_short_id())
        db.add(client)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(client)
        return client
    raise HTTPException(status_code=500, detail="Unable to generate a unique client code, please try again")


@router.get("/{client_id}", response_model=ClientWithStats)
def get_client(client_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    is_privileged = auth.get("role", "user") in ("master",)
    total_sales = sum((o.order_value for o in client.orders), Decimal("0"))
    return ClientWithStats(
        **ClientResponse.model_validate(client).model_dump(),
        total_orders=len(client.orders),
        total_sales=float(total_sales) if is_privileged else None,
    )


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: int, data: ClientUpdate, db: Session = Depends(get_db),
                   auth=Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(client, field, value)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if db.query(Order).filter(Order.client_id == client_id).first():
        raise HTTPException(status_code=400, detail="This client has orders and cannot be deleted.")
    if db.query(Estimate).filter(Estimate.client_id == client_id).first():
        raise HTTPException(status_code=400, detail="This client has estimates and cannot be deleted.")
    client_name = client.name
    db.query(ClientActivity).filter(ClientActivity.client_id == client_id).delete()
    db.delete(client)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_client", module_name="clients",
               record_id=client_id, old_value={"name": client_name})
