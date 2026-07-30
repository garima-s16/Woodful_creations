from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_token
from app.models.client_project import ClientProject
from app.schemas.client_project import ClientProjectCreate, ClientProjectResponse, ClientProjectUpdate

router = APIRouter(prefix="/api/client-projects", tags=["clients"])
security = HTTPBearer()


def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@router.get("/", response_model=list[ClientProjectResponse])
def get_projects(client_id: int | None = Query(default=None), db: Session = Depends(get_db), auth=Depends(verify_auth)):
    query = db.query(ClientProject)
    if client_id is not None:
        query = query.filter(ClientProject.client_id == client_id)
    return query.all()


@router.post("/", response_model=ClientProjectResponse)
def create_project(project: ClientProjectCreate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_project = ClientProject(**project.dict(), amount_pending=project.cost)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/{project_id}", response_model=ClientProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    project = db.query(ClientProject).filter(ClientProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ClientProjectResponse)
def update_project(project_id: int, project: ClientProjectUpdate, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    db_project = db.query(ClientProject).filter(ClientProject.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)

    if "amount_paid" in update_data:
        db_project.amount_pending = db_project.cost - db_project.amount_paid

    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    project = db.query(ClientProject).filter(ClientProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}
