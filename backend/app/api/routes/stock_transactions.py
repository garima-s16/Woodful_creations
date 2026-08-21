from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.stock_transaction import StockTransfer, StockAdjustment
from app.models.stock_ledger_entry import StockLedgerEntry
from app.schemas.stock_transaction import (
    StockTransferCreate, StockTransferResponse, StockAdjustmentCreate, StockAdjustmentResponse,
    MaterialLocationStockResponse,
)
from app.schemas.stock_ledger_entry import StockLedgerEntryResponse
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


@router.get("/ledger", response_model=List[StockLedgerEntryResponse])
def list_ledger_entries(material_id: int = Query(...), db: Session = Depends(get_db),
                         auth=Depends(get_current_user)):
    """The real, immutable transaction history for a material - every
    Receipt/Issue/Adjustment that has ever affected its stock, in
    order, each traceable back to the actual Purchase/Issue/
    StockAdjustment record that caused it."""
    return db.query(StockLedgerEntry).filter(
        StockLedgerEntry.material_id == material_id
    ).order_by(StockLedgerEntry.created_at.asc()).all()


@router.get("/locations/{material_id}", response_model=MaterialLocationStockResponse)
def get_material_location_stock(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """The genuine per-location breakdown for one material - e.g.
    Rack A2 -> 12, Rack B1 -> 6, Total -> 18 - derived from the ledger,
    never a second stored total."""
    return StockService.get_location_balances(db, material_id)


@router.get("/verify/{material_id}")
def verify_stock(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Proves whether Material.current_stock genuinely reconciles with
    the ledger (opening_stock + every ledger entry) - the actual
    verification this architecture is built to support."""
    return StockService.verify_stock_matches_ledger(db, material_id)
