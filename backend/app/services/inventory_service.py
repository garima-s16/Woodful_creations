from sqlalchemy.orm import Session
from app.models.product import Product
from typing import List


class InventoryService:

    @staticmethod
    def get_low_stock_products(db: Session) -> List[Product]:
        return db.query(Product).filter(Product.quantity <= Product.min_quantity).all()

    @staticmethod
    def get_out_of_stock_products(db: Session) -> List[Product]:
        return db.query(Product).filter(Product.quantity <= 0).all()

    @staticmethod
    def calculate_inventory_value(db: Session) -> float:
        products = db.query(Product).all()
        return sum((p.quantity or 0) * (p.price_per_unit or 0) for p in products)

    @staticmethod
    def get_products_by_category(db: Session, category: str) -> List[Product]:
        return db.query(Product).filter(Product.category == category).all()

    @staticmethod
    def search_products(db: Session, search_term: str) -> List[Product]:
        like = f"%{search_term}%"
        return db.query(Product).filter(
            (Product.material_type.ilike(like)) |
            (Product.sku.ilike(like)) |
            (Product.description.ilike(like))
        ).all()
