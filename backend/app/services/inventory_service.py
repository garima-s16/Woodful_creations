from sqlalchemy.orm import Session
from app.models.inventory import Product, StockMovement, StockAlert
from typing import List, Optional
import uuid
from datetime import datetime

class InventoryService:
    
    @staticmethod
    def get_low_stock_products(db: Session, threshold: int = 10) -> List[Product]:
        return db.query(Product).filter(
            (Product.quantity <= threshold) & (Product.is_active == True)
        ).all()
    
    @staticmethod
    def get_out_of_stock_products(db: Session) -> List[Product]:
        return db.query(Product).filter(
            (Product.quantity <= 0) & (Product.is_active == True)
        ).all()
    
    @staticmethod
    def record_stock_movement(
        db: Session,
        product_id: str,
        movement_type: str,
        quantity: int,
        notes: Optional[str] = None
    ) -> StockMovement:
        movement = StockMovement(
            id=str(uuid.uuid4()),
            product_id=product_id,
            movement_type=movement_type,
            quantity=quantity,
            notes=notes
        )
        db.add(movement)
        db.commit()
        return movement
    
    @staticmethod
    def create_stock_alert(
        db: Session,
        product_id: str,
        alert_type: str,
        message: str
    ) -> StockAlert:
        alert = StockAlert(
            id=str(uuid.uuid4()),
            product_id=product_id,
            alert_type=alert_type,
            message=message
        )
        db.add(alert)
        db.commit()
        return alert
    
    @staticmethod
    def get_stock_history(db: Session, product_id: str, limit: int = 100) -> List[StockMovement]:
        return db.query(StockMovement).filter(
            StockMovement.product_id == product_id
        ).order_by(StockMovement.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_unread_alerts(db: Session) -> List[StockAlert]:
        return db.query(StockAlert).filter(
            StockAlert.is_read == False
        ).order_by(StockAlert.created_at.desc()).all()
    
    @staticmethod
    def mark_alert_as_read(db: Session, alert_id: str) -> StockAlert:
        alert = db.query(StockAlert).filter(StockAlert.id == alert_id).first()
        if alert:
            alert.is_read = True
            db.commit()
        return alert
    
    @staticmethod
    def calculate_inventory_value(db: Session) -> float:
        products = db.query(Product).filter(Product.is_active == True).all()
        return sum(p.quantity * p.unit_cost for p in products)
    
    @staticmethod
    def get_products_by_category(db: Session, category: str) -> List[Product]:
        return db.query(Product).filter(
            (Product.category == category) & (Product.is_active == True)
        ).all()
    
    @staticmethod
    def search_products(db: Session, search_term: str) -> List[Product]:
        return db.query(Product).filter(
            (Product.is_active == True) & (
                (Product.name.ilike(f"%{search_term}%")) |
                (Product.sku.ilike(f"%{search_term}%")) |
                (Product.description.ilike(f"%{search_term}%"))
            )
        ).all()