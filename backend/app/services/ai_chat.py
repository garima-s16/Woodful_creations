from sqlalchemy.orm import Session
from app.models.models import Product, User
from typing import Dict, Optional
import re

async def process_ai_message(
    message: str,
    user: User,
    context: Optional[Dict] = None,
    db: Session = None
) -> Dict:
    message_lower = message.lower()
    
    if "low stock" in message_lower or "stock low" in message_lower:
        return await handle_low_stock_query(user, db)
    
    elif "show products" in message_lower or "list products" in message_lower:
        return await handle_list_products(user, db)
    
    elif "add" in message_lower and "product" in message_lower:
        return {
            "text": "To add a product, use the Stock Inventory page and click 'Add New Product'. Please provide the product details there.",
            "action": "navigate_inventory"
        }
    
    elif "total" in message_lower and ("stock" in message_lower or "inventory" in message_lower):
        return await handle_inventory_summary(user, db)
    
    elif "help" in message_lower or "what can you do" in message_lower:
        return get_help_message()
    
    else:
        return {
            "text": "I can help you with: low stock items, product listings, inventory summary, and more. Type 'help' for more options.",
            "action": None
        }

async def handle_low_stock_query(user: User, db: Session) -> Dict:
    try:
        low_stock_products = db.query(Product).filter(
            Product.quantity <= Product.min_stock
        ).all()
        
        if not low_stock_products:
            return {"text": "All products have sufficient stock levels."}
        
        product_list = "\n".join([
            f"- {p.name} (SKU: {p.sku}): {p.quantity} units (Min: {p.min_stock})"
            for p in low_stock_products[:5]
        ])
        
        return {
            "text": f"Low Stock Alert: {len(low_stock_products)} products below minimum stock level:\n\n{product_list}",
            "action": "show_low_stock"
        }
    except Exception as e:
        return {"text": f"Error retrieving low stock items: {str(e)}"}

async def handle_list_products(user: User, db: Session) -> Dict:
    try:
        products = db.query(Product).filter(Product.is_active == True).limit(10).all()
        
        if not products:
            return {"text": "No products found in inventory."}
        
        product_list = "\n".join([
            f"- {p.name} (SKU: {p.sku}): {p.quantity} units, Price: ₹{p.selling_price}"
            for p in products
        ])
        
        return {
            "text": f"Top 10 Products in Inventory:\n\n{product_list}",
            "action": "show_products"
        }
    except Exception as e:
        return {"text": f"Error retrieving products: {str(e)}"}

async def handle_inventory_summary(user: User, db: Session) -> Dict:
    try:
        total_products = db.query(Product).filter(Product.is_active == True).count()
        total_quantity = db.query(Product).filter(Product.is_active == True).count()
        low_stock = db.query(Product).filter(
            (Product.quantity <= Product.min_stock) & (Product.is_active == True)
        ).count()
        
        return {
            "text": f"Inventory Summary:\nTotal Products: {total_products}\nLow Stock Items: {low_stock}\nAll Systems Normal",
            "action": "show_summary"
        }
    except Exception as e:
        return {"text": f"Error retrieving summary: {str(e)}"}

def get_help_message() -> Dict:
    return {
        "text": """I can help you with:
1. 'Show low stock items' - See products below minimum stock level
2. 'List products' - View top products in inventory
3. 'Inventory summary' - Get overall inventory statistics
4. 'Add product' - Navigate to add new product
5. 'Help' - Show this help message

How can I assist you today?""",
        "action": "show_help"
    }