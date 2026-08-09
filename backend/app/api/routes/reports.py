from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.report_service import ReportService
from datetime import datetime

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/order-profitability")
async def get_order_profitability_report(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    report = ReportService.get_order_profitability_report(db, start_date, end_date, limit, skip)
    return {
        "data": report,
        "count": len(report)
    }

@router.get("/supplier-performance")
async def get_supplier_performance_report(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    report = ReportService.get_supplier_performance_report(db, limit, skip)
    return {
        "data": report,
        "count": len(report)
    }

@router.get("/stock-summary")
async def get_stock_summary_report(db: Session = Depends(get_db)):
    report = ReportService.get_stock_summary_report(db)
    return report
