from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.stock_transaction import StockTransfer, StockAdjustment
from app.schemas.stock_transaction import (
    StockTransferCreate, StockTransferResponse, StockAdjustmentCreate, StockAdjustmentResponse,
)
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/stock", tags=["stock-transactions"])


@router.post("/transfers", response_model=StockTransferResponse, status_code=201)
def create_transfer(data: StockTransferCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    return StockService.record_transfer(db, data)


@router.get("/transfers", response_model=List[StockTransferResponse])
def list_transfers(material_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(StockTransfer)
    if material_id:
        query = query.filter(StockTransfer.material_id == material_id)
    return query.order_by(StockTransfer.created_at.desc()).limit(100).all()


@router.post("/adjustments", response_model=StockAdjustmentResponse, status_code=201)
def create_adjustment(data: StockAdjustmentCreate, db: Session = Depends(get_db),
                       auth=Depends(require_role("master"))):
    return StockService.record_adjustment(db, data)


@router.get("/adjustments", response_model=List[StockAdjustmentResponse])
def list_adjustments(material_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                      auth=Depends(get_current_user)):
    query = db.query(StockAdjustment)
    if material_id:
        query = query.filter(StockAdjustment.material_id == material_id)
    return query.order_by(StockAdjustment.created_at.desc()).limit(100).all()
