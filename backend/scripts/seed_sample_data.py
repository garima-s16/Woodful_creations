import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.db import SessionLocal, Base, engine
from app.models import Supplier, Material, Purchase, Issue, Client, User
from datetime import date
from sqlalchemy.exc import IntegrityError

def ensure_tables():
    Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    try:
        # Suppliers
        suppliers = [
            {"supplier_id":"SUP-001","name":"Century Plywood Dealer","category":"Plywood","contact_person":"Rajesh","phone":"98XXXXXX21","gstin":"23ABCDE1234F1Z5","payment_terms":"15 Days","remarks":"Primary plywood supplier"},
            {"supplier_id":"SUP-002","name":"Greenpanel Distributor","category":"HDHMR","contact_person":"Mukesh","phone":"98XXXXXX22","gstin":"23ABCDE2234F1Z5","payment_terms":"Cash","remarks":"HDHMR and MDF"},
        ]
        for s in suppliers:
            existing = db.query(Supplier).filter(Supplier.supplier_id == s["supplier_id"]).first()
            if not existing:
                db.add(Supplier(**s))
        db.commit()

        # Materials
        materials = [
            {"material_id":"MAT-001","name":"HDHMR 18mm","category":"HDHMR","unit":"Sheets","opening_stock":35,"current_stock":23,"minimum_stock":20,"unit_cost":1800},
            {"material_id":"MAT-002","name":"Plywood BWP 18mm","category":"Plywood","unit":"Sheets","opening_stock":28,"current_stock":23,"minimum_stock":15,"unit_cost":2400},
        ]
        for m in materials:
            existing = db.query(Material).filter(Material.material_id == m["material_id"]).first()
            if not existing:
                db.add(Material(**m))
        db.commit()

        # Minimal purchases example
        purchases = [
            {"purchase_no":"PUR-001","date":date(2026,7,20),"supplier_id":db.query(Supplier).filter(Supplier.supplier_id=="SUP-002").first().id,"material_id":db.query(Material).filter(Material.material_id=="MAT-001").first().id,"quantity":20,"unit":"Sheets","rate":1800,"taxable_value":36000,"gst_percent":18,"gst_amount":6480,"invoice_total":42480,"payment_status":"Paid"}
        ]
        for p in purchases:
            existing = db.query(Purchase).filter(Purchase.purchase_no == p["purchase_no"]).first()
            if not existing:
                db.add(Purchase(**p))
        db.commit()

        # Create master users if missing
        masters = [
            {"email":"garima@woodfulcreations.com","username":"garimas","name":"Garima Sharma","password":"Gullak*16"},
            {"email":"nikhil@woodfulcreations.com","username":"nikhils","name":"Nikhil","password":"Nikhil*27"},
        ]
        for m in masters:
            existing = db.query(User).filter((User.username==m["username"]) | (User.email==m["email"])).first()
            if not existing:
                # Simple hash function - project uses its own hashing util; replace if needed
                import hashlib
                hp = hashlib.sha256(m["password"].encode("utf-8")).hexdigest()
                user = User(username=m["username"], email=m["email"], full_name=m["name"], hashed_password=hp, is_master=True, cannot_be_deleted=True)
                db.add(user)
        db.commit()
        print("Seeding completed.")
    except IntegrityError as e:
        db.rollback()
        print("Integrity error during seeding: ", e)
    except Exception as e:
        db.rollback()
        print("Error during seeding: ", e)
    finally:
        db.close()

if __name__ == "__main__":
    ensure_tables()
    seed()
