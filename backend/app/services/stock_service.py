"""
Stock module business logic and services
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from app.models.stock import (
    Product, StockMovement, StockAlert, InventoryAudit,
    StockCategory, StockStatus
)
from app.schemas.stock import (
    ProductCreate, ProductUpdate, StockMovementCreate,
    StockAlertCreate, InventoryAuditCreate
)
import logging

logger = logging.getLogger(__name__)


class StockService:
    """Service class for stock management operations"""
    
    @staticmethod
    def create_product(db: Session, product: ProductCreate) -> Product:
        """Create a new product"""
        db_product = Product(
            name=product.name,
            sku=product.sku,
            description=product.description,
            category_id=product.category_id,
            quantity_in_stock=product.quantity_in_stock,
            minimum_quantity=product.minimum_quantity,
            reorder_quantity=product.reorder_quantity,
            cost_price=product.cost_price,
            selling_price=product.selling_price,
            supplier_id=product.supplier_id,
            location=product.location,
            barcode=product.barcode,
            status=StockService.calculate_status(product.quantity_in_stock, product.minimum_quantity)
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        logger.info(f"Product created: {db_product.id} - {db_product.name}")
        return db_product
    
    @staticmethod
    def get_product(db: Session, product_id: int) -> Optional[Product]:
        """Get product by ID"""
        return db.query(Product).filter(Product.id == product_id).first()
    
    @staticmethod
    def get_all_products(db: Session, skip: int = 0, limit: int = 100,
                        category_id: Optional[int] = None,
                        status: Optional[str] = None,
                        is_active: Optional[bool] = True) -> Tuple[List[Product], int]:
        """Get all products with pagination and filters"""
        query = db.query(Product)
        
        if is_active is not None:
            query = query.filter(Product.is_active == is_active)
        
        if category_id:
            query = query.filter(Product.category_id == category_id)
        
        if status:
            query = query.filter(Product.status == status)
        
        total = query.count()
        products = query.offset(skip).limit(limit).all()
        
        return products, total
    
    @staticmethod
    def search_products(db: Session, search_term: str,
                       skip: int = 0, limit: int = 100) -> List[Product]:
        """Search products by name, SKU, or barcode"""
        return db.query(Product).filter(
            or_(
                Product.name.ilike(f"%{search_term}%"),
                Product.sku.ilike(f"%{search_term}%"),
                Product.barcode.ilike(f"%{search_term}%")
            )
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_product(db: Session, product_id: int,
                      product_update: ProductUpdate) -> Optional[Product]:
        """Update product information"""
        db_product = StockService.get_product(db, product_id)
        if not db_product:
            return None
        
        update_data = product_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field not in ['quantity_in_stock', 'status']:
                setattr(db_product, field, value)
        
        db_product.updated_at = datetime.utcnow()
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        logger.info(f"Product updated: {db_product.id}")
        return db_product
    
    @staticmethod
    def add_stock(db: Session, product_id: int, quantity: int,
                  reason: str = "Restock", reference_number: Optional[str] = None,
                  updated_by: Optional[str] = None, notes: Optional[str] = None) -> Product:
        """Add stock to product"""
        db_product = StockService.get_product(db, product_id)
        if not db_product:
            raise ValueError(f"Product {product_id} not found")
        
        old_quantity = db_product.quantity_in_stock
        db_product.quantity_in_stock += quantity
        db_product.last_restocked = datetime.utcnow()
        db_product.status = StockService.calculate_status(
            db_product.quantity_in_stock,
            db_product.minimum_quantity
        )
        
        # Create stock movement record
        movement = StockMovement(
            product_id=product_id,
            movement_type="in",
            quantity=quantity,
            reason=reason,
            reference_number=reference_number,
            updated_by=updated_by,
            notes=notes
        )
        
        db.add(db_product)
        db.add(movement)
        db.commit()
        db.refresh(db_product)
        
        logger.info(f"Stock added: Product {product_id}, Quantity {quantity} ({old_quantity} -> {db_product.quantity_in_stock})")
        return db_product
    
    @staticmethod
    def deduct_stock(db: Session, product_id: int, quantity: int,
                    reason: str = "Sale", reference_number: Optional[str] = None,
                    updated_by: Optional[str] = None, notes: Optional[str] = None) -> Product:
        """Deduct stock from product"""
        db_product = StockService.get_product(db, product_id)
        if not db_product:
            raise ValueError(f"Product {product_id} not found")
        
        if db_product.quantity_in_stock < quantity:
            raise ValueError(f"Insufficient stock. Available: {db_product.quantity_in_stock}, Requested: {quantity}")
        
        old_quantity = db_product.quantity_in_stock
        db_product.quantity_in_stock -= quantity
        db_product.status = StockService.calculate_status(
            db_product.quantity_in_stock,
            db_product.minimum_quantity
        )
        
        # Create stock movement record
        movement = StockMovement(
            product_id=product_id,
            movement_type="out",
            quantity=quantity,
            reason=reason,
            reference_number=reference_number,
            updated_by=updated_by,
            notes=notes
        )
        
        db.add(db_product)
        db.add(movement)
        
        # Check and create alert if stock is low
        if db_product.quantity_in_stock <= db_product.minimum_quantity:
            StockService.create_or_update_alert(
                db, product_id, "low_stock",
                db_product.minimum_quantity,
                db_product.quantity_in_stock
            )
        
        db.commit()
        db.refresh(db_product)
        
        logger.info(f"Stock deducted: Product {product_id}, Quantity {quantity} ({old_quantity} -> {db_product.quantity_in_stock})")
        return db_product
    
    @staticmethod
    def get_stock_movements(db: Session, product_id: int,
                           skip: int = 0, limit: int = 100) -> List[StockMovement]:
        """Get stock movements for a product"""
        return db.query(StockMovement).filter(
            StockMovement.product_id == product_id
        ).order_by(StockMovement.created_at.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def create_or_update_alert(db: Session, product_id: int, alert_type: str,
                              threshold: int, current_quantity: int) -> StockAlert:
        """Create or update stock alert"""
        existing_alert = db.query(StockAlert).filter(
            and_(
                StockAlert.product_id == product_id,
                StockAlert.alert_type == alert_type,
                StockAlert.is_resolved == False
            )
        ).first()
        
        if existing_alert:
            existing_alert.current_quantity = current_quantity
            existing_alert.threshold = threshold
            existing_alert.updated_at = datetime.utcnow()
            db.add(existing_alert)
        else:
            alert = StockAlert(
                product_id=product_id,
                alert_type=alert_type,
                threshold=threshold,
                current_quantity=current_quantity,
                is_active=True,
                is_resolved=False
            )
            db.add(alert)
        
        db.commit()
        return existing_alert if existing_alert else db.query(StockAlert).filter(
            and_(
                StockAlert.product_id == product_id,
                StockAlert.alert_type == alert_type
            )
        ).first()
    
    @staticmethod
    def get_active_alerts(db: Session, skip: int = 0, limit: int = 100) -> List[StockAlert]:
        """Get all active stock alerts"""
        return db.query(StockAlert).filter(
            and_(
                StockAlert.is_active == True,
                StockAlert.is_resolved == False
            )
        ).order_by(StockAlert.created_at.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def resolve_alert(db: Session, alert_id: int) -> StockAlert:
        """Resolve a stock alert"""
        alert = db.query(StockAlert).filter(StockAlert.id == alert_id).first()
        if alert:
            alert.is_resolved = True
            alert.is_active = False
            alert.resolved_at = datetime.utcnow()
            db.add(alert)
            db.commit()
            logger.info(f"Alert resolved: {alert_id}")
        return alert
    
    @staticmethod
    def create_inventory_audit(db: Session, audit: InventoryAuditCreate) -> InventoryAudit:
        """Create inventory audit record"""
        db_product = StockService.get_product(db, audit.product_id)
        if not db_product:
            raise ValueError(f"Product {audit.product_id} not found")
        
        variance = audit.physical_quantity - db_product.quantity_in_stock
        variance_percentage = (variance / db_product.quantity_in_stock * 100) if db_product.quantity_in_stock > 0 else 0
        
        db_audit = InventoryAudit(
            product_id=audit.product_id,
            system_quantity=db_product.quantity_in_stock,
            physical_quantity=audit.physical_quantity,
            variance=variance,
            variance_percentage=variance_percentage,
            audited_by=audit.audited_by,
            notes=audit.notes
        )
        
        # If significant variance, update system quantity
        if variance != 0:
            db_product.quantity_in_stock = audit.physical_quantity
            db_product.status = StockService.calculate_status(
                db_product.quantity_in_stock,
                db_product.minimum_quantity
            )
            db_audit.action_taken = "Stock quantity adjusted"
            db.add(db_product)
        
        db.add(db_audit)
        db.commit()
        db.refresh(db_audit)
        logger.info(f"Inventory audit created: Product {audit.product_id}, Variance: {variance}")
        return db_audit
    
    @staticmethod
    def get_stock_summary(db: Session) -> Dict:
        """Get stock summary for dashboard"""
        products = db.query(Product).filter(Product.is_active == True).all()
        
        total_products = len(products)
        total_quantity = sum(p.quantity_in_stock for p in products)
        total_value = sum(p.quantity_in_stock * p.cost_price for p in products)
        
        low_stock_count = len([p for p in products if p.status == StockStatus.LOW_STOCK])
        out_of_stock_count = len([p for p in products if p.status == StockStatus.OUT_OF_STOCK])
        
        active_alerts = db.query(StockAlert).filter(
            and_(
                StockAlert.is_active == True,
                StockAlert.is_resolved == False
            )
        ).count()
        
        return {
            "total_products": total_products,
            "total_quantity": total_quantity,
            "total_value": round(total_value, 2),
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "active_alerts": active_alerts
        }
    
    @staticmethod
    def calculate_status(quantity: int, minimum_quantity: int) -> StockStatus:
        """Calculate product status based on quantity"""
        if quantity == 0:
            return StockStatus.OUT_OF_STOCK
        elif quantity <= minimum_quantity:
            return StockStatus.LOW_STOCK
        else:
            return StockStatus.IN_STOCK
    
    @staticmethod
    def get_low_stock_products(db: Session, days: int = 7) -> List[Product]:
        """Get products that are low in stock"""
        return db.query(Product).filter(
            Product.status.in_([StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK]),
            Product.is_active == True
        ).all()
    
    @staticmethod
    def get_stock_movements_report(db: Session, days: int = 30,
                                  movement_type: Optional[str] = None) -> List[StockMovement]:
        """Get stock movements report for specified period"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(StockMovement).filter(StockMovement.created_at >= cutoff_date)
        
        if movement_type:
            query = query.filter(StockMovement.movement_type == movement_type)
        
        return query.order_by(StockMovement.created_at.desc()).all()
