from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime
from app.database import StockItem, StockHistory, Alert
from app.core.constants import MATERIAL_TYPES, ALERT_TYPES
from app.core.exceptions import LowStockError, InvalidMaterialError, InvalidThicknessError
import logging

logger = logging.getLogger(__name__)

class StockService:
    @staticmethod
    def validate_material(material_type: str, thickness: float) -> bool:
        if material_type not in MATERIAL_TYPES:
            raise InvalidMaterialError(material_type)
        
        if thickness not in MATERIAL_TYPES[material_type]:
            raise InvalidThicknessError(material_type, thickness)
        
        return True
    
    @staticmethod
    def get_low_stock_items(db: Session) -> List[Dict]:
        items = db.query(StockItem).filter(StockItem.quantity <= StockItem.min_stock).all()
        return items
    
    @staticmethod
    def create_low_stock_alert(db: Session, item_id: int, user_id: int) -> Alert:
        item = db.query(StockItem).filter(StockItem.id == item_id).first()
        if not item:
            return None
        
        alert = Alert(
            user_id=user_id,
            alert_type="LOW_STOCK",
            title=f"Low Stock: {item.name}",
            message=f"{item.name} ({item.quantity} units) is below minimum ({item.min_stock} units)",
            related_item_id=item_id,
            priority="high"
        )
        db.add(alert)
        db.commit()
        return alert
    
    @staticmethod
    def record_stock_movement(db: Session, item_id: int, transaction_type: str, quantity: int, 
                             notes: Optional[str], performed_by: int) -> StockHistory:
        history = StockHistory(
            stock_item_id=item_id,
            transaction_type=transaction_type,
            quantity_changed=quantity,
            reason=notes,
            performed_by=performed_by
        )
        db.add(history)
        db.commit()
        return history
    
    @staticmethod
    def update_stock_quantity(db: Session, item_id: int, new_quantity: int, 
                             transaction_type: str, notes: Optional[str], performed_by: int) -> StockItem:
        item = db.query(StockItem).filter(StockItem.id == item_id).first()
        if not item:
            return None
        
        quantity_changed = new_quantity - item.quantity
        item.quantity = new_quantity
        item.updated_at = datetime.utcnow()
        
        StockService.record_stock_movement(db, item_id, transaction_type, quantity_changed, notes, performed_by)
        
        if new_quantity <= item.min_stock:
            StockService.create_low_stock_alert(db, item_id, performed_by)
        
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    
    @staticmethod
    def get_stock_value(db: Session) -> Dict:
        items = db.query(StockItem).all()
        total_value = sum(item.unit_cost * item.quantity for item in items)
        total_items = len(items)
        total_quantity = sum(item.quantity for item in items)
        
        return {
            "total_items": total_items,
            "total_quantity": total_quantity,
            "total_value": round(total_value, 2),
            "average_item_value": round(total_value / total_items, 2) if total_items > 0 else 0
        }
    
    @staticmethod
    def get_material_statistics(db: Session) -> Dict:
        items = db.query(StockItem).all()
        materials = {}
        
        for item in items:
            material = item.name
            if material not in materials:
                materials[material] = {
                    "total_quantity": 0,
                    "total_value": 0,
                    "units": []
                }
            
            materials[material]["total_quantity"] += item.quantity
            materials[material]["total_value"] += item.unit_cost * item.quantity
            materials[material]["units"].append({
                "id": item.id,
                "quantity": item.quantity,
                "sku": item.sku
            })
        
        return materials