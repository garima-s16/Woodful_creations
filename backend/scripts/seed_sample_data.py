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

from app.core.database import SessionLocal
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
from app.models.product import Product, ProductMaterial
from app.models.order_item import OrderItem
from app.models.estimate_line_item import EstimateLineItem
from app.utils.id_generator import generate_business_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def _dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def _t(s):
    return datetime.strptime(s, "%H:%M").time()


def _city_from_address(address):
    """Derives a city token from a '<street>, <City>, Madhya Pradesh -
    <PIN>' style address string, purely by position - never invents a
    city that isn't already present in the address text. Addresses that
    don't have a distinct city segment (e.g. an industrial-area address
    that names the town in the street line itself) simply get no city
    value rather than a guessed one."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 3:
        return parts[-2]
    return None


# ==========================================================================
# Permanent Woodful business-roster data (real Clients/Suppliers/Employees,
# as opposed to the illustrative test/demo data seeded further below).
# Verbatim from the business - names, phone numbers and addresses are
# never generated, randomized or looked up; this is the single source of
# truth these three seed functions read from, so re-running the seed can
# never drift from these exact values.
# ==========================================================================
WOODFUL_CLIENTS = [
    # (name, phone, address)
    ("Sanket", "7864678341", "24 Saket Nagar, Indore, Madhya Pradesh - 452018"),
    ("Ishu", "7864678342", "70 Indrapuri, Mhow, Madhya Pradesh - 453441"),
    ("Ashu", "7864678343", "18 Vijay Nagar, Indore, Madhya Pradesh - 452010"),
    ("Shrangi", "7009870098", "42 Scheme No. 54, Indore, Madhya Pradesh - 452010"),
    ("Nimisha", "7864678345", "15 Nehru Nagar, Bhopal, Madhya Pradesh - 462003"),
    ("Siddharth", "7864678346", "31 Freeganj, Ujjain, Madhya Pradesh - 456001"),
    ("Priya", "7864678347", "56 Arera Colony, Bhopal, Madhya Pradesh - 462016"),
    ("Meenal", "7864678348", "12 AB Road, Rau, Madhya Pradesh - 453331"),
    ("Mayank", "7864678349", "28 Civil Lines, Dewas, Madhya Pradesh - 455001"),
    ("Madhuri", "7864678350", "9 Sudama Nagar, Indore, Madhya Pradesh - 452009"),
    ("Brajwal", "7864678351", "17 Navlakhi, Indore, Madhya Pradesh - 452001"),
    ("Behlool", "7864678352", "63 Pithampur Sector 1, Madhya Pradesh - 454775"),
    ("Srishti", "7864678353", "21 Saket Nagar, Bhopal, Madhya Pradesh - 462024"),
    ("Rahul", "7864678354", "45 Rau Main Road, Rau, Madhya Pradesh - 453331"),
    ("Sakina", "7864678355", "11 Jawahar Marg, Indore, Madhya Pradesh - 452002"),
    ("Aviral", "7864678356", "37 Nehru Nagar, Indore, Madhya Pradesh - 452008"),
    ("Mahek", "7864678357", "19 Khandwa Road, Indore, Madhya Pradesh - 452020"),
    ("Mahak", "7864678358", "52 Geeta Bhawan, Indore, Madhya Pradesh - 452001"),
    ("Ashutosh", "7864678359", "14 Shastri Nagar, Ujjain, Madhya Pradesh - 456010"),
    ("Arpita", "7864678360", "26 Palasia, Indore, Madhya Pradesh - 452001"),
    ("Mansi", "7864678361", "8 Vijay Nagar, Indore, Madhya Pradesh - 452010"),
    ("Jayashree", "7864678362", "33 MP Nagar, Bhopal, Madhya Pradesh - 462011"),
    ("Hamzah", "7864678363", "16 Jahangirabad, Bhopal, Madhya Pradesh - 462008"),
    ("Sangita Priyadarshini", "7864678364", "29 Annapurna Road, Indore, Madhya Pradesh - 452009"),
    ("Sangita", "7864678365", "41 Malwa Mill, Indore, Madhya Pradesh - 452002"),
    ("Pravesh", "7864678366", "22 Freeganj, Ujjain, Madhya Pradesh - 456001"),
    ("Ashish", "7864678367", "39 Rau Road, Indore, Madhya Pradesh - 453331"),
    ("Netra Pawar", "7864678368", "7 Navlakhi, Indore, Madhya Pradesh - 452001"),
    ("Gaurav", "7864678369", "61 Pithampur Sector 3, Madhya Pradesh - 454775"),
    ("Aditya Mire", "7864678370", "13 Vijay Nagar, Indore, Madhya Pradesh - 452010"),
    ("Gunjan", "7864678371", "35 Arera Colony, Bhopal, Madhya Pradesh - 462016"),
    ("Atif", "7864678372", "20 Mhow Cantt, Mhow, Madhya Pradesh - 453441"),
    ("Nilam", "7864678373", "48 Dhar Road, Dhar, Madhya Pradesh - 454001"),
    ("Deepti", "7864678374", "10 Saket Nagar, Indore, Madhya Pradesh - 452018"),
    ("Chetan", "7864678375", "27 AB Road, Indore, Madhya Pradesh - 452016"),
    ("Sagar Khona", "7864678376", "54 Vijay Nagar, Indore, Madhya Pradesh - 452010"),
    ("Sharad", "7864678377", "32 Freeganj, Ujjain, Madhya Pradesh - 456001"),
    ("Kuldeep", "7864678378", "6 Dewas Naka, Indore, Madhya Pradesh - 452010"),
]

WOODFUL_SUPPLIERS = [
    # (name, phone, address)
    ("Aniket", "7864678379", "25 Siyaganj, Indore, Madhya Pradesh - 452007"),
    ("Pallishree", "7864678380", "18 Rau Industrial Area, Rau, Madhya Pradesh - 453331"),
    ("Sombodhana", "7864678381", "44 Pithampur Industrial Area, Madhya Pradesh - 454775"),
    ("Catalina", "7864678382", "9 MG Road, Indore, Madhya Pradesh - 452001"),
    ("Sumit Mathew", "7864678383", "31 Lasudia, Indore, Madhya Pradesh - 452010"),
    ("Ruturaj", "7864678384", "16 Dewas Naka, Indore, Madhya Pradesh - 452010"),
    ("Pragati", "7864678385", "23 Industrial Area, Dewas, Madhya Pradesh - 455001"),
    ("Nisha", "7864678386", "12 Dhar Road, Indore, Madhya Pradesh - 452002"),
    ("Prathamesh", "7864678387", "38 Mhow Road, Mhow, Madhya Pradesh - 453441"),
    ("Vignesh", "7864678388", "20 Sanwer Road, Indore, Madhya Pradesh - 452015"),
]

WOODFUL_EMPLOYEES = [
    # (name, phone, address, role) - role must be kept exactly as given
    ("Shweta", "7864678389", "15 Vijay Nagar, Indore, Madhya Pradesh - 452010", "Designer"),
    ("Shivani", "7864678390", "28 Saket Nagar, Indore, Madhya Pradesh - 452018", "Designer"),
    ("Pankaj", "7864678391", "42 Rau Main Road, Rau, Madhya Pradesh - 453331", "Carpenter"),
    ("Ravi", "7864678392", "19 Sudama Nagar, Indore, Madhya Pradesh - 452009", "Carpenter"),
    ("Devendra", "7864678393", "33 Mhow Road, Mhow, Madhya Pradesh - 453441", "Carpenter"),
    ("Arpit", "7864678394", "11 Nehru Nagar, Bhopal, Madhya Pradesh - 462003", "Helper"),
    ("Madan", "7864678395", "26 Freeganj, Ujjain, Madhya Pradesh - 456001", "Helper"),
    ("Chhoutu", "7864678396", "37 Industrial Area, Dewas, Madhya Pradesh - 455001", "Helper"),
]

# Master Users - real names, MASTER permissions only. Never seeded as
# Client/Supplier/Employee rows.
WOODFUL_MASTER_USERS = [
    # (username, email, full_name, password_env_var)
    ("nikhils", "nikhil@woodful.local", "Nikhil Soni", "SEED_NIKHIL_PASSWORD"),
    ("garimas", "garima@woodful.local", "Garima Sharma", "SEED_GARIMA_PASSWORD"),
]

# Reserved future test-user pool (Section "FUTURE TEST-USER POOL"). Kept
# here only as names for later use - deliberately NOT seeded as Clients,
# Suppliers or Employees, and no phone/address/database rows are
# generated for them.
FUTURE_TEST_USER_POOL = [
    "Ashutosh Shukla", "Harsh Tiwari", "Bilal Siddiqui", "Harsh Rusia",
    "Hitesh Tiwari", "Harshita Verma", "Gaurang Trivedi", "Dinsha Saluja",
    "Asmita Singh", "Astha Porwal", "Ayushi", "Aayush", "Aashutosh Pandey",
    "Urja", "Pranshoo", "Jay Verma", "Prachi Agrawal", "Dhanashree",
    "Harsha", "Harshit Methi", "Hitesh Goyal", "Priyanka Sharma",
    "Rishabh Singh", "Abhishek Sharma", "Shweta Goyal",
]


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

    workshop = Location(name="Main Workshop", location_type="Warehouse", business_id=generate_business_id(db))
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
        area = Location(name=area_name, location_type="Area", parent_id=workshop.id, business_id=generate_business_id(db))
        db.add(area)
        db.flush()
        out[area_name] = area
        for rack_name in racks:
            rack = Location(name=rack_name, location_type="Rack", parent_id=area.id, business_id=generate_business_id(db))
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
    """Two named master admin accounts (Nikhil Soni, Garima Sharma) with
    independent passwords and usernames, per repeated explicit request.

    Each account's password comes from its own env var
    (SEED_NIKHIL_PASSWORD / SEED_GARIMA_PASSWORD) - never hard-coded,
    and never shared between the two accounts, so one can be rotated
    without touching the other. If an account's env var isn't set:
      - a NEW account for that person is skipped entirely (with a
        loud warning - see below), same as before.
      - an EXISTING account for that person keeps its current
        password untouched - the var is only used to (re)create or
        explicitly reset a password, never required just to keep an
        already-working account working.

    Idempotent and non-destructive: for an existing account (matched
    by email - the roster's own stable identifier for each person),
    full_name and username are corrected to the exact roster values in
    place (so a roster username change like this one actually reaches
    an already-seeded account, not just brand-new ones), but role,
    is_active and cannot_be_deleted are never touched here, and the
    password is only touched if that person's env var is explicitly
    set."""
    from app.core.security import hash_password
    from app.models.user import User

    created = 0
    updated = 0
    password_reset = 0
    for username, email, full_name, password_env_var in WOODFUL_MASTER_USERS:
        password = os.environ.get(password_env_var)
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.full_name != full_name:
                existing.full_name = full_name
                updated += 1
            if existing.username != username:
                existing.username = username
                updated += 1
            if password:
                existing.password_hash = hash_password(password)
                password_reset += 1
            continue
        if not password:
            banner = (
                "\n" + "!" * 78 + "\n"
                f"!!  {password_env_var} is not set - the {full_name} master account\n"
                "!!  ({email}) will NOT be created. If this is your only master\n"
                "!!  account, you will be LOCKED OUT after this seed run finishes.\n"
                "!!  Stop now and run instead:\n"
                "!!\n"
                f"!!      export {password_env_var}='choose-a-real-password'\n"
                "!!      python scripts/seed_sample_data.py\n"
                "!!\n"
                f"!!  (Windows PowerShell: $env:{password_env_var} = 'choose-a-real-password')\n"
                + "!" * 78 + "\n"
            ).format(email=email)
            print(banner)
            logger.warning("%s is not set - skipping creation of the %s master account (%s).",
                            password_env_var, full_name, email)
            continue
        db.add(User(
            username=username, email=email, full_name=full_name, role="master",
            password_hash=hash_password(password), is_active=True, cannot_be_deleted=True,
        ))
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d master user(s)", created)
    if updated:
        logger.info("Corrected %d master user field(s) (username/full name) to match the roster", updated)
    if password_reset:
        logger.info("Reset password for %d existing master user(s) (their env var was set)", password_reset)


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
        ("SUP-006", "Sanket Plywood & Boards", "Plywood", "Sanket", "9856781126", "23ABCDE6234F1Z5", "15 Days", "Alternate plywood/HDHMR supplier"),
        ("SUP-007", "Ashu Hardware House", "Hardware", "Ashu", "9856781127", "23ABCDE7234F1Z5", "7 Days", "Alternate hardware supplier"),
        ("SUP-008", "Shruti Laminates", "Laminate", "Shruti", "9856781128", "23ABCDE8234F1Z5", "15 Days", "Alternate laminate supplier"),
    ]
    out = {s.supplier_code: s for s in db.query(Supplier).filter(Supplier.supplier_code.in_([r[0] for r in rows])).all()}
    created = 0
    for code, name, cat, contact, phone, gstin, terms, remarks in rows:
        if code in out:
            continue
        s = Supplier(supplier_code=code, name=name, category=cat, contact_person=contact,
                      phone=phone, gstin=gstin, payment_terms=terms, remarks=remarks,
                      business_id=generate_business_id(db))
        db.add(s)
        out[code] = s
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d named suppliers", created)
    return out


def seed_woodful_suppliers(db):
    """Upserts the permanent Woodful supplier roster (WOODFUL_SUPPLIERS)
    - added alongside the existing SUP-xxx suppliers, not replacing
    them. Uses its own SUPW-xxx code range so it can never collide with
    SUP-xxx codes. Each roster address is stored in the Supplier
    model's own `address` column.

    Also migrates any SUPW-xxx row created by an older run of this
    script, back when there was no address column and the address was
    stashed in remarks as "Address: <address>" - the address moves
    into the real column and that stopgap remark is cleared, so
    remarks is free again for genuine notes.

    Idempotent per-row by supplier_code, matching seed_named_suppliers'
    own pattern."""
    existing = {
        s.supplier_code: s for s in
        db.query(Supplier).filter(Supplier.supplier_code.like("SUPW-%")).all()
    }
    created = 0
    updated = 0
    for i, (name, phone, address) in enumerate(WOODFUL_SUPPLIERS, start=1):
        code = f"SUPW-{i:03d}"
        row = existing.get(code)
        if row:
            changed = False
            if row.address != address:
                row.address = address
                changed = True
            if row.remarks == f"Address: {address}":
                row.remarks = None
                changed = True
            if changed:
                updated += 1
            continue
        db.add(Supplier(
            supplier_code=code, name=name, category="General Supplier",
            contact_person=name, phone=phone, address=address,
            business_id=generate_business_id(db),
        ))
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d Woodful roster suppliers", created)
    if updated:
        logger.info("Migrated %d Woodful roster supplier(s) onto the address column", updated)


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
        ("SUP-001", "Century Plywood Dealer", "Plywood", "Sanket", "9856781121", "23ABCDE1234F1Z5", "15 Days", "Primary plywood supplier"),
        ("SUP-002", "Greenpanel Distributor", "HDHMR", "Ishu", "9856781122", "23ABCDE2234F1Z5", "Cash", "HDHMR and MDF"),
        ("SUP-003", "Merino Laminates", "Laminate", "Ashu", "9856781123", "23ABCDE3234F1Z5", "30 Days", "Decorative laminates"),
        ("SUP-004", "Hardware Hub", "Hardware", "Mahek", "9856781124", "23ABCDE4234F1Z5", "7 Days", "Hinges and channels"),
        ("SUP-005", "Paint Solutions", "Paint/PU", "Aviral", "9856781125", "23ABCDE5234F1Z5", "Cash", "PU and polish material"),
    ]
    out = {}
    for code, name, cat, contact, phone, gstin, terms, remarks in rows:
        s = Supplier(supplier_code=code, name=name, category=cat, contact_person=contact,
                      phone=phone, gstin=gstin, payment_terms=terms, remarks=remarks,
                      business_id=generate_business_id(db))
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
                      subcategory_id=subcategory_row.id if subcategory_row else None,
                      business_id=generate_business_id(db))
        db.add(m)
        out[code] = m
    db.commit()
    logger.info("Seeded %d materials", len(rows))
    return out


def seed_products(db):
    """Product Master demo catalog - a mix of standard (repeatable
    catalog) and custom (one-off, client-specific) pieces, each with a
    real itemized cost breakdown (material/hardware/labour/machine/
    finish/packing/transport/other + overhead/margin %), the same shape
    a real production cost estimate would use. Names/figures here are
    original demo data, not sourced from any external record."""
    if db.query(Product).count() > 0:
        return {p.product_code: p for p in db.query(Product).all()}
    rows = [
        # code, name, type, category, subcategory, unit, L, W, H, dim_unit, primary_material, finish,
        # mat, hw, labour, machine, finish_c, pack, transport, other, overhead%, margin%, cost, selling
        ("PRD-001", "Harbor 3-Seater Sofa", "standard", "Seating", "Sofas", "Nos",
         84, 36, 32, "in", "Teak frame + linen upholstery", "Natural teak",
         18000, 2500, 6000, 1200, 2000, 800, 1000, 500, 8, 30, 32000, 48000),
        ("PRD-002", "Meridian Coffee Table", "standard", "Tables", "Coffee Tables", "Nos",
         42, 24, 18, "in", "Sheesham solid wood", "Walnut polish",
         4200, 500, 1500, 600, 1000, 300, 500, 200, 8, 30, 8800, 12500),
        ("PRD-003", "Everline 4-Door Wardrobe", "standard", "Storage", "Wardrobes", "Nos",
         72, 24, 84, "in", "BWP Plywood + laminate", "Matte laminate",
         22000, 4500, 6500, 1500, 1800, 700, 900, 400, 8, 28, 38300, 49000),
        ("PRD-004", "Studio Compact TV Unit", "standard", "Storage", "TV Units", "Nos",
         60, 16, 20, "in", "MDF + laminate", "Gloss laminate",
         6500, 1200, 2000, 500, 600, 300, 400, 200, 8, 28, 11700, 15000),
        ("PRD-005", "Northline Dining Table (6-Seater)", "standard", "Tables", "Dining Tables", "Nos",
         72, 36, 30, "in", "Sheesham solid wood", "Natural matte",
         16000, 1500, 4500, 1000, 1500, 600, 900, 400, 8, 30, 26400, 38000),
        ("PRD-006", "Custom Bedroom Suite - Reference Build", "custom", "Bedroom", "Bedroom Sets", "Nos",
         None, None, None, "in", "BWP Plywood + veneer", "PU matte",
         120000, 25000, 45000, 8000, 12000, 3000, 4000, 2000, 8, 25, 219000, 280000),
        ("PRD-007", "Custom Modular Kitchen - Reference Build", "custom", "Kitchen", "Modular Kitchen", "Set",
         None, None, None, "in", "BWP Plywood + laminate + granite top", "Matte laminate",
         85000, 35000, 30000, 6000, 8000, 2000, 3000, 1500, 8, 25, 170500, 216000),
        ("PRD-008", "Custom CNC Wall Panel - Reference Build", "custom", "Decor", "Wall Panels", "Sq Ft",
         None, None, None, "in", "HDHMR carved panel", "PU white",
         28000, 2000, 12000, 5000, 3000, 500, 1000, 500, 8, 25, 52000, 65000),
        # Billable services - Family 102's Product ID requirement means
        # even a freeform-feeling line like "Installation" needs a real
        # Product Master row to reference; these are exactly that,
        # priced per Woodful's typical labour/logistics cost, not tied
        # to a physical item. Unused cost components are 0, not None -
        # the cost-field conversion below has no None-guard.
        ("PRD-009", "Delivery & Installation Service", "standard", "Services", "Installation", "Nos",
         None, None, None, "in", None, None,
         0, 0, 6000, 0, 0, 800, 1000, 200, 8, 25, 8000, 10000),
        ("PRD-010", "Site Design Consultation", "standard", "Services", "Design", "Visit",
         None, None, None, "in", None, None,
         0, 0, 4000, 0, 0, 0, 500, 500, 8, 25, 5000, 6500),
        ("PRD-011", "Electrical/Site Coordination Service", "standard", "Services", "Coordination", "Nos",
         None, None, None, "in", None, None,
         0, 0, 3500, 0, 0, 0, 500, 500, 8, 25, 4500, 5800),
    ]
    out = {}
    for (code, name, ptype, cat, sub, unit, length, width, height, dim_unit, primary_mat, finish,
         mat_c, hw_c, lab_c, mach_c, fin_c, pack_c, trans_c, other_c, overhead, margin, cost, selling) in rows:
        p = Product(
            product_code=code, business_id=generate_business_id(db), name=name, product_type=ptype,
            category=cat, subcategory=sub, unit=unit,
            length=Decimal(str(length)) if length is not None else None,
            width=Decimal(str(width)) if width is not None else None,
            height=Decimal(str(height)) if height is not None else None,
            dimension_unit=dim_unit, primary_material=primary_mat, finish=finish,
            material_cost=Decimal(str(mat_c)), hardware_cost=Decimal(str(hw_c)), labour_cost=Decimal(str(lab_c)),
            machine_cost=Decimal(str(mach_c)), finish_cost=Decimal(str(fin_c)), packing_cost=Decimal(str(pack_c)),
            transport_cost=Decimal(str(trans_c)), other_cost=Decimal(str(other_c)),
            overhead_percent=Decimal(str(overhead)), margin_percent=Decimal(str(margin)),
            cost_price=Decimal(str(cost)), selling_price=Decimal(str(selling)),
            is_active=True,
        )
        db.add(p)
        out[code] = p
    db.commit()
    logger.info("Seeded %d products", len(rows))
    return out


def seed_product_materials(db, products, materials):
    """Bill-of-materials links - which real seeded Materials a Product
    actually consumes, tying the Product Master into the existing
    Material Stock Master (not just a flat cost estimate)."""
    if db.query(ProductMaterial).count() > 0:
        return
    rows = [
        # product_code, material_code, quantity_required, unit
        ("PRD-003", "MAT-002", 3, "Sheets"),   # Wardrobe - BWP Plywood
        ("PRD-003", "MAT-004", 2, "Sheets"),   # Wardrobe - White Laminate
        ("PRD-003", "MAT-006", 8, "Nos"),      # Wardrobe - Soft Close Hinges
        ("PRD-004", "MAT-003", 1, "Sheets"),   # TV Unit - MDF
        ("PRD-004", "MAT-005", 1, "Sheets"),   # TV Unit - Walnut Laminate
        ("PRD-006", "MAT-002", 6, "Sheets"),   # Custom Bedroom Suite - BWP Plywood
        ("PRD-006", "MAT-010", 4, "Litres"),   # Custom Bedroom Suite - PU White Paint
        ("PRD-007", "MAT-001", 5, "Sheets"),   # Custom Modular Kitchen - HDHMR
        ("PRD-007", "MAT-007", 6, "Sets"),     # Custom Modular Kitchen - Telescopic Channels
        ("PRD-008", "MAT-003", 2, "Sheets"),   # Custom CNC Wall Panel - MDF
    ]
    count = 0
    for prod_code, mat_code, qty, unit in rows:
        product = products.get(prod_code)
        material = materials.get(mat_code)
        if not product or not material:
            continue
        db.add(ProductMaterial(product_id=product.id, material_id=material.id,
                                quantity_required=Decimal(str(qty)), unit=unit))
        count += 1
    db.commit()
    logger.info("Seeded %d product-material BOM links", count)


def seed_estimate_line_items(db, estimates, products):
    """Real itemized breakdowns for the seeded estimates, linking to the
    Product Master where the line genuinely corresponds to a cataloged,
    custom, or billable-service product - Family 102's Product ID
    requirement means every line should resolve to a real Product Master
    row now, including services like Installation/Design Consultation."""
    if db.query(EstimateLineItem).count() > 0:
        return
    rows = [
        # estimate_code, description, category, qty, unit, rate, product_code (or None)
        ("EST-001", "Custom Bedroom Suite", "Furniture", 1, "Set", 219000, "PRD-006"),
        ("EST-001", "Delivery and installation", "Installation", 1, "Nos", 8000, "PRD-009"),
        ("EST-002", "Custom Modular Kitchen", "Furniture", 1, "Set", 170500, "PRD-007"),
        ("EST-002", "Site electrical coordination", "Service", 1, "Nos", 5000, "PRD-011"),
        ("EST-003", "Custom CNC Wall Panel", "Furniture", 1, "Sq Ft", 52000, "PRD-008"),
        ("EST-004", "Additional puja room shelf unit", "Furniture", 1, "Nos", 30000, None),
        ("EST-005", "Studio Compact TV Unit (declined)", "Furniture", 1, "Nos", 11700, "PRD-004"),
        ("EST-006", "Northline Dining Table (6-Seater)", "Furniture", 1, "Nos", 38000, "PRD-005"),
        ("EST-006", "Meridian Coffee Table", "Furniture", 1, "Nos", 12500, "PRD-002"),
        ("EST-007", "Meridian Coffee Table", "Furniture", 1, "Nos", 12500, "PRD-002"),
        ("EST-008", "Harbor 3-Seater Sofa", "Furniture", 1, "Nos", 48000, "PRD-001"),
    ]
    count = 0
    for est_code, desc, category, qty, unit, rate, prod_code in rows:
        estimate = estimates.get(est_code)
        if not estimate:
            continue
        product = products.get(prod_code) if prod_code else None
        qty_d = Decimal(str(qty))
        rate_d = Decimal(str(rate))
        db.add(EstimateLineItem(
            estimate_id=estimate.id, description=desc, category=category, quantity=qty_d, unit=unit,
            rate=rate_d, amount=(qty_d * rate_d), sort_order=count,
            product_id=product.id if product else None,
        ))
        count += 1
    db.commit()
    logger.info("Seeded %d estimate line items", count)


def seed_order_items(db, orders, products):
    """Real Order Items so an order identifies exactly what was ordered
    (Family 21's core requirement), linked to the Product Master where
    applicable."""
    if db.query(OrderItem).count() > 0:
        return
    rows = [
        # order_code, description, category, qty, unit, rate, product_code (or None)
        ("WC-2026-001", "Custom Bedroom Suite", "Furniture", 1, "Set", 219000, "PRD-006"),
        ("WC-2026-001", "Delivery and installation", "Installation", 1, "Nos", 8000, "PRD-009"),
        ("WC-2026-002", "Custom Modular Kitchen", "Furniture", 1, "Set", 170500, "PRD-007"),
        ("WC-2026-002", "Site electrical coordination", "Service", 1, "Nos", 5000, "PRD-011"),
        ("WC-2026-003", "Custom CNC Wall Panel", "Furniture", 1, "Sq Ft", 52000, "PRD-008"),
        ("WC-2026-004", "Custom Mandir Unit", "Furniture", 1, "Nos", 100000, None),
        ("WC-2026-004", "Additional carving detail", "Design", 1, "Nos", 15000, None),
        ("WC-2026-005", "Harbor 3-Seater Sofa (showroom display)", "Furniture", 2, "Nos", 32000, "PRD-001"),
        ("WC-2026-005", "Meridian Coffee Table (showroom display)", "Furniture", 2, "Nos", 8800, "PRD-002"),
        ("WC-2026-006", "Northline Dining Table (6-Seater)", "Furniture", 1, "Nos", 38000, "PRD-005"),
        ("WC-2026-006", "Meridian Coffee Table", "Furniture", 1, "Nos", 12500, "PRD-002"),
        ("WC-2026-007", "Meridian Coffee Table", "Furniture", 1, "Nos", 12500, "PRD-002"),
        ("WC-2026-008", "Everline 4-Door Wardrobe", "Furniture", 1, "Nos", 49000, "PRD-003"),
    ]
    count = 0
    for order_code, desc, category, qty, unit, rate, prod_code in rows:
        order = orders.get(order_code)
        if not order:
            continue
        product = products.get(prod_code) if prod_code else None
        qty_d = Decimal(str(qty))
        rate_d = Decimal(str(rate))
        db.add(OrderItem(
            order_id=order.id, description=desc, category=category, quantity=qty_d, unit=unit,
            rate=rate_d, amount=(qty_d * rate_d), sort_order=count,
            product_id=product.id if product else None,
        ))
        count += 1
    db.commit()
    logger.info("Seeded %d order items", count)


def seed_clients(db):
    if db.query(Client).count() > 0:
        return {c.client_code: c for c in db.query(Client).all()}
    rows = [
        ("CL-001", "Siddharth", "9312345654", "siddharth@example.com", "Indore", "Referral", "2026-07-10", "Bedroom furniture"),
        ("CL-002", "Khushaal", "9823456731", "khushaal@example.com", "Bicholi, Indore", "Architect", "2026-07-12", "Modular kitchen"),
        ("CL-003", "Anaya", "9823456732", "anaya@example.com", "Vijay Nagar", "Instagram", "2026-07-18", "CNC wall panel"),
        ("CL-004", "Nimisha", "9823456733", "nimisha@example.com", "Rau", "Existing Client", "2026-07-19", "Mandir"),
        ("CL-005", "Mayank", "9312345600", "mayank@example.com", "Woodful Creations", "Internal", "2026-07-20", "Showroom display"),
        # Full relationship-chain demo client (Client Master section 9):
        # Sanket -> Estimate -> Order -> Product -> Task -> Payment, with
        # an outstanding balance still pending.
        ("CL-006", "Sanket", "9734567841", "sanket@example.com", "Palasia, Indore", "Referral", "2026-08-01", "Dining set + coffee table"),
        # No-transactions demo client (Client Master section 14): a fresh
        # lead with no estimate/order/payment yet at all - exercises the
        # "no orders yet" empty state rather than a decorative zero KPI.
        ("CL-007", "Pratharv", "9734567842", "pratharv@example.com", "Rajwada, Indore", "Instagram", "2026-08-15", "Enquired about dining furniture, awaiting site visit"),
        # Client Recognition rule in action (the exact business rule from
        # the Client Recognition Business Rule doc): this is a
        # DIFFERENT Shrangi from CL-003 - same name, but a different
        # phone number, so per the rule (name AND phone must both
        # match to reuse a client) this must be a distinct client
        # record, not a merge. Full workflow: Estimate (coffee table,
        # April) -> Estimate (sofa, May) -> coffee table Estimate
        # approved & converted to Order (June) -> Order completed &
        # fully paid -> direct Order for a wardrobe (July, no source
        # estimate). The sofa estimate is left "sent" - approved but
        # not yet converted is a realistic, common state to demonstrate.
        ("CL-008", "Shrangi", "7009870098", "shrangi.new@example.com", "Palasia, Indore", "Referral", "2026-04-05", "Coffee table + sofa quotations, coffee table converted to order"),
        ("CL-009", "Ishu", "9845673001", "ishu@example.com", "Bicholi, Indore", "Referral", "2026-08-18", "New lead"),
        ("CL-010", "Ashu", "9845673002", "ashu@example.com", "Vijay Nagar", "Instagram", "2026-08-18", "New lead"),
        ("CL-011", "Ritu", "9845673003", "ritu@example.com", "Saket Nagar, Indore", "Referral", "2026-08-19", "New lead"),
        ("CL-012", "Kushal", "9845673004", "kushal@example.com", "Rau, Indore", "Instagram", "2026-08-19", "New lead"),
        ("CL-013", "Shruti", "9845673005", "shruti@example.com", "Palasia, Indore", "Referral", "2026-08-19", "New lead"),
    ]
    out = {}
    for code, name, phone, email, addr, source, contact_date, remarks in rows:
        c = Client(client_code=code, name=name, phone=phone, email=email, address=addr,
                   lead_source=source, first_contact_date=_d(contact_date), remarks=remarks,
                   business_id=generate_business_id(db))
        db.add(c)
        out[code] = c
    db.commit()
    logger.info("Seeded %d clients", len(rows))
    return out


def resolve_woodful_client_duplicates(db):
    """Consolidates any already-seeded demo Client row onto the
    permanent Woodful roster identity for its name, per the roster
    rule that a name on WOODFUL_CLIENTS is one canonical person with
    one canonical phone/address - overriding the old demo "Client
    Recognition" scenario where a same-name-different-phone row was
    treated as a distinct client.

    For every roster name that already has one or more Client rows:
      - the row already carrying the roster phone (if any) is
        canonical; otherwise the oldest row (lowest id) is promoted
        and its phone/address/city are corrected in place - so its
        existing client_code and every FK already pointed at it
        (Orders, Estimates, ...) survive untouched.
      - every other row sharing that name is a true duplicate: its
        Orders/Estimates/activities/documents/rate records are
        re-pointed to the canonical row's id, then the duplicate row
        itself is deleted. No transaction history is lost, only the
        duplicate person record.

    Must run before seed_woodful_clients, so that function's own
    name+phone lookup finds the now-corrected row instead of creating
    a second CLW-xxx record for the same person.

    Idempotent: once each roster name has exactly one Client row with
    the exact roster phone/address, there is nothing left to merge or
    correct on the next run."""
    from app.models.client_activity import ClientActivity
    from app.models.client_document import ClientDocument
    from app.models.client_product_rate import ClientProductRate

    fixed = 0
    merged = 0
    for name, phone, address in WOODFUL_CLIENTS:
        city = _city_from_address(address)
        matches = db.query(Client).filter(Client.name == name).order_by(Client.id.asc()).all()
        if not matches:
            continue  # no existing demo row under this name yet - seed_woodful_clients will create the CLW-xxx row

        canonical = next((c for c in matches if c.phone == phone), None) or matches[0]
        if canonical.phone != phone or canonical.address != address or canonical.city != city or canonical.status != "Active":
            canonical.phone = phone
            canonical.address = address
            canonical.city = city
            canonical.status = "Active"
            fixed += 1

        for dup in matches:
            if dup.id == canonical.id:
                continue
            db.query(Order).filter(Order.client_id == dup.id).update({"client_id": canonical.id})
            db.query(Estimate).filter(Estimate.client_id == dup.id).update({"client_id": canonical.id})
            db.query(ClientActivity).filter(ClientActivity.client_id == dup.id).update({"client_id": canonical.id})
            db.query(ClientDocument).filter(ClientDocument.client_id == dup.id).update({"client_id": canonical.id})
            db.query(ClientProductRate).filter(ClientProductRate.client_id == dup.id).update({"client_id": canonical.id})
            db.delete(dup)
            merged += 1
    db.commit()
    if fixed:
        logger.info("Corrected %d Woodful roster client(s) to canonical phone/address in place", fixed)
    if merged:
        logger.info("Merged %d duplicate Woodful roster client record(s), re-pointing their transactions", merged)


def seed_woodful_clients(db):
    """Upserts the permanent Woodful client roster (WOODFUL_CLIENTS).

    Run after resolve_woodful_client_duplicates, which has already
    corrected any pre-existing demo row for a roster name onto the
    exact roster phone/address in place. So by the time this runs, a
    name+phone lookup finds that corrected row for every name that had
    prior demo data (e.g. Sanket, Shrangi, ...) and this function only
    ever creates a brand-new CLW-xxx record for roster names that never
    had a demo row at all.

    Idempotent: re-running always converges to the same set of
    records with the same phone/address values, whether that's by
    finding an already-corrected demo row or an already-created
    CLW-xxx row."""
    created = 0
    updated = 0
    for i, (name, phone, address) in enumerate(WOODFUL_CLIENTS, start=1):
        city = _city_from_address(address)
        existing = db.query(Client).filter(Client.phone == phone, Client.name == name).first()
        if existing:
            if existing.address != address or existing.city != city:
                existing.address = address
                existing.city = city
                updated += 1
            continue
        code = f"CLW-{i:03d}"
        if db.query(Client).filter(Client.client_code == code).first():
            continue
        c = Client(client_code=code, name=name, phone=phone, address=address, city=city,
                   status="Active", business_id=generate_business_id(db))
        db.add(c)
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d Woodful roster clients", created)
    if updated:
        logger.info("Updated %d Woodful roster client(s) (address/city)", updated)


# Client-wide margin overrides for THIS bulk-data test only (per the
# test's own explicit instruction: "These are NOT permanent customer
# rules... Future Estimates for the same customer may use a different
# margin"). Each is a ClientProductRate row with product_id=None (a
# client-wide default, see app/models/client_product_rate.py), which
# app/utils/pricing_priority.py's resolve_selling_rate already treats
# as priority level 3 (customer-specific margin) - applied
# automatically wherever an Estimate for that client doesn't have a
# more specific override, never touching the global 30% default or
# any other client.
TEST_MARGIN_OVERRIDES = [
    # (client name, margin_percent)
    ("Meenal", 15), ("Siddharth", 15), ("Priya", 15),
    ("Shrangi", 10), ("Nimisha", 10),
    ("Mayank", 0), ("Madhuri", 0),
]


def seed_client_margin_overrides(db):
    """Must run after resolve_woodful_client_duplicates/
    seed_woodful_clients, so every named client already exists as
    exactly one canonical row. Idempotent: skips a client that already
    has a client-wide override row."""
    from app.models.client_product_rate import ClientProductRate
    from app.models.product import Product

    created = 0
    for name, margin in TEST_MARGIN_OVERRIDES:
        client = db.query(Client).filter(Client.name == name).first()
        if not client:
            logger.warning("Margin override skipped - no client named %r found", name)
            continue
        existing = db.query(ClientProductRate).filter(
            ClientProductRate.client_id == client.id, ClientProductRate.product_id.is_(None),
        ).first()
        if existing:
            continue
        db.add(ClientProductRate(
            client_id=client.id, product_id=None, margin_percent=Decimal(str(margin)),
            notes=f"Test-specific margin for this bulk-data run - not a permanent customer rule.",
            created_by="seed_script",
        ))
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d client-wide margin override(s)", created)


def seed_orders(db, clients):
    if db.query(Order).count() > 0:
        return {o.order_code: o for o in db.query(Order).all()}
    rows = [
        ("WC-2026-001", "CL-001", "Bedroom Furniture", "2026-07-20", "2026-08-20", 325000, 32500, 97500, "Cutting", 45, "High", "Ravi", "Indore", "Bedroom and wardrobe"),
        ("WC-2026-002", "CL-002", "Modular Kitchen", "2026-07-22", "2026-08-25", 216000, 21600, 64800, "Material Purchase", 30, "Urgent", "Devendra", "Bicholi, Indore", "Base and wall cabinets"),
        ("WC-2026-003", "CL-003", "CNC Wall Panel", "2026-07-25", "2026-08-10", 85000, 25000, 0, "Designing", 10, "Medium", "Devendra", "Vijay Nagar", "3D carved panel"),
        ("WC-2026-004", "CL-004", "Mandir", "2026-07-26", "2026-08-18", 125000, 25000, 0, "Approved", 20, "High", "Ravi", "Rau", "HDHMR mandir"),
        ("WC-2026-005", "CL-005", "Showroom Display", "2026-07-27", "2026-09-01", 180000, 0, 0, "Designing", 10, "Low", "Brajwal", "Woodful Creations", "Internal work"),
        # Sanket - full chain demo (Client Master section 9): dining set +
        # coffee table, partially paid, genuinely outstanding balance.
        ("WC-2026-006", "CL-006", "Dining Furniture", "2026-08-02", "2026-08-30", 50500, 20000, 0, "Cutting", 25, "Medium", "Pankaj", "Palasia, Indore", "Dining table + coffee table, from Sanket's approved estimate"),
        # Shrangi (CL-008, the new/different Shrangi) - coffee table
        # Estimate approved & converted to Order in June, fully paid and
        # marked Completed before her direct wardrobe order in July.
        ("WC-2026-007", "CL-008", "Coffee Table", "2026-06-10", "2026-06-25", 12500, 12500, 0, "Completed", 100, "Low", "Devendra", "Palasia, Indore", "Converted from Shrangi's approved coffee table estimate; fully paid"),
        # Direct order (no source estimate) - placed in July, after the
        # coffee table order above was completed and fully paid.
        ("WC-2026-008", "CL-008", "Wardrobe", "2026-07-15", "2026-08-10", 49000, 15000, 0, "Material Purchase", 15, "Medium", "Pankaj", "Palasia, Indore", "Direct order - no estimate, placed after coffee table completion"),
    ]
    out = {}
    for code, cl_code, ptype, odate, ddate, value, advance, other, status, progress, priority, sup, addr, remarks in rows:
        total_received = Decimal(str(advance)) + Decimal(str(other))
        o = Order(order_code=code, client_id=clients[cl_code].id, project_type=ptype,
                  order_date=_d(odate), delivery_date=_d(ddate), order_value=Decimal(str(value)),
                  advance=Decimal(str(advance)), other_received=Decimal(str(other)),
                  total_received=total_received, balance=Decimal(str(value)) - total_received,
                  project_status=status, progress_percent=progress, priority=priority,
                  supervisor=sup, site_address=addr, remarks=remarks,
                  business_id=generate_business_id(db))
        db.add(o)
        out[code] = o
    db.commit()
    logger.info("Seeded %d orders", len(rows))
    return out


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
        # code, client, order (None if not yet/never converted), status, material_cost, labor_cost, valid_until, remarks, estimate_date
        ("EST-001", "CL-001", "WC-2026-001", "approved", 200000, 80000, "2026-08-05", "Approved - became the bedroom furniture order", "2026-07-15"),
        ("EST-002", "CL-002", "WC-2026-002", "approved", 140000, 50000, "2026-08-05", "Approved - became the modular kitchen order", "2026-07-18"),
        ("EST-003", "CL-003", None, "sent", 55000, 20000, "2026-08-15", "Sent to client, awaiting decision on the CNC panel", "2026-07-20"),
        ("EST-004", "CL-004", None, "draft", 30000, 10000, "2026-08-20", "Draft for an additional puja room piece", "2026-07-22"),
        ("EST-005", "CL-001", None, "rejected", 45000, 15000, "2026-07-30", "Client declined a separate TV unit estimate", "2026-07-10"),
        ("EST-006", "CL-006", "WC-2026-006", "approved", 42000, 8500, "2026-08-10", "Approved - became Sanket's dining furniture order", "2026-07-28"),
        # Each Estimate is independent - no timeline/history feature, this
        # is simply the date this particular quotation was given. Coffee
        # Table estimate given in April, later approved and converted to
        # WC-2026-007 in June - status is "closed" (not "approved"),
        # matching exactly what the real conversion route sets atomically
        # alongside order_id (see orders.py's estimate-claim logic).
        ("EST-007", "CL-008", "WC-2026-007", "closed", 10500, 2000, "2026-05-01", "Coffee table quotation", "2026-04-10"),
        # A separate, independent Sofa estimate given May 15 - unrelated
        # to EST-007 beyond both belonging to the same client.
        ("EST-008", "CL-008", None, "sent", 40000, 8000, "2026-06-15", "Sofa quotation", "2026-05-15"),
    ]
    out = {}
    for code, cl_code, order_code, status, mat_cost, lab_cost, valid_until, remarks, estimate_date in rows:
        subtotal = Decimal(str(mat_cost)) + Decimal(str(lab_cost))
        tax_amount, total_cost = _compute_totals(subtotal, Decimal("0"), Decimal("18"))
        e = Estimate(
            estimate_code=code, client_id=clients[cl_code].id,
            order_id=orders[order_code].id if order_code else None,
            material_cost=Decimal(str(mat_cost)), labor_cost=Decimal(str(lab_cost)),
            discount=Decimal("0"), tax_percent=Decimal("18"), tax_amount=tax_amount, total_cost=total_cost,
            status=status, valid_until=_d(valid_until), remarks=remarks,
            business_id=generate_business_id(db),
            created_at=_d(estimate_date), updated_at=_d(estimate_date),
        )
        db.add(e)
        out[code] = e
    db.commit()
    logger.info("Seeded %d estimates", len(rows))
    return out


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
        ("WC-2026-006", "Advance", "UPI", 20000, "2026-08-02", "Pankaj", "Advance on dining furniture order"),
        ("WC-2026-007", "Advance", "UPI", 12500, "2026-06-10", "Devendra", "Full payment on coffee table order - paid in full at booking"),
        ("WC-2026-008", "Advance", "UPI", 15000, "2026-07-15", "Pankaj", "Advance on wardrobe - direct order after coffee table completion"),
    ]
    count = 0
    for order_code, ptype, mode, amount, pdate, received_by, remarks in rows:
        db.add(Payment(
            receipt_code=f"RCPT-{count + 1:03d}", order_id=orders[order_code].id,
            date=_d(pdate), payment_type=ptype, payment_mode=mode,
            amount=Decimal(str(amount)), received_by=received_by, remarks=remarks,
            business_id=generate_business_id(db),
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
                               amount=Decimal(str(amount)), approved_by="Nikhil",
                               business_id=generate_business_id(db)))
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
                         invoice_total=Decimal(str(total)), payment_status=status,
                         business_id=generate_business_id(db)))
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
        ("EMP-001", "Pankaj", "Assembly", "Senior Carpenter", "9845671001", "2026-04-01", 22000, "9845672001", "Senior carpenter",
         "ABCPK1234A", "100200300401", "State Bank of India", "112233440001", "New"),
        ("EMP-002", "Ravi", "Panel Saw", "Carpenter", "9845671002", "2026-04-10", 19000, "9845672002", "Carpenter",
         "ABCPR5678B", "100200300402", "Bank of Baroda", "112233440002", "Old"),
        ("EMP-003", "Devendra", "CNC", "CNC Operator", "9845671003", "2026-05-01", 20000, "9845672003", "Carpenter, CNC operator",
         "ABCPD9012C", "100200300403", "State Bank of India", "112233440003", "New"),
        ("EMP-004", "Shweta", "Design", "Interior Designer", "9845671004", "2026-04-05", 24000, "9845672004", "Interior designer",
         "ABCPS3456D", "100200300404", "HDFC Bank", "112233440004", "New"),
        ("EMP-005", "Shivani", "Design", "Interior Designer", "9845671005", "2026-05-20", 22000, "9845672005", "Interior designer",
         "ABCPS7890E", "100200300405", "ICICI Bank", "112233440005", "Old"),
        ("EMP-006", "Arpit", "Assembly", "Helper", "9845671006", "2026-06-01", 15000, "9845672006", "Helper",
         None, None, "State Bank of India", "112233440006", "New"),
        ("EMP-007", "Madan", "Edge Banding", "Helper", "9845671007", "2026-06-01", 14500, "9845672007", "Helper",
         None, None, None, None, None),
        ("EMP-008", "Chhoutu", "Installation", "Helper", "9845671008", "2026-06-15", 14000, "9845672008", "Helper",
         None, None, None, None, None),
    ]
    out = {}
    for code, name, dept, designation, phone, joined, salary, emergency, remarks, pan, uan, bank_name, acc_no, regime in rows:
        e = Employee(employee_code=code, name=name, department=dept, designation=designation, phone=phone,
                     joining_date=_d(joined), monthly_salary=Decimal(str(salary)),
                     status="Active", emergency_contact=emergency, remarks=remarks,
                     pan=pan, uan=uan, bank_name=bank_name, bank_account_number=acc_no, tax_regime=regime,
                     business_id=generate_business_id(db))
        db.add(e)
        out[code] = e
    db.commit()
    logger.info("Seeded %d employees", len(rows))
    return out


def apply_woodful_employee_roster(db, employees):
    """Applies the permanent employee roster's exact phone/address/role
    onto the already-seeded Employee rows they belong to - every name
    in WOODFUL_EMPLOYEES matches one of seed_employees' EMP-xxx rows
    1:1, so this reconciles those rows in place rather than creating
    new ones. designation is overwritten to exactly the given role
    (Designer / Carpenter / Helper), per the "keep these roles exactly"
    instruction. Address is stored in the Employee model's own
    `address` column, leaving remarks free for the genuine
    job-description text seed_employees already put there.

    Also migrates any row from an older run of this script, back
    when there was no address column and the address was stashed in
    remarks as "Address: <address>" - that stopgap value is cleared
    once the address has been copied into the real column (the
    original job-description remark it replaced can't be recovered).

    Idempotent: setting the same phone/designation/address on a
    re-run is a no-op (guarded by the equality checks below)."""
    by_name = {}
    for emp in employees.values():
        by_name.setdefault(emp.name, emp)
    updated = 0
    for name, phone, address, role in WOODFUL_EMPLOYEES:
        emp = by_name.get(name)
        if not emp:
            logger.warning("Woodful roster employee '%s' not found among seeded employees - skipping", name)
            continue
        changed = False
        if emp.phone != phone or emp.designation != role or emp.address != address:
            emp.phone = phone
            emp.designation = role
            emp.address = address
            changed = True
        legacy_remark = f"Address: {address}"
        if emp.remarks == legacy_remark:
            emp.remarks = None
            changed = True
        if changed:
            updated += 1
    db.commit()
    if updated:
        logger.info("Updated %d employee(s) with Woodful roster details", updated)


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
            business_id=generate_business_id(db),
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
            business_id=generate_business_id(db),
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
                           standard_hours=Decimal("8"), attendance_status=status, remarks=remarks,
                           business_id=generate_business_id(db)))
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
        # Sanket's order - completes the Client -> Estimate -> Order ->
        # Product -> Task -> Payment chain (Client Master section 9).
        ("TSK-019", "2026-08-03", "EMP-001", "WC-2026-006", "Cut dining table + coffee table panels", "Medium", "09:00", "15:00", "DOING", 35, None),
        ("TSK-020", "2026-07-18", "EMP-001", "WC-2026-008", "Cut wardrobe panels", "Medium", "09:00", "16:00", "DOING", 20, None),
    ]
    out = {}
    for code, tdate, emp_code, order_code, desc, priority, start, end, status, completion, delay in rows:
        t = DailyTask(task_code=code, date=_d(tdate), employee_id=employees[emp_code].id,
                       order_id=orders[order_code].id, task_description=desc, priority=priority,
                       planned_start=_t(start), planned_end=_t(end), status=status,
                       completion_percent=completion, checked_by="Nikhil", delay_reason=delay,
                       created_by="nikhil@woodfulcreations.com", business_id=generate_business_id(db))
        db.add(t)
        out[code] = t
    db.commit()

    # Handoff chain - Measure -> Drawing -> Cutting, same order, each
    # linked to the one before it via previous_task_id.
    measure = DailyTask(
        task_code="TSK-013", date=_d("2026-07-20"), employee_id=employees["EMP-005"].id,
        order_id=orders["WC-2026-001"].id, task_description="Measure wardrobe opening",
        priority="High", status="DONE", completion_percent=100, created_by="nikhil@woodfulcreations.com",
        business_id=generate_business_id(db),
    )
    db.add(measure)
    db.commit()
    drawing = DailyTask(
        task_code="TSK-014", date=_d("2026-07-21"), employee_id=employees["EMP-004"].id,
        order_id=orders["WC-2026-001"].id, task_description="Prepare cutting drawing",
        priority="High", status="DONE", completion_percent=100, created_by="nikhil@woodfulcreations.com",
        previous_task_id=measure.id, business_id=generate_business_id(db),
    )
    db.add(drawing)
    db.commit()
    cutting = DailyTask(
        task_code="TSK-015", date=_d("2026-07-22"), employee_id=employees["EMP-001"].id,
        order_id=orders["WC-2026-001"].id, task_description="Cut plywood for wardrobe",
        priority="High", status="DOING", completion_percent=40, created_by="nikhil@woodfulcreations.com",
        previous_task_id=drawing.id, business_id=generate_business_id(db),
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
        business_id=generate_business_id(db),
    )
    db.add(parent)
    db.commit()
    sub1 = DailyTask(
        task_code="TSK-017", date=_d("2026-07-26"), employee_id=employees["EMP-002"].id,
        order_id=orders["WC-2026-001"].id, task_description="Assembly", priority="Medium",
        status="TO DO", completion_percent=0, created_by="nikhil@woodfulcreations.com",
        parent_task_id=parent.id, business_id=generate_business_id(db),
    )
    sub2 = DailyTask(
        task_code="TSK-018", date=_d("2026-07-27"), employee_id=employees["EMP-005"].id,
        order_id=orders["WC-2026-001"].id, task_description="Installation", priority="Medium",
        status="TO DO", completion_percent=0, created_by="nikhil@woodfulcreations.com",
        parent_task_id=parent.id, business_id=generate_business_id(db),
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
                              start_time=_t(start), end_time=_t(end), status=status,
                              business_id=generate_business_id(db)))
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


if __name__ == "__main__":
    # NOTE: this used to call Base.metadata.create_all(bind=engine) here.
    # That is what caused "table X already exists" failures inside Alembic
    # migrations (e.g. migration 0030): create_all() would silently create
    # every table the current models define, with no record of that in
    # alembic_version, so the NEXT time the backend started up and Alembic
    # tried to run migrations from scratch it collided with tables that
    # already existed. Alembic (via run_startup_migrations() at backend
    # startup) is now the ONLY thing responsible for creating/upgrading
    # schema. This script only seeds data and assumes the schema already
    # exists - run the backend at least once (or `alembic upgrade head`)
    # before running this script.
    pass
    db = SessionLocal()
    try:
        seed_master_users(db)
        locations = seed_locations(db)
        subcategories = seed_material_hierarchy(db)
        seed_lookups(db)
        suppliers = seed_suppliers(db)
        named_suppliers = seed_named_suppliers(db)
        seed_woodful_suppliers(db)
        materials = seed_materials(db, suppliers, locations, subcategories)
        seed_supplier_materials(db, suppliers, named_suppliers, materials)
        products = seed_products(db)
        seed_product_materials(db, products, materials)
        clients = seed_clients(db)
        orders = seed_orders(db, clients)
        estimates = seed_estimates(db, clients, orders)
        seed_estimate_line_items(db, estimates, products)
        seed_order_items(db, orders, products)
        seed_payments(db, orders)
        seed_project_expenses(db, orders)
        # Runs only after every Order/Estimate is seeded, so re-pointing a
        # duplicate client's transactions onto its canonical record has
        # real rows to act on; must run before seed_woodful_clients so that
        # function's name+phone lookup finds the now-corrected row instead
        # of creating a second (CLW-xxx) record for the same person.
        resolve_woodful_client_duplicates(db)
        seed_woodful_clients(db)
        seed_client_margin_overrides(db)
        seed_purchases(db, suppliers, materials)
        seed_issues(db, orders, materials)
        employees = seed_employees(db)
        apply_woodful_employee_roster(db, employees)
        seed_salary_slips(db, employees)
        seed_leaves(db, employees)
        seed_attendance(db, employees)
        tasks = seed_daily_tasks(db, employees, orders)
        seed_task_comments(db, tasks)
        seed_production_jobs(db, employees, orders, materials)
        seed_company_holidays(db)
        seed_notifications(db, materials, orders, employees, tasks)

        from app.models.user import User
        master_count = db.query(User).filter(User.role == "master", User.is_active == True).count()  # noqa: E712
        if master_count == 0:
            print(
                "\n" + "!" * 78 + "\n"
                "!!  SEED FINISHED, BUT THERE IS NO ACTIVE MASTER ACCOUNT IN THIS DATABASE.\n"
                "!!  You will NOT be able to sign in. Re-run with SEED_MASTER_PASSWORD set\n"
                "!!  (see the warning above) to create nikhil@woodful.local / garima@woodful.local.\n"
                + "!" * 78 + "\n"
            )
            logger.warning("Seed run completed with zero active master users - sign-in is impossible until this is fixed.")
        else:
            logger.info("Confirmed %d active master account(s) exist.", master_count)
        logger.info("Seed complete.")
    finally:
        db.close()
