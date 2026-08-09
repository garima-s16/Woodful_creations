from sqlalchemy.orm import Session
from app.models.material import Material
from app.models.purchase import PurchaseOrder
from app.models.issue import MaterialIssue
from typing import List, Dict, Any

class StockService:
    
    @staticmethod
    def update_stock_on_purchase(db: Session, material_id: int, quantity: int) -> Material:
        material = db.query(Material).filter(Material.id == material_id).first()
        if material:
            material.total_purchased += quantity
            material.current_stock = material.calculate_current_stock()
            db.add(material)
            db.commit()
            db.refresh(material)
        return material
    
    @staticmethod
    def update_stock_on_issue(db: Session, material_id: int, quantity: int) -> Material:
        material = db.query(Material).filter(Material.id == material_id).first()
        if material:
            if material.current_stock < quantity:
                raise ValueError(f"Insufficient stock. Available: {material.current_stock}")
            material.total_issued += quantity
            material.current_stock = material.calculate_current_stock()
            db.add(material)
            db.commit()
            db.refresh(material)
        return material
    
    @staticmethod
    def get_low_stock_materials(db: Session) -> List[Material]:
        materials = db.query(Material).filter(
            Material.current_stock <= Material.minimum_stock,
            Material.is_active == 1
        ).all()
        return materials
    
    @staticmethod
    def get_stock_summary(db: Session) -> Dict[str, Any]:
        materials = db.query(Material).filter(Material.is_active == 1).all()
        
        total_stock_value = 0
        low_stock_count = 0
        out_of_stock_count = 0
        
        for material in materials:
            material.current_stock = material.calculate_current_stock()
            status = material.get_stock_status()
            
            if status == "LOW_STOCK":
                low_stock_count += 1
            elif status == "OUT_OF_STOCK":
                out_of_stock_count += 1
        
        return {
            "total_materials": len(materials),
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count
        }
    
    @staticmethod
    def get_stock_by_category(db: Session) -> Dict[str, Dict[str, Any]]:
        materials = db.query(Material).filter(Material.is_active == 1).all()
        category_summary = {}
        
        for material in materials:
            material.current_stock = material.calculate_current_stock()
            category = material.category
            
            if category not in category_summary:
                category_summary[category] = {
                    "total_items": 0,
                    "total_quantity": 0
                }
            
            category_summary[category]["total_items"] += 1
            category_summary[category]["total_quantity"] += material.current_stock
        
        return category_summary
