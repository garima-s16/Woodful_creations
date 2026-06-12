"""
Stock module business logic and services
Enhanced for material types with variants
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from app.models.stock import (
    Product, ProductVariant, StockMovement, StockAlert, InventoryAudit,
    StockCategory, StockStatus, MaterialType, MATERIAL_THICKNESSES
)
from app.schemas.stock import (
    ProductCreate, ProductUpdate, ProductVariantCreate, ProductVariantUpdate,
    StockMovementCreate, InventoryAuditCreate
)
import logging

logger = logging.getLogger(__name__)


class StockService:
    """Service class for stock management operations"""
    
    # ==================== PRODUCT OPERATIONS ====================
    
    @staticmethod
    def create_product(db: Session, product: ProductCreate) -> Product:
        """Create a new product/material"""
        db_product = Product(
            name=product.name,
            sku_prefix=product.sku_prefix,
            description=product.description,
            category_id=product.category_id,
            material_type=product.material_type,
            is_active=True
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
                        material_type: Optional[str] = None,
                        is_active: Optional[bool] = True) -> Tuple[List[Product], int]:
        """Get all products with pagination and filters"""
        query = db.query(Product)
        
        if is_active is not None:
            query = query.filter(Product.is_active == is_active)
        
        if material_type:
            query = query.filter(Product.material_type == material_type)
        
        total = query.count()
        products = query.offset(skip).limit(limit).all()
        
        return products, total
    
    @staticmethod
    def search_products(db: Session, search_term: str,
                       skip: int = 0, limit: int = 100) -> List[Product]:
        """Search products by name or SKU prefix"""
        return db.query(Product).filter(
            or_(
                Product.name.ilike(f"%{search_term}%"),
                Product.sku_prefix.ilike(f"%{search_term}%")
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
            setattr(db_product, field, value)
        
        db_product.updated_at = datetime.utcnow()
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        logger.info(f"Product updated: {db_product.id}")
        return db_product
    
    # ==================== VARIANT OPERATIONS ====================
    
    @staticmethod
    def create_variant(db: Session, variant: ProductVariantCreate) -> ProductVariant:
        """Create a product variant (specific thickness/size)"""
        # Get product to validate it exists
        product = StockService.get_product(db, variant.product_id)
        if not product:
            raise ValueError(f"Product {variant.product_id} not found")
        
        # Generate SKU if not provided
        if not variant.sku:
            sku = f"{product.sku_prefix}-{int(variant.thickness * 10):03d}"
        else:
            sku = variant.sku
        
        # Calculate standard area if dimensions provided
        standard_area = None
        if variant.standard_width and variant.standard_length:
            standard_area = variant.standard_width * variant.standard_length
        
        db_variant = ProductVariant(
            product_id=variant.product_id,
            thickness=variant.thickness,
            unit=variant.unit,
            sku=sku,
            barcode=variant.barcode,
            quantity_in_stock=variant.quantity_in_stock,
            minimum_quantity=variant.minimum_quantity,
            reorder_quantity=variant.reorder_quantity,
            cost_price=variant.cost_price,
            selling_price=variant.selling_price,
            standard_width=variant.standard_width,
            standard_length=variant.standard_length,
            standard_area=standard_area,
            supplier_name=variant.supplier_name,
            grade=variant.grade,
            finish=variant.finish,
            location=variant.location,
            status=StockService.calculate_status(
                variant.quantity_in_stock,
                variant.minimum_quantity
            )
        )
        db.add(db_variant)
        db.commit()
        db.refresh(db_variant)
        logger.info(f"Variant created: {db_variant.id} - {product.name} ({variant.thickness}mm)")
        return db_variant
    
    @staticmethod
    def get_variant(db: Session, variant_id: int) -> Optional[ProductVariant]:
        """Get product variant by ID"""
        return db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    
    @staticmethod
    def get_product_variants(db: Session, product_id: int) -> List[ProductVariant]:
        """Get all variants for a product"""
        return db.query(ProductVariant).filter(
            ProductVariant.product_id == product_id,
            ProductVariant.is_active == True
        ).order_by(ProductVariant.thickness).all()
    
    @staticmethod
    def update_variant(db: Session, variant_id: int,
                      variant_update: ProductVariantUpdate) -> Optional[ProductVariant]:
        """Update product variant"""
        db_variant = StockService.get_variant(db, variant_id)
        if not db_variant:
            return None
        
        update_data = variant_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field not in ['quantity_in_stock', 'status']:
                setattr(db_variant, field, value)
        
        db_variant.updated_at = datetime.utcnow()
        db.add(db_variant)
        db.commit()
        db.refresh(db_variant)
        logger.info(f"Variant updated: {db_variant.id}")
        return db_variant
    
    # ==================== STOCK OPERATIONS ====================
    
    @staticmethod
    def add_stock(db: Session, variant_id: int, quantity: int,
                  reason: str = "Restock", reference_number: Optional[str] = None,
                  updated_by: Optional[str] = None, notes: Optional[str] = None) -> ProductVariant:
        """Add stock to variant"""
        db_variant = StockService.get_variant(db, variant_id)
        if not db_variant:
            raise ValueError(f"Variant {variant_id} not found")
        
        old_quantity = db_variant.quantity_in_stock
        db_variant.quantity_in_stock += quantity
        db_variant.last_restocked = datetime.utcnow()
        db_variant.status = StockService.calculate_status(
            db_variant.quantity_in_stock,
            db_variant.minimum_quantity
        )
        
        # Create stock movement record
        movement = StockMovement(
            variant_id=variant_id,
            product_id=db_variant.product_id,
            movement_type="in",
            quantity=quantity,
            reason=reason,
            reference_number=reference_number,
            updated_by=updated_by,
            notes=notes
        )
        
        db.add(db_variant)
        db.add(movement)
        db.commit()
        db.refresh(db_variant)
        
        logger.info(f"Stock added: Variant {variant_id}, Quantity {quantity} ({old_quantity} -> {db_variant.quantity_in_stock})")
        return db_variant
    
    @staticmethod
    def deduct_stock(db: Session, variant_id: int, quantity: int,
                    reason: str = "Sale", reference_number: Optional[str] = None,
                    updated_by: Optional[str] = None, notes: Optional[str] = None) -> ProductVariant:
        """Deduct stock from variant"""
        db_variant = StockService.get_variant(db, variant_id)
        if not db_variant:
            raise ValueError(f"Variant {variant_id} not found")
        
        if db_variant.quantity_in_stock < quantity:
            raise ValueError(f"Insufficient stock. Available: {db_variant.quantity_in_stock}, Requested: {quantity}")
        
        old_quantity = db_variant.quantity_in_stock
        db_variant.quantity_in_stock -= quantity
        db_variant.status = StockService.calculate_status(
            db_variant.quantity_in_stock,
            db_variant.minimum_quantity
        )
        
        # Create stock movement record
        movement = StockMovement(
            variant_id=variant_id,
            product_id=db_variant.product_id,
            movement_type="out",
            quantity=quantity,
            reason=reason,
            reference_number=reference_number,
            updated_by=updated_by,
            notes=notes
        )
        
        db.add(db_variant)
        db.add(movement)
        
        # Check and create alert if stock is low
        if db_variant.quantity_in_stock <= db_variant.minimum_quantity:
            StockService.create_or_update_alert(
                db, variant_id, db_variant.product_id, "low_stock",
                db_variant.minimum_quantity,
                db_variant.quantity_in_stock
            )
        
        db.commit()
        db.refresh(db_variant)
        
        logger.info(f"Stock deducted: Variant {variant_id}, Quantity {quantity} ({old_quantity} -> {db_variant.quantity_in_stock})")
        return db_variant
    
    @staticmethod
    def get_stock_movements(db: Session, variant_id: int,
                           skip: int = 0, limit: int = 100) -> List[StockMovement]:
        """Get stock movements for a variant"""
        return db.query(StockMovement).filter(
            StockMovement.variant_id == variant_id
        ).order_by(StockMovement.created_at.desc()).offset(skip).limit(limit).all()
    
    # ==================== ALERT OPERATIONS ====================
    
    @staticmethod
    def create_or_update_alert(db: Session, variant_id: int, product_id: int,
                              alert_type: str, threshold: int,
                              current_quantity: int) -> StockAlert:
        """Create or update stock alert"""
        existing_alert = db.query(StockAlert).filter(
            and_(
                StockAlert.variant_id == variant_id,
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
                variant_id=variant_id,
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
                StockAlert.variant_id == variant_id,
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
    
    # ==================== AUDIT OPERATIONS ====================
    
    @staticmethod
    def create_inventory_audit(db: Session, audit: InventoryAuditCreate) -> InventoryAudit:
        """Create inventory audit record"""
        db_variant = StockService.get_variant(db, audit.variant_id)
        if not db_variant:
            raise ValueError(f"Variant {audit.variant_id} not found")
        
        variance = audit.physical_quantity - db_variant.quantity_in_stock
        variance_percentage = (variance / db_variant.quantity_in_stock * 100) if db_variant.quantity_in_stock > 0 else 0
        
        db_audit = InventoryAudit(
            variant_id=audit.variant_id,
            product_id=audit.product_id,
            system_quantity=db_variant.quantity_in_stock,
            physical_quantity=audit.physical_quantity,
            variance=variance,
            variance_percentage=variance_percentage,
            audited_by=audit.audited_by,
            notes=audit.notes
        )
        
        # If significant variance, update system quantity
        if variance != 0:
            db_variant.quantity_in_stock = audit.physical_quantity
            db_variant.status = StockService.calculate_status(
                db_variant.quantity_in_stock,
                db_variant.minimum_quantity
            )
            db_audit.action_taken = "Stock quantity adjusted"
            db.add(db_variant)
        
        db.add(db_audit)
        db.commit()
        db.refresh(db_audit)
        logger.info(f"Inventory audit created: Variant {audit.variant_id}, Variance: {variance}")
        return db_audit
    
    # ==================== DASHBOARD & REPORTS ====================
    
    @staticmethod
    def get_stock_summary(db: Session) -> Dict:
        """Get stock summary for dashboard"""
        products = db.query(Product).filter(Product.is_active == True).all()
        variants = db.query(ProductVariant).filter(ProductVariant.is_active == True).all()
        
        total_products = len(products)
        total_variants = len(variants)
        total_quantity = sum(v.quantity_in_stock for v in variants)
        total_value = sum(v.quantity_in_stock * v.cost_price for v in variants)
        
        low_stock_count = len([v for v in variants if v.status == StockStatus.LOW_STOCK])
        out_of_stock_count = len([v for v in variants if v.status == StockStatus.OUT_OF_STOCK])
        
        active_alerts = db.query(StockAlert).filter(
            and_(
                StockAlert.is_active == True,
                StockAlert.is_resolved == False
            )
        ).count()
        
        # Material breakdown
        material_breakdown = {}
        for variant in variants:
            material_type = variant.product_id
            material_breakdown[material_type] = material_breakdown.get(material_type, 0) + variant.quantity_in_stock
        
        return {
            "total_products": total_products,
            "total_variants": total_variants,
            "total_quantity": total_quantity,
            "total_value": round(total_value, 2),
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "active_alerts": active_alerts,
            "material_breakdown": material_breakdown
        }
    
    @staticmethod
    def calculate_status(quantity: int, minimum_quantity: int) -> StockStatus:
        """Calculate variant status based on quantity"""
        if quantity == 0:
            return StockStatus.OUT_OF_STOCK
        elif quantity <= minimum_quantity:
            return StockStatus.LOW_STOCK
        else:
            return StockStatus.IN_STOCK
    
    @staticmethod
    def get_low_stock_variants(db: Session) -> List[ProductVariant]:
        """Get variants that are low in stock"""
        return db.query(ProductVariant).filter(
            ProductVariant.status.in_([StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK]),
            ProductVariant.is_active == True
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
    
    @staticmethod
    def get_material_stock(db: Session, product_id: int) -> Dict:
        """Get complete stock information for a material with all variants"""
        product = StockService.get_product(db, product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        variants = StockService.get_product_variants(db, product_id)
        
        total_stock_quantity = sum(v.quantity_in_stock for v in variants)
        total_stock_value = sum(v.quantity_in_stock * v.cost_price for v in variants)
        
        low_stock_variants = [v for v in variants if v.status == StockStatus.LOW_STOCK]
        out_of_stock_variants = [v for v in variants if v.status == StockStatus.OUT_OF_STOCK]
        
        return {
            "product": product,
            "variants": variants,
            "total_stock_quantity": total_stock_quantity,
            "total_stock_value": round(total_stock_value, 2),
            "low_stock_variants": low_stock_variants,
            "out_of_stock_variants": out_of_stock_variants
        }
