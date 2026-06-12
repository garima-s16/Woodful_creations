"""
Stock module API routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.services.stock_service import StockService
from app.schemas.stock import (
    ProductCreate, ProductUpdate, ProductResponse, ProductDetailResponse,
    StockMovementCreate, StockMovementResponse, BulkStockMovement,
    StockAlertResponse, InventoryAuditCreate, InventoryAuditResponse,
    StockCategoryCreate, StockCategoryResponse, StockSummary,
    DashboardMetrics
)
from app.models.stock import StockCategory, StockStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["Stock"])

# Dependency (placeholder - replace with actual database session)
def get_db():
    # This would be replaced with actual database session
    pass


# PRODUCT ENDPOINTS
@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product"""
    try:
        db_product = StockService.create_product(db, product)
        return db_product
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products", response_model=dict)
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Get all products with pagination and filters"""
    try:
        products, total = StockService.get_all_products(
            db, skip, limit, category_id, status, is_active
        )
        return {
            "data": products,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/search", response_model=List[ProductResponse])
async def search_products(
    query: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Search products by name, SKU, or barcode"""
    try:
        products = StockService.search_products(db, query, skip, limit)
        return products
    except Exception as e:
        logger.error(f"Error searching products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get product details by ID"""
    try:
        product = StockService.get_product(db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        profit_margin = ((product.selling_price - product.cost_price) / product.cost_price * 100) if product.cost_price > 0 else 0
        stock_value = product.quantity_in_stock * product.cost_price
        
        response = ProductDetailResponse(
            **product.__dict__,
            profit_margin=profit_margin,
            stock_value=stock_value
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db)
):
    """Update product information"""
    try:
        updated_product = StockService.update_product(db, product_id, product_update)
        if not updated_product:
            raise HTTPException(status_code=404, detail="Product not found")
        return updated_product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# STOCK MOVEMENT ENDPOINTS
@router.post("/products/{product_id}/add-stock", response_model=dict)
async def add_stock(
    product_id: int,
    movement: StockMovementCreate,
    db: Session = Depends(get_db)
):
    """Add stock to product"""
    try:
        if movement.product_id != product_id:
            raise HTTPException(status_code=400, detail="Product ID mismatch")
        
        updated_product = StockService.add_stock(
            db,
            product_id,
            movement.quantity,
            movement.reason,
            movement.reference_number,
            movement.updated_by,
            movement.notes
        )
        return {
            "status": "success",
            "message": f"Stock added successfully",
            "product": updated_product
        }
    except Exception as e:
        logger.error(f"Error adding stock: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products/{product_id}/deduct-stock", response_model=dict)
async def deduct_stock(
    product_id: int,
    movement: StockMovementCreate,
    db: Session = Depends(get_db)
):
    """Deduct stock from product"""
    try:
        if movement.product_id != product_id:
            raise HTTPException(status_code=400, detail="Product ID mismatch")
        
        updated_product = StockService.deduct_stock(
            db,
            product_id,
            movement.quantity,
            movement.reason,
            movement.reference_number,
            movement.updated_by,
            movement.notes
        )
        return {
            "status": "success",
            "message": f"Stock deducted successfully",
            "product": updated_product
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deducting stock: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-movements", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def bulk_stock_movements(
    bulk_movement: BulkStockMovement,
    db: Session = Depends(get_db)
):
    """Process multiple stock movements"""
    try:
        results = []
        for movement in bulk_movement.movements:
            try:
                if movement.movement_type == "in":
                    product = StockService.add_stock(
                        db, movement.product_id, movement.quantity,
                        movement.reason, movement.reference_number,
                        movement.updated_by, movement.notes
                    )
                elif movement.movement_type == "out":
                    product = StockService.deduct_stock(
                        db, movement.product_id, movement.quantity,
                        movement.reason, movement.reference_number,
                        movement.updated_by, movement.notes
                    )
                results.append({"product_id": movement.product_id, "status": "success"})
            except Exception as e:
                results.append({"product_id": movement.product_id, "status": "error", "error": str(e)})
        
        return {"status": "processed", "results": results}
    except Exception as e:
        logger.error(f"Error processing bulk movements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/movements", response_model=List[StockMovementResponse])
async def get_stock_movements(
    product_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get stock movements for a product"""
    try:
        movements = StockService.get_stock_movements(db, product_id, skip, limit)
        return movements
    except Exception as e:
        logger.error(f"Error fetching movements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ALERT ENDPOINTS
@router.get("/alerts", response_model=List[StockAlertResponse])
async def get_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get active stock alerts"""
    try:
        alerts = StockService.get_active_alerts(db, skip, limit)
        return alerts
    except Exception as e:
        logger.error(f"Error fetching alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/alerts/{alert_id}/resolve", response_model=dict)
async def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """Resolve a stock alert"""
    try:
        alert = StockService.resolve_alert(db, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "resolved", "alert_id": alert_id}
    except Exception as e:
        logger.error(f"Error resolving alert: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# INVENTORY AUDIT ENDPOINTS
@router.post("/audits", response_model=InventoryAuditResponse, status_code=status.HTTP_201_CREATED)
async def create_audit(audit: InventoryAuditCreate, db: Session = Depends(get_db)):
    """Create inventory audit record"""
    try:
        db_audit = StockService.create_inventory_audit(db, audit)
        return db_audit
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating audit: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# DASHBOARD ENDPOINTS
@router.get("/dashboard/summary", response_model=StockSummary)
async def get_stock_summary(db: Session = Depends(get_db)):
    """Get stock summary for dashboard"""
    try:
        summary = StockService.get_stock_summary(db)
        return summary
    except Exception as e:
        logger.error(f"Error fetching summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/low-stock", response_model=List[ProductResponse])
async def get_low_stock_products(db: Session = Depends(get_db)):
    """Get low stock products"""
    try:
        products = StockService.get_low_stock_products(db)
        return products
    except Exception as e:
        logger.error(f"Error fetching low stock products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/movements", response_model=List[StockMovementResponse])
async def get_movements_report(
    days: int = Query(30, ge=1, le=365),
    movement_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get stock movements report"""
    try:
        movements = StockService.get_stock_movements_report(db, days, movement_type)
        return movements
    except Exception as e:
        logger.error(f"Error fetching report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
