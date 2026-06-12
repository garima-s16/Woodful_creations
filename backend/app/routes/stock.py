"""
Stock module API routes - Enhanced for material types and variants
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.services.stock_service import StockService
from app.schemas.stock import (
    ProductCreate, ProductUpdate, ProductResponse,
    ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse, ProductVariantDetailResponse,
    StockMovementCreate, StockMovementResponse, BulkStockMovement,
    StockAlertResponse, InventoryAuditCreate, InventoryAuditResponse,
    MaterialStockResponse, StockSummary, DashboardMetrics,
    MATERIAL_DISPLAY_NAMES, MaterialTypeEnum
)
from app.database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stock", tags=["Stock Management"])


# ==================== MATERIAL TYPES ENDPOINTS ====================

@router.get("/materials", response_model=dict)
async def get_all_materials():
    """Get all available materials and their standard thicknesses"""
    materials = {}
    for material_type, thicknesses in [
        ("plywood_commercial", [6, 12, 18]),
        ("bwp_plywood", [6, 12, 18]),
        ("marine_plywood", [6, 12, 18]),
        ("mdf", [3, 6, 12, 18]),
        ("prelaminated_mdf", [6, 12, 18]),
        ("hdhmr", [6, 12, 18]),
        ("hdf", [2.5, 3, 4]),
        ("particle_board", [12, 18]),
        ("prelaminated_particle", [18]),
        ("block_board", [19, 25]),
        ("flush_door_board", [30, 35]),
        ("wpc_board", [6, 12, 18]),
        ("pvc_board", [6, 12, 18]),
        ("acrylic_sheet", [3, 5, 8]),
        ("veneer_mdf_plywood", [6, 12, 18]),
        ("flexi_plywood", [6, 8]),
    ]:
        materials[material_type] = {
            "display_name": MATERIAL_DISPLAY_NAMES.get(material_type, material_type),
            "thicknesses": thicknesses
        }
    
    return {
        "materials": materials,
        "total_materials": len(materials)
    }


# ==================== PRODUCT ENDPOINTS ====================

@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """Create a new material/product"""
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
    material_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Get all products/materials with pagination and filters"""
    try:
        products, total = StockService.get_all_products(
            db, skip, limit, material_type, is_active
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
    """Search products by name or SKU prefix"""
    try:
        products = StockService.search_products(db, query, skip, limit)
        return products
    except Exception as e:
        logger.error(f"Error searching products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}", response_model=MaterialStockResponse)
async def get_product_with_variants(product_id: int, db: Session = Depends(get_db)):
    """Get product with all its variants"""
    try:
        material_stock = StockService.get_material_stock(db, product_id)
        return material_stock
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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


# ==================== VARIANT ENDPOINTS ====================

@router.post("/variants", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED)
async def create_variant(variant: ProductVariantCreate, db: Session = Depends(get_db)):
    """Create a product variant (specific thickness)"""
    try:
        db_variant = StockService.create_variant(db, variant)
        profit_margin = ((db_variant.selling_price - db_variant.cost_price) / db_variant.cost_price * 100) if db_variant.cost_price > 0 else 0
        stock_value = db_variant.quantity_in_stock * db_variant.cost_price
        return ProductVariantDetailResponse(
            **db_variant.__dict__,
            profit_margin=profit_margin,
            stock_value=stock_value
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating variant: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/variants/{variant_id}", response_model=ProductVariantDetailResponse)
async def get_variant(variant_id: int, db: Session = Depends(get_db)):
    """Get variant details"""
    try:
        variant = StockService.get_variant(db, variant_id)
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        
        profit_margin = ((variant.selling_price - variant.cost_price) / variant.cost_price * 100) if variant.cost_price > 0 else 0
        stock_value = variant.quantity_in_stock * variant.cost_price
        
        return ProductVariantDetailResponse(
            **variant.__dict__,
            profit_margin=profit_margin,
            stock_value=stock_value
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching variant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/variants/{variant_id}", response_model=ProductVariantResponse)
async def update_variant(
    variant_id: int,
    variant_update: ProductVariantUpdate,
    db: Session = Depends(get_db)
):
    """Update variant information"""
    try:
        updated_variant = StockService.update_variant(db, variant_id, variant_update)
        if not updated_variant:
            raise HTTPException(status_code=404, detail="Variant not found")
        return updated_variant
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating variant: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== STOCK OPERATIONS ====================

@router.post("/variants/{variant_id}/add-stock", response_model=dict)
async def add_stock(
    variant_id: int,
    movement: StockMovementCreate,
    db: Session = Depends(get_db)
):
    """Add stock to variant"""
    try:
        updated_variant = StockService.add_stock(
            db,
            variant_id,
            movement.quantity,
            movement.reason,
            movement.reference_number,
            movement.updated_by,
            movement.notes
        )
        return {
            "status": "success",
            "message": f"Stock added successfully",
            "new_quantity": updated_variant.quantity_in_stock
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding stock: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/variants/{variant_id}/deduct-stock", response_model=dict)
async def deduct_stock(
    variant_id: int,
    movement: StockMovementCreate,
    db: Session = Depends(get_db)
):
    """Deduct stock from variant"""
    try:
        updated_variant = StockService.deduct_stock(
            db,
            variant_id,
            movement.quantity,
            movement.reason,
            movement.reference_number,
            movement.updated_by,
            movement.notes
        )
        return {
            "status": "success",
            "message": f"Stock deducted successfully",
            "new_quantity": updated_variant.quantity_in_stock
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
                    StockService.add_stock(
                        db, movement.variant_id, movement.quantity,
                        movement.reason, movement.reference_number,
                        movement.updated_by, movement.notes
                    )
                elif movement.movement_type == "out":
                    StockService.deduct_stock(
                        db, movement.variant_id, movement.quantity,
                        movement.reason, movement.reference_number,
                        movement.updated_by, movement.notes
                    )
                results.append({"variant_id": movement.variant_id, "status": "success"})
            except Exception as e:
                results.append({"variant_id": movement.variant_id, "status": "error", "error": str(e)})
        
        return {"status": "processed", "results": results}
    except Exception as e:
        logger.error(f"Error processing bulk movements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/variants/{variant_id}/movements", response_model=List[StockMovementResponse])
async def get_stock_movements(
    variant_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get stock movements for a variant"""
    try:
        movements = StockService.get_stock_movements(db, variant_id, skip, limit)
        return movements
    except Exception as e:
        logger.error(f"Error fetching movements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ALERTS & AUDITS ====================

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


# ==================== DASHBOARD & REPORTS ====================

@router.get("/dashboard/summary", response_model=StockSummary)
async def get_stock_summary(db: Session = Depends(get_db)):
    """Get stock summary for dashboard"""
    try:
        summary = StockService.get_stock_summary(db)
        return summary
    except Exception as e:
        logger.error(f"Error fetching summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/low-stock", response_model=List[ProductVariantResponse])
async def get_low_stock_variants(db: Session = Depends(get_db)):
    """Get low/out of stock variants"""
    try:
        variants = StockService.get_low_stock_variants(db)
        return variants
    except Exception as e:
        logger.error(f"Error fetching low stock variants: {str(e)}")
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
