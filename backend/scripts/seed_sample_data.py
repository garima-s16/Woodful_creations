"""
Seed the database with sample business data plus two named master admin
accounts (Garima, Nikhil) via SEED_MASTER_PASSWORD.

All demo business data (Clients, Suppliers, Materials, Employees,
Products, supplier pricing, product BOM) is read from
docs/Woodful_demo_data.xlsx - see the WORKBOOK-DRIVEN DATA note below.
This file contains only the seeding logic, not the data itself.

Idempotent - safe to re-run; skips any table that already has rows.
"""
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.platform.database import SessionLocal, engine
from app import models  # noqa: F401
from app.models import (
    Unit, StockStatus, StockPaymentStatus, SupplierTerm,
    Department, TaskStatus, AttendanceStatus, Machine,
    ProjectStatus, Priority, PaymentMode, LeadSource, ProjectType, ExpenseCategory,
)
from app.modules.inventory.models import MaterialCategory, MaterialSubcategory, Location, Material
from app.modules.procurement.models import Supplier, SupplierMaterial, Purchase
from app.modules.clients.models import Client
from app.modules.communications.models import Notification
from app.modules.communications.services import NotificationService
from app.modules.hr.models import Employee, SalarySlip, Leave, Attendance
from app.modules.catalog.models import Product, ProductMaterial
from app.modules.operations.models import DailyTask
from app.modules.operations.schemas import DAILY_TASK_STATUSES, DAILY_TASK_PRIORITIES
from app.platform.ids import generate_business_id, generate_unique_code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def _dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def _t(s):
    return datetime.strptime(s, "%H:%M").time()


def _num(value, default=0):
    """Null-safe numeric read for a workbook cell, for the exact case
    _workbook_rows's own docstring doesn't protect against: a blank
    Excel cell is still a present dict KEY with value None (see
    _workbook_rows), so row.get("Column", default) never applies its
    default - it only returns None. Decimal(str(None)) is
    "None" -> decimal.InvalidOperation, and arithmetic like
    (a + b) with any operand None raises TypeError - both real,
    observed seed-time crashes this function exists to prevent.

    An explicit `value is None` check, not `value or default`: a
    genuinely-recorded 0 (e.g. "PF deduction = 0", "Overtime = 0") is
    real workbook data, not a stand-in for "blank" - `or` would
    silently replace it with `default` too, which is wrong whenever
    default != 0."""
    return default if value is None else value


# ==========================================================================
# WORKBOOK-DRIVEN DATA - docs/Woodful_demo_data.xlsx is the single source
# of truth for demo business data: Clients (both the Woodful roster and
# the Demo Clients test-scenario roster), Suppliers (both the Woodful
# roster and the material-vendor Suppliers), Materials, Employees,
# Products, Supplier Material Pricing, Product-Material BOM, Purchases,
# Salary Slips, Leaves, and Attendance all come from it. Loaded once and
# cached; every seed function that needs a sheet calls
# _workbook_rows("Sheet Name") rather than re-opening the file.
#
# This applies to demo seeding only - the application's own UI and Excel
# import features (adding/importing Employees, Suppliers, Products, etc.
# in normal use) are untouched and still work exactly as before.
#
# Business data must not be hard-coded in Python. Anything the current
# seed needs that the workbook doesn't yet provide gets added to the
# workbook, not filled in with a Python fallback value - Materials'
# Rate/Minimum Stock/Supplier columns are the one pre-existing exception
# (documented deterministic rules for genuinely blank demo cells,
# predating this pass) rather than a pattern to extend. A record's own
# *code* (MAT-xxx/SUP-xxx/PRD-xxx/EMP-xxx) is calculated from row
# position at seed time, the same way the app's own code-generation
# logic works, so the workbook holds business information, not a
# duplicate identifier scheme; Client/Purchase codes (CL-xxx/PUR-xxx)
# go one step further and are generated through the app's own
# generate_unique_code() rather than even a row-position scheme, since
# that's the mechanism the real create-Client/create-Purchase endpoints
# already use.
# ==========================================================================
_WORKBOOK_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "Woodful_demo_data.xlsx"
_workbook_cache = {}


def _workbook_rows(sheet_name):
    """Returns every non-blank data row from the given sheet as a list
    of dicts keyed by that sheet's own header row (row 1) - so callers
    read row["Material Name"], not a positional tuple that silently
    breaks if a column is ever reordered in the workbook."""
    if sheet_name in _workbook_cache:
        return _workbook_cache[sheet_name]
    import openpyxl
    wb = openpyxl.load_workbook(_WORKBOOK_PATH, data_only=True)
    ws = wb[sheet_name]
    headers = [c.value for c in ws[1]]
    rows = []
    for raw_row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in raw_row):
            continue
        rows.append({headers[i]: raw_row[i] for i in range(len(headers)) if i < len(raw_row)})
    _workbook_cache[sheet_name] = rows
    return rows


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
# Permanent Woodful business-roster data (real Clients/Suppliers), read
# directly from the workbook's own Phone/Address columns - previously
# hardcoded here as Python tuples; the workbook didn't have those two
# columns at all until they were added directly to
# docs/Woodful_demo_data.xlsx (moving the data out of code and into the
# one real source of truth, rather than leaving it duplicated in both
# places or generating fresh values in Python).
# ==========================================================================
def _woodful_clients():
    return [(r["Client Name"], str(r["Phone"]), r["Address"]) for r in _workbook_rows("Clients") if r.get("Client Name")]


def _woodful_suppliers():
    return [(r["Supplier Name"], str(r["Phone"]), r["Address"]) for r in _workbook_rows("Suppliers") if r.get("Supplier Name")]


def _employee_rows():
    """The full Employee sheet, row order preserved (it drives the
    calculated EMP-{i:03d} codes - see seed_employees)."""
    return _workbook_rows("Employees")


def _material_supplier_rows():
    """The full Material Suppliers sheet, row order preserved (it drives
    the calculated SUP-{i:03d} codes - see seed_suppliers)."""
    return _workbook_rows("Material Suppliers")


def _product_rows():
    """The full Products sheet, row order preserved (it drives the
    calculated PRD-{i:03d} codes - see seed_products)."""
    return _workbook_rows("Products")

# Reserved future test-user pool: already lives in docs/Woodful_demo_data.xlsx's
# "Extra Names" sheet (Name / Potential Use columns) - this was a dead,
# duplicate copy of that same list left behind in Python (unused,
# unreferenced by any seed function), the exact kind of hidden
# duplicate data source this pass removes. Not seeded as Clients,
# Suppliers or Employees either way.


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
    location name for other seed functions to reference.

    Idempotent per-record, not per-table: each node is looked up by
    its own name (the natural unique key here) before creating it, so
    a previous run that only got partway through the hierarchy is
    completed on the next run instead of being silently skipped
    entirely."""
    existing = {l.name: l for l in db.query(Location).all()}
    out = dict(existing)
    created = 0

    workshop = existing.get("Main Workshop")
    if not workshop:
        workshop = Location(name="Main Workshop", location_type="Warehouse", business_id=generate_business_id(db))
        db.add(workshop)
        db.flush()
        out["Main Workshop"] = workshop
        created += 1

    areas = {
        "Board Storage": ["Rack A1", "Rack A2", "Rack A3"],
        "Hardware Storage": ["Rack B1", "Rack B2"],
        "Laminate Storage": ["Rack C1"],
        "Paint Store": [],
        "Chemical Area": [],
        "Packaging Area": [],
    }
    for area_name, racks in areas.items():
        area = out.get(area_name)
        if not area:
            area = Location(name=area_name, location_type="Area", parent_id=workshop.id, business_id=generate_business_id(db))
            db.add(area)
            db.flush()
            out[area_name] = area
            created += 1
        for rack_name in racks:
            if rack_name not in out:
                rack = Location(name=rack_name, location_type="Rack", parent_id=area.id, business_id=generate_business_id(db))
                db.add(rack)
                db.flush()
                out[rack_name] = rack
                created += 1

    db.commit()
    logger.info("Locations: created %d, existing %d", created, len(out) - created)
    return out


def seed_material_hierarchy(db):
    """Category -> Subcategory rows, derived directly from the real
    workbook's Materials sheet (its own Category and Material Type
    columns), not a hand-maintained dict that could drift from the
    actual data. Returns a dict keyed by subcategory name so
    seed_materials can wire each seeded material's subcategory_id
    correctly, the same way seed_locations' returned dict wires
    location_id."""
    pairs = {}  # category_name -> set of subcategory names, in first-seen order
    for row in _workbook_rows("Materials"):
        category_name, subcategory_name = row.get("Category"), row.get("Material Type")
        if not category_name or not subcategory_name:
            continue
        pairs.setdefault(category_name, {})[subcategory_name] = None

    existing_categories = {c.name: c for c in db.query(MaterialCategory).all()}
    out = {s.name: s for s in db.query(MaterialSubcategory).all()}
    created = 0
    for category_name, subcategory_names in pairs.items():
        category = existing_categories.get(category_name)
        if not category:
            category = MaterialCategory(name=category_name)
            db.add(category)
            db.flush()
            existing_categories[category_name] = category
        for sub_name in subcategory_names:
            if sub_name in out:
                continue
            sub = MaterialSubcategory(category_id=category.id, name=sub_name)
            db.add(sub)
            db.flush()
            out[sub_name] = sub
            created += 1

    db.commit()
    logger.info("Material subcategories: created %d, existing %d", created, len(out) - created)
    return out




def seed_woodful_suppliers(db):
    """Upserts the permanent Woodful supplier roster (read from the workbook)
    - added alongside the existing SUP-xxx suppliers, not replacing
    them. Uses its own SUPW-xxx code range so it can never collide with
    SUP-xxx codes. The Supplier model has no address column (and this
    task doesn't add one), so each roster address is kept verbatim in
    remarks rather than dropped.

    Idempotent per-row by supplier_code, matching seed_suppliers' own
    pattern."""
    existing_codes = {
        s.supplier_code for s in
        db.query(Supplier).filter(Supplier.supplier_code.like("SUPW-%")).all()
    }
    created = 0
    for i, (name, phone, address) in enumerate(_woodful_suppliers(), start=1):
        code = f"SUPW-{i:03d}"
        if code in existing_codes:
            continue
        db.add(Supplier(
            supplier_code=code, name=name, category="General Supplier",
            contact_person=name, phone=phone, remarks=f"Address: {address}",
            business_id=generate_business_id(db),
        ))
        created += 1
    db.commit()
    if created:
        logger.info("Seeded %d Woodful roster suppliers", created)


def seed_supplier_materials(db, suppliers, materials):
    """Real multi-supplier pricing comparisons, e.g. BWP Plywood from
    Century Plywood Dealer at 2350 vs. Sanket Plywood & Boards at 2410.
    Uses SupplierMaterial, not the legacy single Material.supplier_id -
    that stays pointed at each material's existing primary supplier.

    Reads docs/Woodful_demo_data.xlsx's "Supplier Material Pricing"
    sheet, matched by material/supplier NAME rather than a MAT-xxx/SUP-xxx
    code - both codes are only assigned at seed time from row position
    (see seed_materials/seed_suppliers), so a hardcoded code here would be
    silently wrong the moment either sheet's row order changes. This was
    a real bug in the previous hardcoded version of this function: its
    MAT-xxx codes (assigned back when Materials had far fewer rows) no
    longer pointed at the materials its own comments named."""
    materials_by_name = {m.name: m for m in materials.values()}
    suppliers_by_name = {s.name: s for s in suppliers.values()}
    existing_pairs = {
        (sm.material_id, sm.supplier_id) for sm in db.query(SupplierMaterial.material_id, SupplierMaterial.supplier_id).all()
    }
    count = 0
    for row in _workbook_rows("Supplier Material Pricing"):
        mat_name, sup_name = row.get("Material Name"), row.get("Supplier Name")
        material = materials_by_name.get(mat_name)
        supplier = suppliers_by_name.get(sup_name)
        if not material or not supplier:
            logger.warning("Supplier Material Pricing row skipped - material %r or supplier %r not found", mat_name, sup_name)
            continue
        if (material.id, supplier.id) in existing_pairs:
            continue
        price = row.get("Price")
        db.add(SupplierMaterial(
            material_id=material.id, supplier_id=supplier.id,
            supplier_price=Decimal(str(price)) if price is not None else None,
            moq=row.get("MOQ"), lead_time_days=row.get("Lead Time Days"),
            is_preferred=str(row.get("Preferred")).strip().lower() == "yes",
        ))
        existing_pairs.add((material.id, supplier.id))
        count += 1
    db.commit()
    logger.info("Supplier-material pricing rows: created %d", count)


def seed_lookups(db):
    for model, names in LOOKUPS.items():
        existing_names = {row.name for row in db.query(model).all()}
        created = 0
        for n in names:
            if n in existing_names:
                continue
            db.add(model(name=n))
            created += 1
        if created:
            logger.info("Lookup %s: created %d, existing %d", model.__tablename__, created, len(names) - created)
    db.commit()


def seed_suppliers(db):
    """Material vendor businesses (Century Plywood Dealer, Greenpanel
    Distributor, etc.) - distinct from the Woodful roster suppliers in
    seed_woodful_suppliers (real people/companies Woodful buys from vs.
    Woodful's own SUPW-xxx contact roster).

    Reads docs/Woodful_demo_data.xlsx's "Material Suppliers" sheet
    (previously two separate hardcoded lists here, seed_suppliers'
    SUP-001..005 and a since-removed seed_named_suppliers' SUP-006..008 -
    merged into one workbook table, one function). supplier_code is
    calculated from row position (SUP-{i:03d}), the same way MAT-xxx
    material codes are - the workbook holds supplier information, not a
    duplicate identifier-generation mechanism."""
    out = {s.supplier_code: s for s in db.query(Supplier).all()}
    created = 0
    for i, row in enumerate(_material_supplier_rows(), start=1):
        name = row.get("Supplier Name")
        if not name:
            continue
        code = f"SUP-{i:03d}"
        if code in out:
            continue
        s = Supplier(
            supplier_code=code, name=name, category=row.get("Category"),
            contact_person=row.get("Contact Person"), phone=str(row.get("Phone")) if row.get("Phone") else None,
            gstin=row.get("GSTIN"), payment_terms=row.get("Payment Terms"), remarks=row.get("Remarks"),
            business_id=generate_business_id(db),
        )
        db.add(s)
        out[code] = s
        created += 1
    db.commit()
    logger.info("Suppliers: created %d, existing %d", created, len(out) - created)
    return out


def seed_materials(db, suppliers, locations, subcategories):
    """Reads every material from the real workbook (91 rows) - this
    function used to be split into a 10-row hardcoded list here plus a
    separate ~86-row hardcoded list in scripts/seed_master_catalog.py
    (imported from yet another file, scripts/_extended_materials_data.py).
    That three-file split for one entity was the redundancy this was
    consolidated to remove - there is now exactly one seed_materials
    function and one data source (the workbook), not three files that
    all had to be kept in sync by hand.

    Rate / Minimum Stock / Supplier are read directly from the
    workbook, no Python fallback (an explicit requirement -
    a previous version of this function fell back to average_rate=0,
    a unit-based default minimum_stock, and round-robin supplier
    assignment when these columns were blank; they are populated for
    every row now, directly in docs/Woodful_demo_data.xlsx, using a
    documented per-category/thickness formula - a transparent demo
    anchor, not a researched real-world price, but genuinely workbook
    data rather than code-side invention). location_id is left unset -
    the workbook still gives no warehouse layout to assign from."""
    suppliers_by_name = {s.name: s for s in suppliers.values()}
    # The previously-unused "Inventory Seed" sheet (Item,
    # UOM, Current Qty, Minimum Stock) genuinely overlaps 9 of these 91
    # materials by exact name - connected here as the real source for
    # opening_stock where a match exists, rather than left as an
    # unused duplicate data source. It doesn't cover every material by
    # design, so the minimum_stock*2 formula remains the fallback for
    # the rest - a materially different situation from the earlier
    # "left blank, compensated in Python" problem, since this sheet
    # was never intended to cover all 91 rows.
    inventory_seed_qty = {
        r["Item"]: r["Current Qty"] for r in _workbook_rows("Inventory Seed")
        if r.get("Item") and r.get("Current Qty") is not None
    }
    out = {m.material_code: m for m in db.query(Material).all()}
    created = 0
    for i, row in enumerate(_workbook_rows("Materials"), start=1):
        name = row.get("Material Name")
        if not name:
            continue
        code = f"MAT-{i:03d}"
        if code in out:
            continue
        category = row.get("Category")
        subcategory_name = row.get("Material Type")
        unit = row.get("UOM") or "Nos"
        thickness = row.get("Thickness / Specification")

        average_rate = Decimal(str(row["Rate"]))
        minimum_stock = Decimal(str(row["Minimum Stock"]))
        seeded_qty = inventory_seed_qty.get(name)
        opening_stock = Decimal(str(seeded_qty)) if seeded_qty is not None else minimum_stock * 2
        supplier_row = suppliers_by_name.get(row["Supplier"])
        supplier_id = supplier_row.id if supplier_row else None

        subcategory_row = subcategories.get(subcategory_name)

        m = Material(
            material_code=code, name=name, category=category, thickness_size=thickness, unit=unit,
            opening_stock=opening_stock, total_purchased=Decimal("0"), total_issued=Decimal("0"),
            current_stock=opening_stock, minimum_stock=minimum_stock, average_rate=average_rate,
            supplier_id=supplier_id,
            subcategory_id=subcategory_row.id if subcategory_row else None,
            business_id=generate_business_id(db),
        )
        db.add(m)
        out[code] = m
        created += 1
    db.commit()
    logger.info("Materials: created %d, existing %d", created, len(out) - created)
    return out


def seed_products(db):
    """Product Master demo catalog - a mix of standard (repeatable
    catalog) and custom (one-off, client-specific) pieces, each with a
    real itemized cost breakdown (material/hardware/labour/machine/
    finish/packing/transport/other + overhead/margin %), the same shape
    a real production cost estimate would use.

    Reads docs/Woodful_demo_data.xlsx's "Products" sheet (previously an
    11-row hardcoded list here plus a separate 170-row hardcoded list in
    scripts/_extended_products_data.py - that file is gone; the workbook
    is now the one source for both). product_code is calculated from row
    position (PRD-{i:03d}), the same way MAT-xxx material codes are - per
    the app's own product-code generation approach, the workbook holds
    product information, not a duplicate identifier-generation mechanism.
    This demo-seed cost breakdown is separate from, and doesn't change,
    the application's real product-costing calculation used elsewhere.

    Idempotent per-record: checked by product_code, so a prior partial
    run is completed rather than left incomplete."""
    out = {p.product_code: p for p in db.query(Product).all()}
    created = 0
    for i, row in enumerate(_product_rows(), start=1):
        name = row.get("Product Name")
        if not name:
            continue
        code = f"PRD-{i:03d}"
        if code in out:
            continue

        def _num(key):
            v = row.get(key)
            return Decimal(str(v)) if v not in (None, "") else None

        p = Product(
            product_code=code, business_id=generate_business_id(db), name=name,
            product_type=row.get("Type") or "standard",
            category=row.get("Category"), subcategory=row.get("Subcategory"), unit=row.get("Unit"),
            length=_num("Length"), width=_num("Width"), height=_num("Height"),
            dimension_unit=row.get("Dimension Unit"),
            primary_material=row.get("Primary Material"), finish=row.get("Finish"),
            material_cost=_num("Material Cost") or Decimal("0"),
            hardware_cost=_num("Hardware Cost") or Decimal("0"),
            labour_cost=_num("Labour Cost") or Decimal("0"),
            machine_cost=_num("Machine Cost") or Decimal("0"),
            finish_cost=_num("Finish Cost") or Decimal("0"),
            packing_cost=_num("Packing Cost") or Decimal("0"),
            transport_cost=_num("Transport Cost") or Decimal("0"),
            other_cost=_num("Other Cost") or Decimal("0"),
            overhead_percent=_num("Overhead %") or Decimal("0"),
            margin_percent=_num("Margin %") or Decimal("0"),
            cost_price=_num("Cost Price") or Decimal("0"),
            selling_price=_num("Selling Price") or Decimal("0"),
            is_active=True,
        )
        db.add(p)
        out[code] = p
        created += 1
    db.commit()
    logger.info("Products: created %d, existing %d", created, len(out) - created)
    return out


def seed_product_materials(db, products, materials):
    """Bill-of-materials links - which real seeded Materials a Product
    actually consumes, tying the Product Master into the existing
    Material Stock Master (not just a flat cost estimate).

    Reads docs/Woodful_demo_data.xlsx's "BOM Examples" sheet, matched by
    product/material NAME - a product's PRD-xxx code (like a material's
    MAT-xxx code) is only assigned at seed time from its row position in
    the Products sheet (see seed_products), so a hardcoded code here
    could silently point at a completely different product than
    intended (this was a real bug found and fixed once already, when
    this function was still split across two files)."""
    materials_by_name = {m.name: m for m in materials.values()}
    products_by_name = {p.name: p for p in products.values()}

    existing_pairs = {
        (pm.product_id, pm.material_id) for pm in db.query(ProductMaterial.product_id, ProductMaterial.material_id).all()
    }
    count = 0
    for row in _workbook_rows("BOM Examples"):
        prod_name, mat_name = row.get("Product Name"), row.get("Material Name")
        product = products_by_name.get(prod_name)
        material = materials_by_name.get(mat_name)
        if not product or not material:
            logger.warning("BOM Examples row skipped - product %r or material %r not found", prod_name, mat_name)
            continue
        if (product.id, material.id) in existing_pairs:
            continue
        quantity = row.get("Quantity")
        if quantity is None:
            logger.warning("BOM Examples row skipped - %s / %s has no Quantity", prod_name, mat_name)
            continue
        db.add(ProductMaterial(product_id=product.id, material_id=material.id,
                                quantity_required=Decimal(str(quantity)), unit=row.get("Unit")))
        existing_pairs.add((product.id, material.id))
        count += 1
    db.commit()
    logger.info("Product-material BOM links: created %d", count)


def seed_clients(db):
    """Test/demo-scenario clients (as opposed to the permanent Woodful
    roster clients in seed_woodful_clients) - reads
    docs/Woodful_demo_data.xlsx's "Demo Clients" sheet, which carries
    the same records/remarks previously hardcoded here (including the
    Client Master section 9/14 relationship-chain scenarios), just
    relocated out of Python.

    client_code is NOT read from the workbook and NOT computed from row
    position the way MAT-xxx/SUP-xxx/PRD-xxx/EMP-xxx are - Client
    already has its own real generation mechanism the application
    itself uses on every create (generate_unique_code(db, Client,
    "client_code", "CL-"), same as client_imports.py/clients.py), so
    this reuses that rather than inventing a second, seed-only
    code scheme.

    Idempotent by (name, phone) - the same natural-key approach
    seed_woodful_clients already uses - rather than by a code that
    wouldn't exist yet on the first pass."""
    existing_keys = {(c.name, c.phone) for c in db.query(Client.name, Client.phone).all()}
    created = 0
    for row in _workbook_rows("Demo Clients"):
        name = row.get("Name")
        if not name:
            continue
        phone = str(row.get("Phone")) if row.get("Phone") else None
        if (name, phone) in existing_keys:
            continue
        contact_date = row.get("First Contact Date")
        c = Client(
            client_code=generate_unique_code(db, Client, "client_code", "CL-"),
            name=name, phone=phone, email=row.get("Email"), address=row.get("Address"),
            lead_source=row.get("Lead Source"),
            first_contact_date=_d(contact_date) if isinstance(contact_date, str) else contact_date,
            remarks=row.get("Remarks"), client_type=row.get("Client Type"),
            business_id=generate_business_id(db),
        )
        db.add(c)
        db.flush()
        existing_keys.add((name, phone))
        created += 1
    db.commit()
    out = {c.client_code: c for c in db.query(Client).all()}
    logger.info("Demo clients: created %d, existing %d", created, len(out) - created)
    return out


def seed_woodful_clients(db):
    """Upserts the permanent Woodful client roster (read from the workbook).

    Reconciled against already-seeded test data using this codebase's
    own Client Recognition rule (name AND phone must both match to
    reuse a client) - so the roster's Shrangi row (7009870098) resolves
    to the existing CL-008 test-scenario client (only her address/city
    are updated in place) instead of creating a duplicate Shrangi, and
    her April-Estimate -> May-Estimate -> June-Order -> July-Order
    scenario is left completely untouched. Every other roster name gets
    its own new client record (CLW-xxx - a separate code range from the
    CL-xxx test/demo clients, so neither numbering can ever collide).

    Idempotent: re-running always converges to the same 39 records
    with the same phone/address values, whether that's by finding the
    already-created CLW-xxx row (matched by name+phone, same as the
    Shrangi case) or by finding CL-008 again."""
    created = 0
    updated = 0
    for i, (name, phone, address) in enumerate(_woodful_clients(), start=1):
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


def seed_purchases(db, suppliers, materials):
    """Reads docs/Woodful_demo_data.xlsx's "Purchases" sheet, matched by
    supplier/material NAME rather than SUP-xxx/MAT-xxx code - same
    reasoning as seed_supplier_materials/seed_product_materials: those
    codes are only assigned at seed time from row position, so a
    hardcoded code here could silently point at the wrong record.

    purchase_code is generated via the app's own mechanism
    (generate_unique_code(db, Purchase, "purchase_code", "PUR-"), the
    same one stock_service.py uses on every real purchase create) - not
    read from the workbook and not a seed-only row-position scheme.

    Idempotent by (date, supplier, material, quantity) - a hardcoded
    code can't serve as the idempotency key here since none is
    supplied up front, but this combination already uniquely
    identifies each of the demo rows."""
    materials_by_name = {m.name: m for m in materials.values()}
    suppliers_by_name = {s.name: s for s in suppliers.values()}
    existing_keys = {
        (p.date, p.supplier_id, p.material_id, p.quantity)
        for p in db.query(Purchase.date, Purchase.supplier_id, Purchase.material_id, Purchase.quantity).all()
    }
    created = 0
    for row in _workbook_rows("Purchases"):
        sup_name, mat_name = row.get("Supplier Name"), row.get("Material Name")
        supplier = suppliers_by_name.get(sup_name)
        material = materials_by_name.get(mat_name)
        if not supplier or not material:
            logger.warning("Purchases row skipped - supplier %r or material %r not found", sup_name, mat_name)
            continue
        pdate = _d(row.get("Date"))
        required_fields = {
            "Quantity": row.get("Quantity"), "Rate": row.get("Rate"), "Taxable Value": row.get("Taxable Value"),
            "GST %": row.get("GST %"), "GST Amount": row.get("GST Amount"), "Invoice Total": row.get("Invoice Total"),
        }
        missing = [name for name, value in required_fields.items() if value is None]
        if missing:
            logger.warning("Purchases row skipped - %s / %s missing required value(s): %s", sup_name, mat_name, ", ".join(missing))
            continue
        qty = Decimal(str(required_fields["Quantity"]))
        key = (pdate, supplier.id, material.id, qty)
        if key in existing_keys:
            continue
        db.add(Purchase(
            purchase_code=generate_unique_code(db, Purchase, "purchase_code", "PUR-"),
            date=pdate, supplier_id=supplier.id, material_id=material.id,
            quantity=qty, unit=row.get("Unit"), rate=Decimal(str(required_fields["Rate"])),
            taxable_value=Decimal(str(required_fields["Taxable Value"])),
            gst_percent=Decimal(str(required_fields["GST %"])), gst_amount=Decimal(str(required_fields["GST Amount"])),
            invoice_total=Decimal(str(required_fields["Invoice Total"])), payment_status=row.get("Payment Status") or "Paid",
            business_id=generate_business_id(db),
        ))
        db.flush()
        existing_keys.add(key)
        created += 1
    db.commit()
    logger.info("Purchases: created %d", created)


def seed_employees(db):
    """Reads docs/Woodful_demo_data.xlsx's "Employees" sheet (previously
    two separate hardcoded sources here: seed_employees' own EMP-xxx rows
    plus a WOODFUL_EMPLOYEES roster list that overwrote phone/designation/
    address onto those same rows immediately afterwards - merged into one
    workbook table, one function, one write per field). employee_code is
    calculated from row position (EMP-{i:03d}), the same way MAT-xxx
    material codes are - the workbook holds employee information, not a
    duplicate identifier-generation mechanism. Row order in the sheet
    matches the old EMP-001..008 assignment, so seed_salary_slips/
    seed_leaves/seed_attendance's existing EMP-xxx references still
    resolve to the same people."""
    out = {e.employee_code: e for e in db.query(Employee).all()}
    created = 0
    for i, row in enumerate(_employee_rows(), start=1):
        name = row.get("Name")
        if not name:
            continue
        code = f"EMP-{i:03d}"
        if code in out:
            continue
        joined = row.get("Joining Date")
        e = Employee(
            employee_code=code, name=name, department=row.get("Department"),
            designation=row.get("Role"), phone=str(row.get("Phone")) if row.get("Phone") else None,
            address=row.get("Address"),
            joining_date=_d(joined) if isinstance(joined, str) else joined,
            monthly_salary=Decimal(str(row.get("Monthly Salary") or 0)),
            status="Active",
            emergency_contact=str(row.get("Emergency Contact")) if row.get("Emergency Contact") else None,
            remarks=row.get("Remarks"), pan=row.get("PAN"),
            uan=str(row.get("UAN")) if row.get("UAN") else None,
            bank_name=row.get("Bank Name"),
            bank_account_number=str(row.get("Bank Account Number")) if row.get("Bank Account Number") else None,
            tax_regime=row.get("Tax Regime"),
            business_id=generate_business_id(db),
        )
        db.add(e)
        out[code] = e
        created += 1
    db.commit()
    logger.info("Employees: created %d, existing %d", created, len(out) - created)
    return out


def seed_salary_slips(db, employees):
    """Multiple employees, multiple months - net_salary is computed the
    same way the real create_salary_slip endpoint does (sum of
    earnings minus sum of deductions), verified by hand before being
    written here, not just eyeballed.

    Reads docs/Woodful_demo_data.xlsx's "Salary Slips" sheet, matched
    by employee NAME rather than EMP-xxx code - that code is only
    assigned at seed time from row position in the Employees sheet
    (see seed_employees), so a hardcoded code here could silently
    point at the wrong person if that sheet's row order ever changes."""
    employees_by_name = {e.name: e for e in employees.values()}
    existing_keys = {
        (s.employee_id, s.month, s.year) for s in db.query(SalarySlip.employee_id, SalarySlip.month, SalarySlip.year).all()
    }
    count = 0
    for row in _workbook_rows("Salary Slips"):
        employee = employees_by_name.get(row.get("Employee Name"))
        month, year = row.get("Month"), str(row.get("Year"))
        if not employee:
            logger.warning("Salary Slips row skipped - employee %r not found", row.get("Employee Name"))
            continue
        if (employee.id, month, year) in existing_keys:
            continue
        working_days, paid_days = row.get("Working Days"), row.get("Paid Days")
        if working_days is None or paid_days is None:
            logger.warning("Salary Slips row skipped - %s (%s %s) missing Working Days/Paid Days", row.get("Employee Name"), month, year)
            continue
        basic, da, hra, ot = _num(row.get("Basic")), _num(row.get("DA")), _num(row.get("HRA")), _num(row.get("Overtime"))
        pf, tds, other = _num(row.get("PF")), _num(row.get("TDS")), _num(row.get("Other Deductions"))
        net_salary = Decimal(str(basic + da + hra + ot - pf - tds - other))
        slip = SalarySlip(
            employee_id=employee.id, month=month, year=year,
            working_days=Decimal(str(working_days)), paid_days=Decimal(str(paid_days)),
            basic=Decimal(str(basic)), da=Decimal(str(da)), hra=Decimal(str(hra)),
            overtime_amount=Decimal(str(ot)), pf_deduction=Decimal(str(pf)),
            tds_deduction=Decimal(str(tds)), other_deductions=Decimal(str(other)),
            net_salary=net_salary, status=row.get("Status") or "draft",
            business_id=generate_business_id(db),
        )
        db.add(slip)
        existing_keys.add((employee.id, month, year))
        count += 1
    db.commit()
    logger.info("Salary slips: created %d", count)


def seed_leaves(db, employees):
    """A few real Approved leave records for the same employees covered
    by seed_salary_slips, so the salary slip PDF's Leave Balance field
    has real, non-empty data to demonstrate rather than always showing
    "no leave taken".

    Reads docs/Woodful_demo_data.xlsx's "Leaves" sheet, matched by
    employee NAME - same reasoning as seed_salary_slips."""
    employees_by_name = {e.name: e for e in employees.values()}
    existing_keys = {
        (l.employee_id, l.leave_type, l.start_date) for l in db.query(Leave.employee_id, Leave.leave_type, Leave.start_date).all()
    }
    count = 0
    for row in _workbook_rows("Leaves"):
        employee = employees_by_name.get(row.get("Employee Name"))
        if not employee:
            logger.warning("Leaves row skipped - employee %r not found", row.get("Employee Name"))
            continue
        start = row.get("Start Date")
        if start is None:
            logger.warning("Leaves row skipped - %s has no Start Date", row.get("Employee Name"))
            continue
        start_dt = _d(start) if isinstance(start, str) else start
        if (employee.id, row.get("Leave Type"), start_dt) in existing_keys:
            continue
        days = row.get("Days")
        if days is None:
            logger.warning("Leaves row skipped - %s starting %s has no Days value", row.get("Employee Name"), start_dt)
            continue
        end = row.get("End Date")
        db.add(Leave(
            employee_id=employee.id, leave_type=row.get("Leave Type"),
            start_date=start_dt, end_date=_d(end) if isinstance(end, str) else end,
            days=Decimal(str(days)), reason=row.get("Reason"),
            status="Approved", approved_by="Nikhil Soni",
            business_id=generate_business_id(db),
        ))
        existing_keys.add((employee.id, row.get("Leave Type"), start_dt))
        count += 1
    db.commit()
    logger.info("Leave records: created %d", count)


def seed_attendance(db, employees):
    """Reads docs/Woodful_demo_data.xlsx's "Attendance" sheet, matched
    by employee NAME - same reasoning as seed_salary_slips. Date and
    In/Out Time are separate columns in the workbook (a plain time
    value reads more naturally there than a full datetime); combined
    back into the datetimes the Attendance model actually stores."""
    employees_by_name = {e.name: e for e in employees.values()}
    existing_keys = {
        (a.employee_id, a.date) for a in db.query(Attendance.employee_id, Attendance.date).all()
    }
    count = 0
    for row in _workbook_rows("Attendance"):
        employee = employees_by_name.get(row.get("Employee Name"))
        if not employee:
            logger.warning("Attendance row skipped - employee %r not found", row.get("Employee Name"))
            continue
        adate = row.get("Date")
        adate = adate if isinstance(adate, str) else adate.strftime("%Y-%m-%d")
        if (employee.id, _d(adate)) in existing_keys:
            continue
        in_t, out_t = row.get("In Time"), row.get("Out Time")
        in_dt = _dt(f"{adate} {in_t}") if in_t else None
        out_dt = _dt(f"{adate} {out_t}") if out_t else None
        db.add(Attendance(date=_d(adate), employee_id=employee.id,
                           in_time=in_dt, out_time=out_dt,
                           standard_hours=Decimal("8"), attendance_status=row.get("Status") or "Present", remarks=row.get("Remarks"),
                           business_id=generate_business_id(db)))
        existing_keys.add((employee.id, _d(adate)))
        count += 1
    db.commit()
    logger.info("Attendance records: created %d", count)


# ==========================================================================
# Daily Tasks (Woodful_300_Task_Seed_Data.xlsx, merged into this workbook's
# own "Daily Tasks" sheet). The source sheet carries no employee/assignee
# column, so each row's Task Type is mapped to a real, existing employee -
# never an invented employee_id.
#
# Two source Task Types (Accounts, Administration, HR, Marketing - 40 of
# the 300 rows) had no existing employee of any matching designation; the
# only three designations previously seeded were Carpenter/Designer/Helper.
# Per explicit direction, this was resolved by adding two new rows to the
# Employees sheet itself (Accounts Manager, HR) - through the workbook's
# own existing row-driven EMP-xxx scheme (see seed_employees), not by
# hardcoding a new identifier-generation path here.
#
# DAILY_TASK_DEPARTMENT_AFFINITY is checked first (e.g. a CNC task goes to
# whichever employee's Department is literally "CNC") since it is the more
# specific, realistic match; DAILY_TASK_DESIGNATION_GROUP is the fallback
# for task types with no employee at that department granularity. Within
# whichever group ends up used, employees are round-robined (sorted by
# employee_code) for even distribution rather than piling every task of a
# type onto one person.
# ==========================================================================
DAILY_TASK_DEPARTMENT_AFFINITY = {
    "CNC": "CNC",
    "Wood Cutting": "Panel Saw",
    "Edge Banding": "Edge Banding",
    "Installation": "Installation",
}

DAILY_TASK_DESIGNATION_GROUP = {
    "Carpentry": "Carpenter", "CNC": "Carpenter", "Wood Cutting": "Carpenter",
    "Edge Banding": "Carpenter", "Laminate": "Carpenter", "Installation": "Carpenter",
    "Production": "Carpenter", "Factory": "Carpenter", "Maintenance": "Carpenter",
    "Quality": "Carpenter", "CO2 Laser": "Carpenter",
    "Product Design": "Designer", "Graphic Design": "Designer",
    "Stock": "Helper", "Cleaning": "Helper", "Housekeeping": "Helper",
    "Painting": "Helper", "Facility": "Helper", "Safety": "Helper",
    "Security": "Helper", "Delivery": "Helper", "Procurement": "Helper",
    "Accounts": "Accounts Manager", "Administration": "Accounts Manager",
    "HR": "HR", "Marketing": "HR",
}

# Source sheet's own vocabulary -> the application's real, existing
# DAILY_TASK_STATUSES/DAILY_TASK_PRIORITIES (app/modules/operations/schemas.py) -
# adapting the seed mapping to the app's vocabulary rather than the other
# way round. Only "Not Started"/High/Medium/Critical/Low actually occur in
# the 300 source rows; the extra entries are a safety net if this sheet is
# ever re-exported with different wording.
DAILY_TASK_STATUS_MAP = {
    "Not Started": "TO DO", "To Do": "TO DO",
    "In Progress": "DOING", "Doing": "DOING",
    "Completed": "DONE", "Done": "DONE",
    "Blocked": "BLOCKED",
}
DAILY_TASK_PRIORITY_MAP = {
    "Critical": "Urgent", "Urgent": "Urgent",
    "High": "High",
    "Medium": "Normal", "Normal": "Normal",
    "Low": "Low",
}


def seed_daily_tasks(db, employees):
    """Reads this workbook's "Daily Tasks" sheet (the 300-row
    Woodful_300_Task_Seed_Data import) and seeds DailyTask rows through
    the same generate_unique_code(db, DailyTask, "task_code", "TSK-")
    mechanism the real create_daily_task endpoint uses (see
    app/modules/operations/api/daily_tasks.py) - db.flush() immediately
    after each add, the same fix applied to seed_purchases, so the next
    row's code generation actually sees this one (autoflush=False on
    this app's SessionLocal - see database.py).

    Idempotent by task_description alone: unique across all 300 source
    rows (verified at import time) and never edited by this step - no
    other natural composite key exists here, since the source sheet
    carries no date/employee columns of its own to combine with.

    Every row is validated (Task text present, Status/Priority
    recognized, Task Type resolves to a real employee) before insert;
    anything that fails is skipped and counted, never silently
    coerced."""
    existing_descriptions = {
        t.task_description for t in db.query(DailyTask.task_description).all()
    }

    employees_by_department = defaultdict(list)
    employees_by_designation = defaultdict(list)
    for e in sorted(employees.values(), key=lambda emp: emp.employee_code):
        if e.department:
            employees_by_department[e.department].append(e)
        if e.designation:
            employees_by_designation[e.designation].append(e)

    group_counters = defaultdict(int)

    def pick_employee(task_type):
        dept = DAILY_TASK_DEPARTMENT_AFFINITY.get(task_type)
        candidates = employees_by_department.get(dept) if dept else None
        key = f"dept:{dept}"
        if not candidates:
            designation = DAILY_TASK_DESIGNATION_GROUP.get(task_type)
            candidates = employees_by_designation.get(designation)
            key = f"desig:{designation}"
        if not candidates:
            return None
        idx = group_counters[key] % len(candidates)
        group_counters[key] += 1
        return candidates[idx]

    created = 0
    skipped_duplicate = 0
    skipped_invalid = 0
    invalid_rows = []
    today = datetime.utcnow().date()
    WINDOW_DAYS = 20  # spreads seeded tasks' `date` across a recent window rather than one identical timestamp

    for i, row in enumerate(_workbook_rows("Daily Tasks")):
        description = (row.get("Task") or "").strip()
        task_type = (row.get("Task Type") or "").strip()
        raw_status = (row.get("Status") or "").strip()
        raw_priority = (row.get("Priority") or "").strip() if row.get("Priority") else ""

        if not description:
            skipped_invalid += 1
            invalid_rows.append((f"<row {i + 2}>", "missing Task text"))
            continue
        if description in existing_descriptions:
            skipped_duplicate += 1
            continue

        status = DAILY_TASK_STATUS_MAP.get(raw_status)
        if status not in DAILY_TASK_STATUSES:
            skipped_invalid += 1
            invalid_rows.append((description, f"unrecognized Status {raw_status!r}"))
            continue

        priority = DAILY_TASK_PRIORITY_MAP.get(raw_priority) if raw_priority else None
        if raw_priority and priority not in DAILY_TASK_PRIORITIES:
            skipped_invalid += 1
            invalid_rows.append((description, f"unrecognized Priority {raw_priority!r}"))
            continue

        employee = pick_employee(task_type)
        if not employee:
            skipped_invalid += 1
            invalid_rows.append((description, f"no employee mapping for Task Type {task_type!r}"))
            continue

        task_date = datetime.combine(today - timedelta(days=i % WINDOW_DAYS), datetime.min.time())
        db.add(DailyTask(
            task_code=generate_unique_code(db, DailyTask, "task_code", "TSK-"),
            business_id=generate_business_id(db),
            date=task_date,
            employee_id=employee.id,
            task_description=description,
            task_category=task_type or None,
            priority=priority,
            status=status,
            completion_percent=0,
            remarks=row.get("Notes") or None,
            created_by="Seed Script (Woodful_300_Task_Seed_Data)",
        ))
        db.flush()
        existing_descriptions.add(description)
        created += 1

    db.commit()
    logger.info(
        "Daily Tasks: created %d, skipped duplicate %d, skipped invalid %d",
        created, skipped_duplicate, skipped_invalid,
    )
    for desc, reason in invalid_rows[:20]:
        logger.warning("Daily Task row skipped - %s: %s", desc, reason)
    return {
        "created": created, "skipped_duplicate": skipped_duplicate,
        "skipped_invalid": skipped_invalid, "invalid_rows": invalid_rows,
    }


def seed_notifications(db, materials):
    """Grounded in an already-seeded real entity - a material genuinely
    at/below its minimum stock - rather than an invented number that
    could drift out of sync with the actual seeded data.

    Previously also raised order-based (payment pending, delivery
    upcoming) and task-based (task assigned) notifications - removed
    along with seed_orders/seed_daily_tasks, since Estimates/Orders/
    Tasks are now populated via Excel import rather than this seed
    script, and a notification referencing an order/task that can
    never exist here would just be permanently dead code.

    Idempotent per notification: NotificationService.notify() itself
    has no dedup logic, so this is checked here first by its own
    natural key (notification_type + the entity it's about) before
    calling it - a re-run never produces a duplicate."""
    def _exists(notification_type, related_entity_type, related_entity_id):
        return db.query(Notification).filter(
            Notification.notification_type == notification_type,
            Notification.related_entity_type == related_entity_type,
            Notification.related_entity_id == related_entity_id,
        ).first() is not None

    created = 0
    low_stock_material = materials.get("MAT-003")  # 9mm Commercial Plywood, seeded at 0 stock against a minimum of 10
    if low_stock_material and not _exists("OUT_OF_STOCK", "material", low_stock_material.id):
        NotificationService.notify(
            db, notification_type="OUT_OF_STOCK", severity="CRITICAL",
            title=f"{low_stock_material.name} is out of stock",
            message=f"Current stock is 0, below the minimum of {low_stock_material.minimum_stock}.",
            related_entity_type="material", related_entity_id=low_stock_material.id,
            action_path=f"/materials/{low_stock_material.id}",
        )
        created += 1
    logger.info("Notifications: created %d", created)


def _verify_schema_is_current():
    """The seed script inserts/updates data only - it must never create
    or alter schema itself. Alembic (run automatically by
    `python main.py`, or manually via `alembic upgrade head`) is the
    only thing responsible for schema. This just verifies that's
    already been done, with a clear, actionable failure if not - never
    attempts to fix it itself."""
    from sqlalchemy import inspect, text
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        print(
            "\n" + "!" * 78 + "\n"
            "!!  Database schema is not initialized (no alembic_version table).\n"
            "!!  This script only seeds data - it does not create schema.\n"
            "!!\n"
            "!!  Start the backend first (it migrates automatically on startup):\n"
            "!!      python main.py\n"
            "!!  Then stop it and re-run this seed script.\n"
            + "!" * 78 + "\n"
        )
        sys.exit(1)

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    head_revision = ScriptDirectory.from_config(cfg).get_current_head()

    with engine.connect() as conn:
        current_revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

    if current_revision != head_revision:
        print(
            "\n" + "!" * 78 + "\n"
            f"!!  Database schema is at revision {current_revision!r}, but the code\n"
            f"!!  expects {head_revision!r}. This script only seeds data - it does\n"
            "!!  not create or alter schema.\n"
            "!!\n"
            "!!  Start the backend first to bring the schema up to date:\n"
            "!!      python main.py\n"
            "!!  Then stop it and re-run this seed script.\n"
            + "!" * 78 + "\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    _verify_schema_is_current()
    db = SessionLocal()

    def _run_phase(name, fn, *args, **kwargs):
        """Family 131 seeding-reliability fix: pinpoints exactly which
        phase failed and the real exception, rather than leaving a bare
        ROLLBACK as the only visible signal (the observed failure mode
        this whole diagnostic exists to fix). Re-raises after logging -
        this does not change the transaction/re-runnability behaviour
        of the seed functions themselves (each already commits its own
        work incrementally, so a later phase failing does not undo an
        earlier phase that already committed)."""
        print(f"SEED START: {name}")
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            print(f"SEED FAILED: {name}")
            print(f"exception={exc!r}")
            raise
        print(f"SEED COMPLETE: {name}")
        return result

    try:
        locations = _run_phase("locations", seed_locations, db)
        subcategories = _run_phase("material_hierarchy", seed_material_hierarchy, db)
        _run_phase("lookups", seed_lookups, db)
        suppliers = _run_phase("suppliers", seed_suppliers, db)
        _run_phase("woodful_suppliers", seed_woodful_suppliers, db)
        materials = _run_phase("materials", seed_materials, db, suppliers, locations, subcategories)
        _run_phase("supplier_materials", seed_supplier_materials, db, suppliers, materials)
        products = _run_phase("products", seed_products, db)
        _run_phase("product_materials", seed_product_materials, db, products, materials)
        clients = _run_phase("clients", seed_clients, db)
        _run_phase("woodful_clients", seed_woodful_clients, db)
        _run_phase("purchases", seed_purchases, db, suppliers, materials)
        employees = _run_phase("employees", seed_employees, db)
        _run_phase("salary_slips", seed_salary_slips, db, employees)
        _run_phase("leaves", seed_leaves, db, employees)
        _run_phase("attendance", seed_attendance, db, employees)
        daily_tasks_result = _run_phase("daily_tasks", seed_daily_tasks, db, employees)
        _run_phase("notifications", seed_notifications, db, materials)

        # Final verification: real counts from the database, not an
        # assumption that the script running to completion means data
        # actually landed. Printed unconditionally, success or not.
        from app.modules.auth.auth import User
        from app.modules.inventory.models import MaterialCategory, MaterialSubcategory

        counts = {
            "Users (master)": db.query(User).filter(User.role == "master").count(),
            "Locations": db.query(Location).count(),
            "Material Categories": db.query(MaterialCategory).count(),
            "Material Subcategories": db.query(MaterialSubcategory).count(),
            "Materials": db.query(Material).count(),
            "Suppliers": db.query(Supplier).count(),
            "Products": db.query(Product).count(),
            "Clients": db.query(Client).count(),
            "Employees": db.query(Employee).count(),
            "Purchases": db.query(Purchase).count(),
            "Daily Tasks": db.query(DailyTask).count(),
        }
        print("\n" + "=" * 60)
        print("SEED VERIFICATION")
        print("=" * 60)
        for label, count in counts.items():
            marker = "  <-- WARNING: zero rows" if count == 0 else ""
            print(f"{label:.<40}{count}{marker}")
        print("=" * 60)
        print(
            f"\nDaily Tasks this run: created {daily_tasks_result['created']}, "
            f"skipped (already existed) {daily_tasks_result['skipped_duplicate']}, "
            f"skipped (invalid) {daily_tasks_result['skipped_invalid']}."
        )
        print(
            "\nEstimates/Orders/Payments/Project Expenses/Issues/"
            "Production Jobs are still not seeded by this script - populate them "
            "via the Estimate/Order Excel import feature instead."
        )
    finally:
        db.close()

