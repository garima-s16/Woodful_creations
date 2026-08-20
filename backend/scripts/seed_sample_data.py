"""
Seed the database with sample business data plus two named master admin
accounts (Garima, Nikhil) via SEED_MASTER_PASSWORD.

Idempotent - safe to re-run; skips any table that already has rows.
"""
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models.setting import (
    Unit, StockStatus, StockPaymentStatus, SupplierTerm,
    Department, TaskStatus, AttendanceStatus, Machine,
    ProjectStatus, Priority, PaymentMode, LeadSource, ProjectType, ExpenseCategory,
)
from app.models.material_category import MaterialCategory, MaterialSubcategory
from app.models.location import Location
from app.models.supplier import Supplier
from app.models.supplier_material import SupplierMaterial
from app.models.material import Material
from app.models.purchase import Purchase
from app.models.issue import Issue
from app.models.client import Client
from app.models.order import Order
from app.models.estimate import Estimate
from app.api.routes.estimates import _compute_totals
from app.models.payment import Payment
from app.models.notification import Notification
from app.models.working_calendar import CompanyHoliday
from app.services.notification_service import NotificationService
from app.models.project_expense import ProjectExpense
from app.models.employee import Employee
from app.models.salary_slip import SalarySlip
from app.models.leave import Leave
from app.models.attendance import Attendance
from app.models.daily_task import DailyTask
from app.models.task_comment import TaskComment
from app.models.production_job import ProductionJob
from app.models.product_category import ProductCategory, ProductSubcategory
from app.models.product import Product
from app.models.product_material import ProductMaterial
from app.models.order_item import OrderItem
from app.models.estimate_line_item import EstimateLineItem
from app.utils.id_generator import generate_short_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def _dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def _t(s):
    return datetime.strptime(s, "%H:%M").time()


LOOKUPS = {
    Unit: ["Sheets", "Nos", "Kg", "Litres", "Metres", "Feet", "Sq Ft", "Boxes", "Sets"],
    StockStatus: ["STOCK OK", "LOW STOCK", "OUT OF STOCK"],
    StockPaymentStatus: ["Paid", "Part Paid", "Credit"],
    SupplierTerm: ["Cash", "7 Days", "15 Days", "30 Days", "45 Days"],
    Department: ["CNC", "Laser", "Panel Saw", "Edge Banding", "Assembly", "Painting",
                 "Installation", "Design", "Accounts", "Sales & Marketing", "Store"],
    TaskStatus: ["TO DO", "DOING", "DONE", "BLOCKED"],
    AttendanceStatus: ["Present", "Absent", "Half Day", "Leave"],
    Machine: ["CNC Router", "CO2 Laser", "Panel Saw", "Edge Bander", "Cold Press", "PU Paint Setup"],
    ProjectStatus: ["Enquiry", "Designing", "Approved", "Material Purchase", "Cutting",
                     "Edge Banding", "Assembly", "Painting", "Ready for Dispatch",
                     "Installation", "Completed", "On Hold"],
    Priority: ["Low", "Medium", "High", "Urgent"],
    PaymentMode: ["Cash", "UPI", "Bank", "Credit Card"],
    LeadSource: ["Instagram", "Facebook", "Architect", "Referral", "Google", "Walk-in", "Existing Client"],
    ProjectType: ["Bedroom Furniture", "Modular Kitchen", "Wardrobe", "TV Unit", "Mandir",
                  "CNC Wall Panel", "Office Furniture", "Showroom Display", "Other"],
    ExpenseCategory: ["Raw Material", "Hardware", "Transport", "Installation", "Labour",
                       "Design", "Marketing", "Miscellaneous"],
}


def seed_locations(db):
    """Real hierarchy (Warehouse -> Area -> Rack), not a flat name-only
    list - matches the brief's exact example: Main Workshop -> Board
    Storage -> Rack A1/A2/A3, etc. Returns a flat dict keyed by leaf
    location name for other seed functions to reference."""
    if db.query(Location).count() > 0:
        return {l.name: l for l in db.query(Location).all()}

    workshop = Location(name="Main Workshop", location_type="Warehouse")
    db.add(workshop)
    db.flush()

    out = {"Main Workshop": workshop}
    areas = {
        "Board Storage": ["Rack A1", "Rack A2", "Rack A3"],
        "Hardware Storage": ["Rack B1", "Rack B2"],
        "Laminate Storage": ["Rack C1"],
        "Paint Store": [],
        "Chemical Area": [],
        "Packaging Area": [],
    }
    for area_name, racks in areas.items():
        area = Location(name=area_name, location_type="Area", parent_id=workshop.id)
        db.add(area)
        db.flush()
        out[area_name] = area
        for rack_name in racks:
            rack = Location(name=rack_name, location_type="Rack", parent_id=area.id)
            db.add(rack)
            db.flush()
            out[rack_name] = rack

    db.commit()
    logger.info("Seeded location hierarchy: %d nodes", len(out))
    return out


def seed_material_hierarchy(db):
    """Real Category -> Subcategory rows (not the flat, unwired
    MaterialCategory list this replaced) - matches Section 26's own
    grouping. Returns a dict keyed by subcategory name so seed_materials
    can wire each seeded material's subcategory_id correctly, the same
    way seed_locations' returned dict wires location_id."""
    if db.query(MaterialSubcategory).count() > 0:
        return {s.name: s for s in db.query(MaterialSubcategory).all()}

    hierarchy = {
        "Board & Wood Materials": ["Plywood", "HDHMR", "MDF", "Particle Board", "Block Board", "Solid Wood"],
        "Surface Materials": ["Laminate", "Acrylic", "ACP", "WPC"],
        "Hardware": ["Hinges", "Drawer Channels", "Handles"],
        "Finishing": ["Adhesive", "Paint/PU"],
        "Edge Banding": ["Edge Band"],
        "Packaging & Consumables": ["Packaging", "Consumable"],
    }
    out = {}
    for category_name, subcategory_names in hierarchy.items():
        category = MaterialCategory(name=category_name)
        db.add(category)
        db.flush()
        for sub_name in subcategory_names:
            sub = MaterialSubcategory(category_id=category.id, name=sub_name)
            db.add(sub)
            db.flush()
            out[sub_name] = sub

    db.commit()
    logger.info("Seeded material hierarchy: %d categories, %d subcategories", len(hierarchy), len(out))
    return out


def seed_master_users(db):
    """Two named master admin accounts (Section 22/48), per repeated
    explicit request. Password comes from SEED_MASTER_PASSWORD - never
    hard-coded. If the env var isn't set, this is skipped with a clear
    warning rather than creating an insecure default password."""
    from app.core.security import hash_password
    from app.models.user import User

    password = os.environ.get("SEED_MASTER_PASSWORD")
    if not password:
        logger.warning(
            "SEED_MASTER_PASSWORD is not set - skipping master user creation. "
            "Set this environment variable (e.g. export SEED_MASTER_PASSWORD='...') "
            "and re-run the seed script to create the garima@woodful.local and "
            "nikhil@woodful.local master accounts."
        )
        return

    rows = [
        ("garima", "garima@woodful.local", "Garima"),
        ("nikhil", "nikhil@woodful.local", "Nikhil"),
    ]
    created = 0
    for username, email, full_name in rows:
        if db.query(User).filter((User.email == email) | (User.username == username)).first():
            continue
        db.add(User(
            username=username, email=email, full_name=full_name, role="master",
            password_hash=hash_password(password), is_active=True, cannot_be_deleted=True,
        ))
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d master user(s)", created)


def seed_named_suppliers(db):
    """Additional suppliers matching the brief's specific named roster
    (Section 25/33) - added alongside the existing suppliers, not
    replacing them, so multi-supplier price comparison has real data to
    show (the existing seed only had one supplier per material category).

    Checks each row individually rather than skipping the whole function
    if any one of them already exists - so adding a new named supplier
    here later actually reaches databases that already ran this function
    once, not just fresh ones."""
    rows = [
        ("SUP-006", "Sanket Plywood & Boards", "Plywood", "Sanket", "98XXXXXX26", "23ABCDE6234F1Z5", "15 Days", "Alternate plywood/HDHMR supplier"),
        ("SUP-007", "Ashu Hardware House", "Hardware", "Ashu", "98XXXXXX27", "23ABCDE7234F1Z5", "7 Days", "Alternate hardware supplier"),
        ("SUP-008", "Shruti Laminates", "Laminate", "Shruti", "98XXXXXX28", "23ABCDE8234F1Z5", "15 Days", "Alternate laminate supplier"),
    ]
    out = {s.supplier_code: s for s in db.query(Supplier).filter(Supplier.supplier_code.in_([r[0] for r in rows])).all()}
    created = 0
    for code, name, cat, contact, phone, gstin, terms, remarks in rows:
        if code in out:
            continue
        s = Supplier(supplier_code=code, name=name, category=cat, contact_person=contact,
                      phone=phone, gstin=gstin, payment_terms=terms, remarks=remarks)
        db.add(s)
        out[code] = s
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d named suppliers", created)
    return out


def seed_supplier_materials(db, suppliers, named_suppliers, materials):
    """Real multi-supplier pricing comparisons (Section 33's exact
    example: BWP Plywood from Sanket at 2350, Ashu at 2410). Uses
    SupplierMaterial, not the legacy single Material.supplier_id -
    that stays pointed at each material's existing primary supplier."""
    if db.query(SupplierMaterial).count() > 0:
        return
    rows = [
        # (material_code, supplier_code, price, moq, lead_time_days, is_preferred)
        ("MAT-002", "SUP-001", "2350.00", 10, 2, True),   # BWP Plywood - existing primary supplier
        ("MAT-002", "SUP-006", "2410.00", 5, 1, False),   # BWP Plywood - Sanket, alternate
        ("MAT-001", "SUP-002", "1820.00", 10, 3, True),   # HDHMR - existing primary supplier
        ("MAT-001", "SUP-006", "1850.00", 5, 1, False),   # HDHMR - Sanket, alternate
        ("MAT-007", "SUP-004", "480.00", 10, 2, True),    # Channel - existing primary supplier
        ("MAT-007", "SUP-007", "495.00", 5, 1, False),    # Channel - Ashu, alternate
        ("MAT-004", "SUP-003", "950.00", 10, 3, True),     # White Laminate - existing primary supplier
        ("MAT-004", "SUP-008", "970.00", 5, 1, False),     # White Laminate - Shruti, alternate
    ]
    count = 0
    for mat_code, sup_code, price, moq, lead, preferred in rows:
        material = materials.get(mat_code)
        supplier = suppliers.get(sup_code) or named_suppliers.get(sup_code)
        if not material or not supplier:
            continue
        db.add(SupplierMaterial(
            material_id=material.id, supplier_id=supplier.id, supplier_price=Decimal(price),
            moq=moq, lead_time_days=lead, is_preferred=preferred,
        ))
        count += 1
    db.commit()
    logger.info("Seeded %d supplier-material pricing rows", count)


def seed_lookups(db):
    for model, names in LOOKUPS.items():
        if db.query(model).count() > 0:
            continue
        for n in names:
            db.add(model(name=n))
        logger.info("Seeded %d rows into %s", len(names), model.__tablename__)
    db.commit()


def seed_suppliers(db):
    if db.query(Supplier).count() > 0:
        return {s.supplier_code: s for s in db.query(Supplier).all()}
    rows = [
        ("SUP-001", "Century Plywood Dealer", "Plywood", "Sanket", "98XXXXXX21", "23ABCDE1234F1Z5", "15 Days", "Primary plywood supplier"),
        ("SUP-002", "Greenpanel Distributor", "HDHMR", "Ishu", "98XXXXXX22", "23ABCDE2234F1Z5", "Cash", "HDHMR and MDF"),
        ("SUP-003", "Merino Laminates", "Laminate", "Ashu", "98XXXXXX23", "23ABCDE3234F1Z5", "30 Days", "Decorative laminates"),
        ("SUP-004", "Hardware Hub", "Hardware", "Mahek", "98XXXXXX24", "23ABCDE4234F1Z5", "7 Days", "Hinges and channels"),
        ("SUP-005", "Paint Solutions", "Paint/PU", "Aviral", "98XXXXXX25", "23ABCDE5234F1Z5", "Cash", "PU and polish material"),
    ]
    out = {}
    for code, name, cat, contact, phone, gstin, terms, remarks in rows:
        s = Supplier(supplier_code=code, name=name, category=cat, contact_person=contact,
                      phone=phone, gstin=gstin, payment_terms=terms, remarks=remarks)
        db.add(s)
        out[code] = s
    db.commit()
    logger.info("Seeded %d suppliers", len(rows))
    return out


def seed_materials(db, suppliers, locations, subcategories):
    if db.query(Material).count() > 0:
        return {m.material_code: m for m in db.query(Material).all()}
    rows = [
        # code, name, category/subcategory-name, brand, size, unit, opening, purchased, issued, current, minimum, rate, supplier, location
        ("MAT-001", "HDHMR 18mm", "HDHMR", "Greenpanel", "8x4 ft / 18mm", "Sheets", 35, 20, 32, 23, 20, 1800, "SUP-002", "Rack A1"),
        ("MAT-002", "Plywood BWP 18mm", "Plywood", "Century", "8x4 ft / 18mm", "Sheets", 28, 15, 20, 23, 15, 2400, "SUP-001", "Rack A2"),
        ("MAT-003", "MDF 12mm", "MDF", "Action Tesa", "8x4 ft / 12mm", "Sheets", 22, 0, 22, 0, 10, 1250, "SUP-002", "Rack A3"),
        ("MAT-004", "White Laminate 1mm", "Laminate", "Merino", "8x4 ft / 1mm", "Sheets", 40, 30, 22, 48, 15, 950, "SUP-003", "Rack B1"),
        ("MAT-005", "Walnut Laminate 1mm", "Laminate", "Merino", "8x4 ft / 1mm", "Sheets", 18, 0, 0, 18, 10, 1150, "SUP-003", "Rack B2"),
        ("MAT-006", "Soft Close Hinges", "Hinges", "Hettich", "Full Overlay", "Nos", 120, 100, 90, 130, 50, 145, "SUP-004", "Hardware Storage"),
        ("MAT-007", "Telescopic Channel 18in", "Drawer Channels", "Ebco", "18 inch pair", "Sets", 35, 20, 18, 37, 15, 480, "SUP-004", "Hardware Storage"),
        ("MAT-008", "Fevicol HeatX", "Adhesive", "Pidilite", "50 kg drum", "Kg", 20, 15.5, 13, 22.5, 5, 210, "SUP-004", "Chemical Area"),
        ("MAT-009", "PVC Edge Band White", "Edge Band", "Rehau", "22mm x 0.8mm", "Metres", 450, 300, 380, 370, 150, 18, "SUP-004", "Rack B2"),
        ("MAT-010", "PU White Paint", "Paint/PU", "Asian Paints", "20 Litre", "Litres", 24, 20, 9, 35, 10, 620, "SUP-005", "Paint Store"),
    ]
    out = {}
    for code, name, cat, brand, size, unit, opening, purchased, issued, current, minimum, rate, sup_code, loc in rows:
        # location_id/subcategory_id set from the real hierarchies where a
        # name match exists; the legacy `category`/`location` strings are
        # always set regardless, so nothing breaks even without a match.
        location_row = locations.get(loc)
        subcategory_row = subcategories.get(cat)
        m = Material(material_code=code, name=name, category=cat, brand_grade=brand,
                      thickness_size=size, unit=unit, opening_stock=Decimal(str(opening)),
                      total_purchased=Decimal(str(purchased)), total_issued=Decimal(str(issued)),
                      current_stock=Decimal(str(current)), minimum_stock=Decimal(str(minimum)), average_rate=Decimal(str(rate)),
                      supplier_id=suppliers[sup_code].id, location=loc,
                      location_id=location_row.id if location_row else None,
                      subcategory_id=subcategory_row.id if subcategory_row else None)
        db.add(m)
        out[code] = m
    db.commit()
    logger.info("Seeded %d materials", len(rows))
    return out


def seed_product_categories(db):
    """Family 21 Product Master hierarchy - same Category -> Subcategory
    shape as the material hierarchy, but a genuinely separate table
    (a product and a material are different kinds of thing and must
    never share a category list). Returns a flat dict keyed by
    subcategory name for seed_products() to reference."""
    if db.query(ProductCategory).count() > 0:
        return {s.name: s for s in db.query(ProductSubcategory).all()}
    rows = [
        # category, [subcategories]
        ("Bedroom Furniture", ["Wardrobes", "Beds"]),
        ("Modular Kitchen", ["Base Units", "Wall Units"]),
        ("Mandir", ["Wall Mounted"]),
        ("TV & Entertainment", ["TV Units"]),
        ("Wall Panels", ["CNC Panels"]),
        ("Showroom & Display", ["Display Units"]),
    ]
    out = {}
    for cat_name, subcats in rows:
        category = ProductCategory(name=cat_name, business_id=generate_short_id(db))
        db.add(category)
        db.flush()
        for sub_name in subcats:
            subcategory = ProductSubcategory(category_id=category.id, name=sub_name, business_id=generate_short_id(db))
            db.add(subcategory)
            db.flush()
            out[sub_name] = subcategory
    db.commit()
    logger.info("Seeded %d product categories / %d subcategories", len(rows), len(out))
    return out


def seed_products(db, product_subcategories, materials):
    """The real Product Master (Family 21) - both standard catalog items
    (sold repeatedly, e.g. "Sliding Wardrobe - 3 Door") and custom,
    one-off furniture made for a single client (product_type="custom",
    no SKU) - both represented the same way so OrderItem/
    EstimateLineItem can point at either through one relationship.
    bom gives each standard product a real bill-of-materials against
    already-seeded Materials - a genuine relational fact, not free text."""
    if db.query(Product).count() > 0:
        return {p.sku or p.name: p for p in db.query(Product).all()}
    rows = [
        # name, sku, type, subcategory, description, L, W, H, dim_unit, finish, unit,
        # cost_price, selling_price, tax_percent, lead_time_days, notes, bom[(mat_code, qty, unit)]
        ("Sliding Wardrobe - 3 Door", "WD-SLD-3D", "standard", "Wardrobes",
         "3-door sliding wardrobe, laminate finish, soft-close hardware",
         96, 24, 84, "in", "White Laminate", "Piece", 130000, 180000, 18, 21, "",
         [("MAT-001", 4, "Sheets"), ("MAT-004", 3, "Sheets"), ("MAT-006", 6, "Nos"), ("MAT-007", 3, "Sets")]),
        ("Hinged Wardrobe - 2 Door", "WD-HNG-2D", "standard", "Wardrobes",
         "2-door hinged wardrobe with internal shelving",
         48, 22, 84, "in", "Walnut Laminate", "Piece", 26000, 36000, 18, 14, "",
         [("MAT-002", 2, "Sheets"), ("MAT-005", 1, "Sheets"), ("MAT-006", 4, "Nos")]),
        ("Queen Bed with Storage", "BD-QN-STG", "standard", "Beds",
         "Queen size bed with hydraulic storage",
         78, 60, 36, "in", "White Laminate", "Piece", 68000, 95000, 18, 18, "",
         [("MAT-002", 3, "Sheets"), ("MAT-004", 2, "Sheets")]),
        ("Modular Kitchen Base Unit - 3ft", "MK-BASE-3", "standard", "Base Units",
         "3 ft base cabinet with drawers, BWP core",
         36, 24, 34, "in", "PU White Paint", "Piece", 12000, 18000, 18, 15, "",
         [("MAT-002", 1, "Sheets"), ("MAT-007", 1, "Sets"), ("MAT-010", 1, "Litres")]),
        ("Modular Kitchen Wall Unit - 3ft", "MK-WALL-3", "standard", "Wall Units",
         "3 ft wall cabinet, BWP core",
         36, 13, 28, "in", "PU White Paint", "Piece", 7000, 10500, 18, 15, "",
         [("MAT-002", 1, "Sheets"), ("MAT-006", 2, "Nos")]),
        ("TV Unit - Floating", "TV-FLT-01", "standard", "TV Units",
         "Wall-mounted floating TV unit with LED panel back",
         72, 16, 20, "in", "Walnut Laminate", "Piece", 22000, 32000, 18, 12, "",
         [("MAT-001", 1, "Sheets"), ("MAT-005", 1, "Sheets")]),
        ("CNC Wall Panel - Floral", "CNC-FLR-01", "standard", "CNC Panels",
         "Laser-cut floral pattern decorative wall panel",
         48, 96, 0.75, "in", "Natural Wood", "Sq Ft", 320, 480, 18, 10, "Priced per sheet, sold by area",
         [("MAT-001", 1, "Sheets")]),
        ("Custom Pooja Mandir - HDHMR", None, "custom", "Wall Mounted",
         "Client-specific wall-mounted temple unit, carved front panel - made to order for Nimisha (CL-004)",
         36, 15, 48, "in", "Natural Wood", "Piece", 88000, 125000, 18, 18,
         "One-off for order WC-2026-004", [("MAT-001", 2, "Sheets"), ("MAT-009", 10, "Metres")]),
        ("Custom Showroom Display Unit", None, "custom", "Display Units",
         "Client-specific showroom display fixture - made to order for Woodful's own showroom (CL-005)",
         120, 30, 72, "in", "PU White Paint", "Piece", 128000, 180000, 18, 25,
         "One-off for order WC-2026-005", [("MAT-002", 4, "Sheets"), ("MAT-010", 2, "Litres")]),
        ("Custom CNC Wall Panel - Client Design", None, "custom", "CNC Panels",
         "Client-specific carved 3D wall panel design - made to order for Shrangi (CL-003)",
         60, 96, 1, "in", "Natural Wood", "Piece", 61000, 85000, 18, 12,
         "One-off for order WC-2026-003", [("MAT-001", 1, "Sheets")]),
    ]
    out = {}
    for idx, (name, sku, ptype, subcat_name, desc, length, width, height, dim_unit, finish, unit,
              cost, selling, tax, lead_time, notes, bom) in enumerate(rows, start=1):
        subcategory = product_subcategories.get(subcat_name)
        product = Product(
            product_code=f"PROD-{idx:03d}", business_id=generate_short_id(db), sku=sku, name=name,
            product_type=ptype, subcategory_id=subcategory.id if subcategory else None,
            category=subcategory.category.name if subcategory else None,
            description=desc, length=Decimal(str(length)), width=Decimal(str(width)), height=Decimal(str(height)),
            dimension_unit=dim_unit, finish=finish, unit=unit,
            cost_price=Decimal(str(cost)), selling_price=Decimal(str(selling)), tax_percent=Decimal(str(tax)),
            lead_time_days=lead_time, notes=notes, is_active=True,
        )
        db.add(product)
        db.flush()
        for mat_code, qty, bom_unit in bom:
            material = materials.get(mat_code)
            if not material:
                continue
            db.add(ProductMaterial(product_id=product.id, material_id=material.id,
                                    quantity=Decimal(str(qty)), unit=bom_unit))
        out[sku or name] = product
    db.commit()
    logger.info("Seeded %d products", len(rows))
    return out


def seed_clients(db):
    if db.query(Client).count() > 0:
        return {c.client_code: c for c in db.query(Client).all()}
    rows = [
        ("CL-001", "Siddharth", "93XXXXXX54", "siddharth@example.com", "Indore", "Referral", "2026-07-10", "Bedroom furniture"),
        ("CL-002", "Khushaal", "98XXXXXX31", "khushaal@example.com", "Bicholi, Indore", "Architect", "2026-07-12", "Modular kitchen"),
        ("CL-003", "Shrangi", "98XXXXXX32", "shrangi@example.com", "Vijay Nagar", "Instagram", "2026-07-18", "CNC wall panel"),
        ("CL-004", "Nimisha", "98XXXXXX33", "nimisha@example.com", "Rau", "Existing Client", "2026-07-19", "Mandir"),
        ("CL-005", "Mayank", "93XXXXXX00", "mayank@example.com", "Woodful Creations", "Internal", "2026-07-20", "Showroom display"),
    ]
    out = {}
    for code, name, phone, email, addr, source, contact_date, remarks in rows:
        c = Client(client_code=code, name=name, phone=phone, email=email, address=addr,
                   lead_source=source, first_contact_date=_d(contact_date), remarks=remarks)
        db.add(c)
        out[code] = c
    db.commit()
    logger.info("Seeded %d clients", len(rows))
    return out


def seed_orders(db, clients):
    if db.query(Order).count() > 0:
        return {o.order_code: o for o in db.query(Order).all()}
    rows = [
        ("WC-2026-001", "CL-001", "Bedroom Furniture", "2026-07-20", "2026-08-20", 325000, 32500, 97500, "Cutting", 45, "High", "Ravi", "Indore", "Bedroom and wardrobe"),
        ("WC-2026-002", "CL-002", "Modular Kitchen", "2026-07-22", "2026-08-25", 216000, 21600, 64800, "Material Purchase", 30, "Urgent", "Devendra", "Bicholi, Indore", "Base and wall cabinets"),
        ("WC-2026-003", "CL-003", "CNC Wall Panel", "2026-07-25", "2026-08-10", 85000, 25000, 0, "Designing", 10, "Medium", "Devendra", "Vijay Nagar", "3D carved panel"),
        ("WC-2026-004", "CL-004", "Mandir", "2026-07-26", "2026-08-18", 125000, 25000, 0, "Approved", 20, "High", "Ravi", "Rau", "HDHMR mandir"),
        ("WC-2026-005", "CL-005", "Showroom Display", "2026-07-27", "2026-09-01", 180000, 0, 0, "Designing", 10, "Low", "Brajwal", "Woodful Creations", "Internal work"),
    ]
    out = {}
    for code, cl_code, ptype, odate, ddate, value, advance, other, status, progress, priority, sup, addr, remarks in rows:
        total_received = Decimal(str(advance)) + Decimal(str(other))
        o = Order(order_code=code, client_id=clients[cl_code].id, project_type=ptype,
                  order_date=_d(odate), delivery_date=_d(ddate), order_value=Decimal(str(value)),
                  advance=Decimal(str(advance)), other_received=Decimal(str(other)),
                  total_received=total_received, balance=Decimal(str(value)) - total_received,
                  project_status=status, progress_percent=progress, priority=priority,
                  supervisor=sup, site_address=addr, remarks=remarks)
        db.add(o)
        out[code] = o
    db.commit()
    logger.info("Seeded %d orders", len(rows))
    return out


def seed_order_items(db, orders, products):
    """Family 21 - Product <-> Order Item relationship, applied to the
    demo data: each order's line items sum to exactly that order's
    pre-set order_value, so the two representations agree rather than
    silently drifting apart. Standard-catalog orders (WC-2026-001/002)
    reference real standard Products; the three orders tied to one-off
    work each reference their own custom Product (product_type="custom"),
    demonstrating both kinds of Product Master entry feeding the same
    OrderItem relationship."""
    if db.query(OrderItem).count() > 0:
        return
    # order_code, [(product_sku_or_name, qty, unit, rate, category), ...]
    rows = {
        "WC-2026-001": [
            ("WD-SLD-3D", 1, "Piece", 180000, "Furniture"),
            ("BD-QN-STG", 1, "Piece", 95000, "Furniture"),
            ("TV-FLT-01", 1, "Piece", 50000, "Furniture"),
        ],
        "WC-2026-002": [
            ("MK-BASE-3", 6, "Piece", 18000, "Furniture"),
            ("MK-WALL-3", 6, "Piece", 12000, "Furniture"),
            ("WD-HNG-2D", 1, "Piece", 36000, "Furniture"),
        ],
        "WC-2026-003": [("Custom CNC Wall Panel - Client Design", 1, "Piece", 85000, "Furniture")],
        "WC-2026-004": [("Custom Pooja Mandir - HDHMR", 1, "Piece", 125000, "Furniture")],
        "WC-2026-005": [("Custom Showroom Display Unit", 1, "Piece", 180000, "Furniture")],
    }
    count = 0
    for order_code, items in rows.items():
        order = orders.get(order_code)
        if not order:
            continue
        for idx, (product_key, qty, unit, rate, category) in enumerate(items):
            product = products.get(product_key)
            amount = Decimal(str(qty)) * Decimal(str(rate))
            db.add(OrderItem(
                order_id=order.id, product_id=product.id if product else None,
                description=product.name if product else product_key, category=category,
                quantity=Decimal(str(qty)), unit=unit, rate=Decimal(str(rate)), amount=amount, sort_order=idx,
            ))
            count += 1
    db.commit()
    logger.info("Seeded %d order items", count)


def seed_estimates(db, clients, orders):
    """Demonstrates the full Estimate -> Approval -> Order pipeline
    (Section 4.2/28) with genuine status variety - not every estimate
    here becomes an order, since a real pipeline has estimates still
    pending a decision too. EST-001/002 are marked approved and their
    order_id points at the real order that estimate became; the rest
    stay unlinked, representing estimates still in progress or declined."""
    if db.query(Estimate).count() > 0:
        return {e.estimate_code: e for e in db.query(Estimate).all()}
    rows = [
        # code, client, order (None if not yet/never converted), status, material_cost, labor_cost, valid_until, remarks
        ("EST-001", "CL-001", "WC-2026-001", "approved", 200000, 80000, "2026-08-05", "Approved - became the bedroom furniture order"),
        ("EST-002", "CL-002", "WC-2026-002", "approved", 140000, 50000, "2026-08-05", "Approved - became the modular kitchen order"),
        ("EST-003", "CL-003", None, "sent", 55000, 20000, "2026-08-15", "Sent to client, awaiting decision on the CNC panel"),
        ("EST-004", "CL-004", None, "draft", 30000, 10000, "2026-08-20", "Draft for an additional puja room piece"),
        ("EST-005", "CL-001", None, "rejected", 45000, 15000, "2026-07-30", "Client declined a separate TV unit estimate"),
    ]
    out = {}
    for code, cl_code, order_code, status, mat_cost, lab_cost, valid_until, remarks in rows:
        subtotal = Decimal(str(mat_cost)) + Decimal(str(lab_cost))
        tax_amount, total_cost = _compute_totals(subtotal, Decimal("0"), Decimal("18"))
        e = Estimate(
            estimate_code=code, client_id=clients[cl_code].id,
            order_id=orders[order_code].id if order_code else None,
            material_cost=Decimal(str(mat_cost)), labor_cost=Decimal(str(lab_cost)),
            discount=Decimal("0"), tax_percent=Decimal("18"), tax_amount=tax_amount, total_cost=total_cost,
            status=status, valid_until=_d(valid_until), remarks=remarks,
        )
        db.add(e)
        out[code] = e
    db.commit()
    logger.info("Seeded %d estimates", len(rows))
    return out



    if db.query(Payment).count() > 0:
        return
    rows = [
        ("RCPT-001", "2026-07-20", "WC-2026-001", "Advance", "Bank", 32500, "UTR001"),
        ("RCPT-002", "2026-07-25", "WC-2026-001", "Progress Payment", "UPI", 97500, "UPI001"),
        ("RCPT-003", "2026-07-22", "WC-2026-002", "Advance", "Bank", 21600, "UTR002"),
        ("RCPT-004", "2026-07-27", "WC-2026-002", "Progress Payment", "Bank", 64800, "UTR003"),
        ("RCPT-005", "2026-07-25", "WC-2026-003", "Advance", "UPI", 25000, "UPI003"),
        ("RCPT-006", "2026-07-26", "WC-2026-004", "Advance", "Cash", 25000, "CASH001"),
        ("RCPT-007", "2026-07-28", "WC-2026-005", "Internal", "Bank", 0, None),
    ]
    for code, pdate, order_code, ptype, mode, amount, ref in rows:
        db.add(Payment(receipt_code=code, date=_d(pdate), order_id=orders[order_code].id,
                        payment_type=ptype, payment_mode=mode, amount=Decimal(str(amount)),
                        reference_number=ref, received_by="Nikhil"))
    db.commit()
    logger.info("Seeded %d payments", len(rows))


def seed_estimate_line_items(db, estimates, products):
    """Family 21 - Product <-> Estimate Line Item relationship, applied
    to the demo data: each estimate's Material/Labor line items sum to
    exactly that estimate's pre-set material_cost/labor_cost, so the
    flat legacy totals and the real itemization agree. Some lines
    reference a real Product Master entry; others (hardware, generic
    installation/labor) deliberately have no product_id, demonstrating
    that a line item never requires a catalog entry."""
    if db.query(EstimateLineItem).count() > 0:
        return
    # estimate_code -> [(product_key_or_None, description, category, qty, unit, rate), ...]
    rows = {
        "EST-001": [
            ("WD-SLD-3D", "Sliding Wardrobe - 3 Door", "Material", 1, "Piece", 150000),
            (None, "Hardware & Fittings", "Material", 1, "Lot", 50000),
            (None, "Installation & Labor", "Labor", 1, "Lot", 80000),
        ],
        "EST-002": [
            ("MK-BASE-3", "Modular Kitchen Base Units", "Material", 1, "Lot", 90000),
            ("MK-WALL-3", "Modular Kitchen Wall Units", "Material", 1, "Lot", 50000),
            (None, "Installation & Labor", "Labor", 1, "Lot", 50000),
        ],
        "EST-003": [
            ("Custom CNC Wall Panel - Client Design", "CNC Wall Panel - Client Design", "Material", 1, "Piece", 55000),
            (None, "Installation", "Labor", 1, "Lot", 20000),
        ],
        "EST-004": [
            (None, "Additional Puja Shelf - Material", "Material", 1, "Lot", 30000),
            (None, "Installation & Labor", "Labor", 1, "Lot", 10000),
        ],
        "EST-005": [
            ("TV-FLT-01", "TV Unit - Floating", "Material", 1, "Piece", 45000),
            (None, "Installation & Labor", "Labor", 1, "Lot", 15000),
        ],
    }
    count = 0
    for est_code, items in rows.items():
        estimate = estimates.get(est_code)
        if not estimate:
            continue
        for idx, (product_key, description, category, qty, unit, rate) in enumerate(items):
            product = products.get(product_key) if product_key else None
            amount = Decimal(str(qty)) * Decimal(str(rate))
            db.add(EstimateLineItem(
                estimate_id=estimate.id, product_id=product.id if product else None,
                description=description, category=category,
                quantity=Decimal(str(qty)), unit=unit, rate=Decimal(str(rate)), amount=amount, sort_order=idx,
            ))
            count += 1
    db.commit()
    logger.info("Seeded %d estimate line items", count)


def seed_payments(db, orders):
    """Amounts deliberately match each order's advance/other_received
    values from seed_orders exactly, rather than introduce new numbers -
    otherwise an order's stored total_received/balance would silently
    disagree with the sum of its own payment records. This also gives a
    realistic spread for dashboard testing without needing separate
    "fully paid" fixtures: WC-2026-005 has zero payments (fully
    pending), WC-2026-003/004 have only an advance (partially paid),
    WC-2026-001/002 have an advance plus a progress payment."""
    if db.query(Payment).count() > 0:
        return
    rows = [
        ("WC-2026-001", "Advance", "Bank Transfer", 32500, "2026-07-20", "Ravi", "First advance on booking"),
        ("WC-2026-001", "Progress Payment", "UPI", 97500, "2026-08-05", "Ravi", "Progress payment - cutting stage"),
        ("WC-2026-002", "Advance", "Cash", 21600, "2026-07-22", "Devendra", "Advance received"),
        ("WC-2026-002", "Progress Payment", "Bank Transfer", 64800, "2026-08-08", "Devendra", "Progress payment - material purchase"),
        ("WC-2026-003", "Advance", "UPI", 25000, "2026-07-25", "Devendra", "Design advance"),
        ("WC-2026-004", "Advance", "Cash", 25000, "2026-07-26", "Ravi", "Booking advance"),
    ]
    count = 0
    for order_code, ptype, mode, amount, pdate, received_by, remarks in rows:
        db.add(Payment(
            receipt_code=f"RCPT-{count + 1:03d}", order_id=orders[order_code].id,
            date=_d(pdate), payment_type=ptype, payment_mode=mode,
            amount=Decimal(str(amount)), received_by=received_by, remarks=remarks,
        ))
        count += 1
    db.commit()
    logger.info("Seeded %d payments", count)


def seed_project_expenses(db, orders):
    if db.query(ProjectExpense).count() > 0:
        return
    rows = [
        ("EXP-001", "2026-07-21", "WC-2026-001", "Raw Material", "HDHMR and laminate", "Supplier", 85000),
        ("EXP-002", "2026-07-24", "WC-2026-001", "Labour", "Carpentry labour", "Ravi Team", 28000),
        ("EXP-003", "2026-07-23", "WC-2026-002", "Raw Material", "Plywood and laminate", "Supplier", 72000),
        ("EXP-004", "2026-07-25", "WC-2026-002", "Hardware", "Hinges and channels", "Hardware Hub", 26000),
        ("EXP-005", "2026-07-26", "WC-2026-003", "Raw Material", "MDF sheets", "Supplier", 18000),
        ("EXP-006", "2026-07-27", "WC-2026-004", "Paint/PU", "PU material", "Paint Solutions", 14000),
        ("EXP-007", "2026-07-28", "WC-2026-004", "Labour", "Carving labour", "CNC Team", 12000),
    ]
    for code, edate, order_code, cat, desc, paid_to, amount in rows:
        db.add(ProjectExpense(expense_code=code, date=_d(edate), order_id=orders[order_code].id,
                               category=cat, description=desc, paid_to=paid_to,
                               amount=Decimal(str(amount)), approved_by="Nikhil"))
    db.commit()
    logger.info("Seeded %d project expenses", len(rows))


def seed_purchases(db, suppliers, materials):
    if db.query(Purchase).count() > 0:
        return
    rows = [
        ("PUR-001", "2026-07-20", "SUP-002", "MAT-001", 20, "Sheets", 1800, 36000, 18, 6480, 42480, "Paid"),
        ("PUR-002", "2026-07-21", "SUP-001", "MAT-002", 15, "Sheets", 2400, 36000, 18, 6480, 42480, "Part Paid"),
        ("PUR-003", "2026-07-22", "SUP-003", "MAT-004", 30, "Sheets", 950, 28500, 18, 5130, 33630, "Credit"),
        ("PUR-004", "2026-07-22", "SUP-004", "MAT-006", 100, "Nos", 145, 14500, 18, 2610, 17110, "Paid"),
        ("PUR-005", "2026-07-23", "SUP-004", "MAT-009", 300, "Metres", 18, 5400, 18, 972, 6372, "Paid"),
        ("PUR-006", "2026-07-24", "SUP-005", "MAT-010", 20, "Litres", 620, 12400, 18, 2232, 14632, "Credit"),
        ("PUR-007", "2026-07-25", "SUP-004", "MAT-007", 20, "Sets", 480, 9600, 18, 1728, 11328, "Paid"),
    ]
    for code, pdate, sup_code, mat_code, qty, unit, rate, taxable, gst_pct, gst_amt, total, status in rows:
        db.add(Purchase(purchase_code=code, date=_d(pdate), supplier_id=suppliers[sup_code].id,
                         material_id=materials[mat_code].id, quantity=Decimal(str(qty)), unit=unit,
                         rate=Decimal(str(rate)), taxable_value=Decimal(str(taxable)),
                         gst_percent=Decimal(str(gst_pct)), gst_amount=Decimal(str(gst_amt)),
                         invoice_total=Decimal(str(total)), payment_status=status))
    db.commit()
    logger.info("Seeded %d purchases", len(rows))


def seed_issues(db, orders, materials):
    if db.query(Issue).count() > 0:
        return
    rows = [
        ("ISS-001", "2026-07-23", "WC-2026-001", "MAT-001", 18, "Sheets", "Ravi", "Assembly", "Wardrobe and bed"),
        ("ISS-002", "2026-07-23", "WC-2026-001", "MAT-004", 22, "Sheets", "Madan", "Edge Banding", "Interior laminate"),
        ("ISS-003", "2026-07-24", "WC-2026-002", "MAT-002", 20, "Sheets", "Devendra", "CNC", "Kitchen boxes"),
        ("ISS-004", "2026-07-24", "WC-2026-002", "MAT-006", 90, "Nos", "Ravi", "Assembly", "Kitchen shutters"),
        ("ISS-005", "2026-07-25", "WC-2026-003", "MAT-003", 12, "Sheets", "Devendra", "CNC", "3D carving"),
        ("ISS-006", "2026-07-25", "WC-2026-001", "MAT-009", 380, "Metres", "Madan", "Edge Banding", "Wardrobe edges"),
        ("ISS-007", "2026-07-26", "WC-2026-004", "MAT-001", 14, "Sheets", "Devendra", "CNC", "Mandir panels"),
        ("ISS-008", "2026-07-27", "WC-2026-004", "MAT-010", 9, "Litres", "Arpit", "Painting", "PU finishing"),
        ("ISS-009", "2026-07-28", "WC-2026-002", "MAT-007", 18, "Sets", "Ravi", "Assembly", "Drawers"),
    ]
    for code, idate, order_code, mat_code, qty, unit, issued_to, dept, purpose in rows:
        db.add(Issue(issue_code=code, date=_d(idate), order_id=orders[order_code].id,
                      material_id=materials[mat_code].id, quantity_issued=Decimal(str(qty)),
                      unit=unit, issued_to=issued_to, department=dept, purpose=purpose,
                      approved_by="Nikhil"))
    db.commit()
    logger.info("Seeded %d issues", len(rows))


def seed_employees(db):
    if db.query(Employee).count() > 0:
        return {e.employee_code: e for e in db.query(Employee).all()}
    rows = [
        # code, name, dept, designation, phone, joined, salary, emergency, remarks,
        # pan, uan, bank_name, bank_account_number, tax_regime
        ("EMP-001", "Pankaj", "Assembly", "Senior Carpenter", "98XXXXXX01", "2026-04-01", 22000, "98XXXXXX11", "Senior carpenter",
         "ABCPK1234A", "100200300401", "State Bank of India", "112233440001", "New"),
        ("EMP-002", "Ravi", "Panel Saw", "Carpenter", "98XXXXXX02", "2026-04-10", 19000, "98XXXXXX12", "Carpenter",
         "ABCPR5678B", "100200300402", "Bank of Baroda", "112233440002", "Old"),
        ("EMP-003", "Devendra", "CNC", "CNC Operator", "98XXXXXX03", "2026-05-01", 20000, "98XXXXXX13", "Carpenter, CNC operator",
         "ABCPD9012C", "100200300403", "State Bank of India", "112233440003", "New"),
        ("EMP-004", "Shweta", "Design", "Interior Designer", "98XXXXXX04", "2026-04-05", 24000, "98XXXXXX14", "Interior designer",
         "ABCPS3456D", "100200300404", "HDFC Bank", "112233440004", "New"),
        ("EMP-005", "Shivani", "Design", "Interior Designer", "98XXXXXX05", "2026-05-20", 22000, "98XXXXXX15", "Interior designer",
         "ABCPS7890E", "100200300405", "ICICI Bank", "112233440005", "Old"),
        ("EMP-006", "Arpit", "Assembly", "Helper", "98XXXXXX06", "2026-06-01", 15000, "98XXXXXX16", "Helper",
         None, None, "State Bank of India", "112233440006", "New"),
        ("EMP-007", "Madan", "Edge Banding", "Helper", "98XXXXXX07", "2026-06-01", 14500, "98XXXXXX17", "Helper",
         None, None, None, None, None),
        ("EMP-008", "Chhoutu", "Installation", "Helper", "98XXXXXX08", "2026-06-15", 14000, "98XXXXXX18", "Helper",
         None, None, None, None, None),
    ]
    out = {}
    for code, name, dept, designation, phone, joined, salary, emergency, remarks, pan, uan, bank_name, acc_no, regime in rows:
        e = Employee(employee_code=code, name=name, department=dept, designation=designation, phone=phone,
                     joining_date=_d(joined), monthly_salary=Decimal(str(salary)),
                     status="Active", emergency_contact=emergency, remarks=remarks,
                     pan=pan, uan=uan, bank_name=bank_name, bank_account_number=acc_no, tax_regime=regime)
        db.add(e)
        out[code] = e
    db.commit()
    logger.info("Seeded %d employees", len(rows))
    return out


def seed_salary_slips(db, employees):
    """Multiple employees, multiple months - net_salary is computed the
    same way the real create_salary_slip endpoint does (sum of
    earnings minus sum of deductions), verified by hand before being
    written here, not just eyeballed."""
    if db.query(SalarySlip).count() > 0:
        return
    rows = [
        # code, month, year, working_days, paid_days, basic, da, hra, overtime,
        # pf, tds, other_deductions, status
        ("EMP-001", "May", "2026", 26, 26, 9500, 500, 6000, 1500, 1140, 0, 300, "paid"),
        ("EMP-001", "June", "2026", 26, 26, 9500, 500, 6000, 1200, 1140, 0, 300, "paid"),
        ("EMP-001", "July", "2026", 26, 25, 9500, 500, 6000, 800, 1140, 0, 300, "finalized"),
        ("EMP-004", "May", "2026", 26, 26, 11000, 0, 6500, 0, 1320, 500, 200, "paid"),
        ("EMP-004", "June", "2026", 26, 26, 11000, 0, 6500, 1000, 1320, 500, 200, "finalized"),
        ("EMP-006", "June", "2026", 26, 26, 7000, 0, 3000, 0, 0, 0, 200, "draft"),
    ]
    count = 0
    for code, month, year, wd, pd, basic, da, hra, ot, pf, tds, other, status in rows:
        employee = employees.get(code)
        if not employee:
            continue
        net_salary = Decimal(str(basic + da + hra + ot - pf - tds - other))
        slip = SalarySlip(
            employee_id=employee.id, month=month, year=year,
            working_days=Decimal(str(wd)), paid_days=Decimal(str(pd)),
            basic=Decimal(str(basic)), da=Decimal(str(da)), hra=Decimal(str(hra)),
            overtime_amount=Decimal(str(ot)), pf_deduction=Decimal(str(pf)),
            tds_deduction=Decimal(str(tds)), other_deductions=Decimal(str(other)),
            net_salary=net_salary, status=status,
        )
        db.add(slip)
        count += 1
    db.commit()
    logger.info("Seeded %d salary slips", count)


def seed_leaves(db, employees):
    """A few real Approved leave records for the same employees covered
    by seed_salary_slips, so the salary slip PDF's Leave Balance field
    has real, non-empty data to demonstrate rather than always showing
    "no leave taken"."""
    if db.query(Leave).count() > 0:
        return
    rows = [
        # code, leave_type, start_date, end_date, days, reason
        ("EMP-001", "SL", "2026-05-12", "2026-05-13", 2, "Fever"),
        ("EMP-001", "CL", "2026-06-20", "2026-06-20", 1, "Personal work"),
        ("EMP-004", "PL", "2026-05-08", "2026-05-08", 1, "Family function"),
    ]
    count = 0
    for code, leave_type, start, end, days, reason in rows:
        employee = employees.get(code)
        if not employee:
            continue
        db.add(Leave(
            employee_id=employee.id, leave_type=leave_type, start_date=_d(start), end_date=_d(end),
            days=Decimal(str(days)), reason=reason, status="Approved", approved_by="Nikhil Soni",
        ))
        count += 1
    db.commit()
    logger.info("Seeded %d leave records", count)


def seed_attendance(db, employees):
    if db.query(Attendance).count() > 0:
        return
    rows = [
        ("2026-07-28", "EMP-001", "2026-07-28 09:00", "2026-07-28 18:30", "Present", None),
        ("2026-07-28", "EMP-002", "2026-07-28 09:10", "2026-07-28 18:15", "Present", None),
        ("2026-07-28", "EMP-003", "2026-07-28 09:05", "2026-07-28 18:00", "Present", None),
        ("2026-07-28", "EMP-004", "2026-07-28 09:20", "2026-07-28 17:50", "Present", None),
        ("2026-07-28", "EMP-005", "2026-07-28 08:45", "2026-07-28 19:00", "Present", "Site visit"),
        ("2026-07-27", "EMP-004", None, None, "Absent", None),
        ("2026-07-28", "EMP-006", "2026-07-28 09:00", "2026-07-28 13:00", "Half Day", "Half day - personal work"),
    ]
    for adate, emp_code, in_t, out_t, status, remarks in rows:
        db.add(Attendance(date=_d(adate), employee_id=employees[emp_code].id,
                           in_time=_dt(in_t) if in_t else None, out_time=_dt(out_t) if out_t else None,
                           standard_hours=Decimal("8"), attendance_status=status, remarks=remarks))
    db.commit()
    logger.info("Seeded %d attendance records", len(rows))


def seed_daily_tasks(db, employees, orders):
    if db.query(DailyTask).count() > 0:
        return {t.task_code: t for t in db.query(DailyTask).all()}
    rows = [
        ("TSK-001", "2026-07-28", "EMP-001", "WC-2026-002", "Cut base cabinet panels", "Urgent", "09:00", "12:00", "DONE", 100, None),
        ("TSK-002", "2026-07-28", "EMP-003", "WC-2026-001", "Edge band wardrobe shutters", "High", "09:30", "13:30", "DOING", 65, None),
        ("TSK-003", "2026-07-28", "EMP-002", "WC-2026-001", "Assemble bed storage boxes", "High", "10:00", "17:00", "DOING", 50, None),
        ("TSK-004", "2026-07-28", "EMP-004", "WC-2026-004", "First PU primer coat", "Medium", "11:00", "16:00", "TO DO", 0, None),
        ("TSK-005", "2026-07-28", "EMP-005", "WC-2026-001", "Site measurement verification", "Urgent", "09:00", "11:00", "DONE", 100, None),
        ("TSK-006", "2026-07-29", "EMP-001", "WC-2026-003", "3D roughing toolpath", "High", "09:00", "14:00", "TO DO", 0, None),
        ("TSK-007", "2026-07-29", "EMP-003", "WC-2026-002", "Edge band base cabinets", "High", "10:00", "16:00", "TO DO", 0, None),
        ("TSK-008", "2026-07-29", "EMP-002", "WC-2026-002", "Assemble wall cabinets", "High", "09:00", "17:00", "TO DO", 0, None),
        ("TSK-009", "2026-07-29", "EMP-004", "WC-2026-004", "Sanding after primer", "Medium", "10:00", "15:00", "TO DO", 0, None),
        ("TSK-010", "2026-07-29", "EMP-005", "WC-2026-001", "Prepare installation hardware", "Medium", "12:00", "16:00", "TO DO", 0, None),
        # Blocked - required demo case.
        ("TSK-011", "2026-07-30", "EMP-004", "WC-2026-004", "Apply final laminate finish", "High", "09:00", "13:00", "BLOCKED", 20, "Waiting for laminate"),
        # Overdue - past date, still not Completed.
        ("TSK-012", "2026-07-15", "EMP-002", "WC-2026-002", "Fit soft-close hinges", "Urgent", "09:00", "12:00", "DOING", 30, None),
    ]
    out = {}
    for code, tdate, emp_code, order_code, desc, priority, start, end, status, completion, delay in rows:
        t = DailyTask(task_code=code, date=_d(tdate), employee_id=employees[emp_code].id,
                       order_id=orders[order_code].id, task_description=desc, priority=priority,
                       planned_start=_t(start), planned_end=_t(end), status=status,
                       completion_percent=completion, checked_by="Nikhil", delay_reason=delay,
                       created_by="nikhil@woodfulcreations.com")
        db.add(t)
        out[code] = t
    db.commit()

    # Handoff chain - Measure -> Drawing -> Cutting, same order, each
    # linked to the one before it via previous_task_id.
    measure = DailyTask(
        task_code="TSK-013", date=_d("2026-07-20"), employee_id=employees["EMP-005"].id,
        order_id=orders["WC-2026-001"].id, task_description="Measure wardrobe opening",
        priority="High", status="DONE", completion_percent=100, created_by="nikhil@woodfulcreations.com",
    )
    db.add(measure)
    db.commit()
    drawing = DailyTask(
        task_code="TSK-014", date=_d("2026-07-21"), employee_id=employees["EMP-004"].id,
        order_id=orders["WC-2026-001"].id, task_description="Prepare cutting drawing",
        priority="High", status="DONE", completion_percent=100, created_by="nikhil@woodfulcreations.com",
        previous_task_id=measure.id,
    )
    db.add(drawing)
    db.commit()
    cutting = DailyTask(
        task_code="TSK-015", date=_d("2026-07-22"), employee_id=employees["EMP-001"].id,
        order_id=orders["WC-2026-001"].id, task_description="Cut plywood for wardrobe",
        priority="High", status="DOING", completion_percent=40, created_by="nikhil@woodfulcreations.com",
        previous_task_id=drawing.id,
    )
    db.add(cutting)
    out["TSK-013"] = measure
    out["TSK-014"] = drawing
    out["TSK-015"] = cutting

    # Subtasks under a parent "Wardrobe" task.
    parent = DailyTask(
        task_code="TSK-016", date=_d("2026-07-25"), employee_id=employees["EMP-001"].id,
        order_id=orders["WC-2026-001"].id, task_description="Wardrobe - full build",
        priority="High", status="DOING", completion_percent=30, created_by="nikhil@woodfulcreations.com",
    )
    db.add(parent)
    db.commit()
    sub1 = DailyTask(
        task_code="TSK-017", date=_d("2026-07-26"), employee_id=employees["EMP-002"].id,
        order_id=orders["WC-2026-001"].id, task_description="Assembly", priority="Medium",
        status="TO DO", completion_percent=0, created_by="nikhil@woodfulcreations.com",
        parent_task_id=parent.id,
    )
    sub2 = DailyTask(
        task_code="TSK-018", date=_d("2026-07-27"), employee_id=employees["EMP-005"].id,
        order_id=orders["WC-2026-001"].id, task_description="Installation", priority="Medium",
        status="TO DO", completion_percent=0, created_by="nikhil@woodfulcreations.com",
        parent_task_id=parent.id,
    )
    db.add_all([sub1, sub2])
    out["TSK-016"] = parent
    out["TSK-017"] = sub1
    out["TSK-018"] = sub2
    db.commit()

    logger.info("Seeded %d daily tasks", len(out))
    return out


def seed_task_comments(db, tasks):
    if db.query(TaskComment).count() > 0:
        return
    rows = [
        ("TSK-002", "Pankaj", "Started edge banding, laminate quality is good."),
        ("TSK-011", "Madan", "Laminate received. Ready for cutting."),
        ("TSK-015", "Pankaj", "Cutting in progress, on schedule for tomorrow."),
    ]
    count = 0
    for code, author, text in rows:
        task = tasks.get(code)
        if not task:
            continue
        db.add(TaskComment(task_id=task.id, author=author, text=text, date=task.date))
        count += 1
    db.commit()
    logger.info("Seeded %d task comments", count)


def seed_production_jobs(db, employees, orders, materials):
    if db.query(ProductionJob).count() > 0:
        return
    rows = [
        ("JOB-001", "2026-07-28", "CNC Router", "EMP-001", "WC-2026-002", "Panel cutting", "Cutting", "MAT-002", 18, 18, "09:00", "12:00", "Completed"),
        ("JOB-002", "2026-07-28", "Edge Bander", "EMP-003", "WC-2026-001", "Edge banding", "Edge Banding", "MAT-009", 32, 20, "09:30", "13:30", "In Progress"),
        ("JOB-003", "2026-07-28", "Cold Press", "EMP-002", "WC-2026-001", "Laminate pressing", None, "MAT-001", 12, 12, "10:00", "12:30", "Completed"),
        ("JOB-004", "2026-07-28", "PU Paint Setup", "EMP-004", "WC-2026-004", "Primer coat", "Finishing", "MAT-010", 8, 0, "11:00", "16:00", "Not Started"),
        ("JOB-005", "2026-07-29", "CNC Router", "EMP-001", "WC-2026-003", "3D roughing", "CNC / Drilling", "MAT-003", 4, 0, "09:00", "14:00", "Not Started"),
        ("JOB-006", "2026-07-29", "Panel Saw", "EMP-002", "WC-2026-002", "Strip cutting", "Cutting", "MAT-002", 15, 0, "09:00", "11:00", "Not Started"),
    ]
    for code, jdate, machine, emp_code, order_code, op, stage, mat_code, planned, completed, start, end, status in rows:
        db.add(ProductionJob(job_code=code, date=_d(jdate), machine=machine,
                              employee_id=employees[emp_code].id, order_id=orders[order_code].id,
                              operation=op, stage=stage, material_id=materials[mat_code].id,
                              planned_qty=planned, completed_qty=completed,
                              start_time=_t(start), end_time=_t(end), status=status))
    db.commit()
    logger.info("Seeded %d production jobs", len(rows))


def seed_company_holidays(db):
    """Demonstrates the working calendar system with genuinely verified
    dates (each weekday checked directly, not assumed) - Independence
    Day and Gandhi Jayanti both fall on real working weekdays in 2026,
    so declaring them holidays genuinely reduces that month's working-day
    count. One special working day (a Sunday) is included too, to
    demonstrate the other side of the same model."""
    if db.query(CompanyHoliday).count() > 0:
        return
    rows = [
        ("2026-08-15", "Independence Day", False, None),
        ("2026-10-02", "Gandhi Jayanti", False, None),
        ("2026-08-09", "Special working Sunday - order backlog", True, "Declared working to catch up on pending orders"),
    ]
    for hdate, name, is_working, remarks in rows:
        db.add(CompanyHoliday(date=_d(hdate).date(), name=name, is_working=is_working, remarks=remarks))
    db.commit()
    logger.info("Seeded %d company holiday/calendar records", len(rows))


def seed_notifications(db, materials, orders, employees, tasks):
    """Grounded entirely in already-seeded real entities - a material
    genuinely at/below its minimum stock, an order with a genuinely
    unpaid balance, a real employee's real task - rather than invented
    numbers that could drift out of sync with the actual seeded data."""
    if db.query(Notification).count() > 0:
        return
    low_stock_material = materials.get("MAT-003")  # MDF 12mm, seeded at 0 stock against a minimum of 10
    if low_stock_material:
        NotificationService.notify(
            db, notification_type="OUT_OF_STOCK", severity="CRITICAL",
            title=f"{low_stock_material.name} is out of stock",
            message=f"Current stock is 0, below the minimum of {low_stock_material.minimum_stock}.",
            related_entity_type="material", related_entity_id=low_stock_material.id,
            action_path=f"/materials/{low_stock_material.id}",
        )

    pending_order = orders.get("WC-2026-005")  # Showroom Display - zero payments received
    if pending_order:
        NotificationService.notify(
            db, notification_type="PAYMENT_PENDING", severity="WARNING",
            title=f"No payment received yet for {pending_order.order_code}",
            message=f"Order value is Rs {pending_order.order_value:,.0f} with no advance recorded.",
            related_entity_type="order", related_entity_id=pending_order.id,
            action_path=f"/orders/{pending_order.id}",
        )

    urgent_order = orders.get("WC-2026-002")  # Modular Kitchen - marked Urgent priority in seed_orders
    if urgent_order:
        NotificationService.notify(
            db, notification_type="DELIVERY_UPCOMING", severity="WARNING",
            title=f"{urgent_order.order_code} delivery approaching",
            message=f"Priority: {urgent_order.priority}. Delivery date: {urgent_order.delivery_date.strftime('%d %b %Y')}.",
            related_entity_type="order", related_entity_id=urgent_order.id,
            action_path=f"/orders/{urgent_order.id}",
        )

    emp_001 = employees.get("EMP-001")
    emp_001_task = next((t for t in tasks.values() if t.employee_id == emp_001.id), None) if emp_001 else None
    if emp_001_task:
        NotificationService.notify(
            db, notification_type="TASK_ASSIGNED", severity="INFO",
            title=f"Task assigned: {emp_001_task.task_description}",
            message=f"Assigned to {emp_001.name}.",
            related_entity_type="task", related_entity_id=emp_001_task.id,
            action_path=f"/daily-tasks/{emp_001_task.id}",
        )
    logger.info("Seeded notifications")


def run_seed(db):
    """The full idempotent seed sequence - shared by the CLI entry point
    below and the Family 21 demo reset endpoint
    (api/routes/demo_reset.py), so there is exactly one place that
    defines "what does a freshly seeded Woodful demo environment
    contain" rather than two copies that could drift apart. Every
    seed_* function here already guards itself with a
    `if db.query(Model).count() > 0: return` (or equivalent) check, so
    calling this again against a database that already has data is
    always a safe no-op re-scan, never a duplicate insert."""
    seed_master_users(db)
    locations = seed_locations(db)
    subcategories = seed_material_hierarchy(db)
    seed_lookups(db)
    suppliers = seed_suppliers(db)
    named_suppliers = seed_named_suppliers(db)
    materials = seed_materials(db, suppliers, locations, subcategories)
    seed_supplier_materials(db, suppliers, named_suppliers, materials)
    product_subcategories = seed_product_categories(db)
    products = seed_products(db, product_subcategories, materials)
    clients = seed_clients(db)
    orders = seed_orders(db, clients)
    seed_order_items(db, orders, products)
    estimates = seed_estimates(db, clients, orders)
    seed_estimate_line_items(db, estimates, products)
    seed_payments(db, orders)
    seed_project_expenses(db, orders)
    seed_purchases(db, suppliers, materials)
    seed_issues(db, orders, materials)
    employees = seed_employees(db)
    seed_salary_slips(db, employees)
    seed_leaves(db, employees)
    seed_attendance(db, employees)
    tasks = seed_daily_tasks(db, employees, orders)
    seed_task_comments(db, tasks)
    seed_production_jobs(db, employees, orders, materials)
    seed_company_holidays(db)
    seed_notifications(db, materials, orders, employees, tasks)
    logger.info("Seed complete.")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()
