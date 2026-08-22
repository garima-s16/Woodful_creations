"""
Woodful Master Catalogue extension.

This module ADDS to the existing scripts/seed_sample_data.py seed system
rather than replacing any part of it - per the master-seed brief's own
instructions ("do not unnecessarily redesign existing modules", "extend
the existing schema only where required", "do not break existing data").

It brings the Product Master and Material Master up to the brief's
"at least 140 products" / rich-material-catalogue targets, adds
representative BOM links for the specific products the brief calls out
by name, and adds a handful of additional Estimates/Orders so the
catalogue's CNC, Laser and Modular Kitchen categories actually show up
in real transactions (not just sit in the product list unused).

Idempotent per-record, exactly like every function in seed_sample_data.py:
each row is looked up by its own stable code (PRD-xxx / MAT-xxx / EST-xxx /
WC-2026-xxx) before insert, so re-running seed_sample_data.py never
duplicates anything here.
"""
import logging
from datetime import datetime
from decimal import Decimal

from app.models.product import Product, ProductMaterial
from app.models.material import Material
from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.utils.id_generator import generate_business_id

from scripts._extended_products_data import EXTENDED_PRODUCT_ROWS
from scripts._extended_materials_data import EXTENDED_MATERIAL_ROWS

logger = logging.getLogger(__name__)


# ==========================================================================
# MATERIALS - Section 5/6 of the brief: board materials, solid wood,
# laminates/surfaces, acrylic, laser sheet materials, edge materials,
# hardware, adhesives/consumables, finishing, packaging - each with a
# sensible UOM (never litres for a sheet good, never "Nos" for adhesive).
# ==========================================================================
def seed_extended_materials(db, suppliers, locations, subcategories):
    """Adds ~86 more Material Master rows (MAT-011 onward) on top of the
    existing 10, covering every material family the brief calls out.
    Falls back gracefully (no supplier / no subcategory / no location)
    for the small number of rows that reference a supplier or location
    not present in this database, rather than crashing the whole seed."""
    out = {m.material_code: m for m in db.query(Material).all()}
    created = 0
    for (code, name, cat, brand, size, unit, opening, purchased, issued,
         current, minimum, rate, sup_code, loc) in EXTENDED_MATERIAL_ROWS:
        if code in out:
            continue
        location_row = locations.get(loc)
        subcategory_row = subcategories.get(cat)
        supplier_row = suppliers.get(sup_code)
        m = Material(
            material_code=code, name=name, category=cat, brand_grade=brand,
            thickness_size=size, unit=unit,
            opening_stock=Decimal(str(opening)), total_purchased=Decimal(str(purchased)),
            total_issued=Decimal(str(issued)), current_stock=Decimal(str(current)),
            minimum_stock=Decimal(str(minimum)), average_rate=Decimal(str(rate)),
            supplier_id=supplier_row.id if supplier_row else None, location=loc,
            location_id=location_row.id if location_row else None,
            subcategory_id=subcategory_row.id if subcategory_row else None,
            business_id=generate_business_id(db),
        )
        db.add(m)
        out[code] = m
        created += 1
    db.commit()
    logger.info("Extended materials: created %d, existing %d", created, len(out) - created)
    return out


# ==========================================================================
# PRODUCTS - Section 3/4 of the brief: Furniture (Living Room, Bedroom,
# Dining, Study & Office, Storage & Other), Modular Kitchen, CNC Products
# & Services, CO2 Laser Products & Services, Decor & Architectural
# Products, and Design/Finishing Services - ~170 additional rows on top
# of the existing 11, all original Woodful-style names (not copied from
# any retailer).
# ==========================================================================
def seed_extended_products(db):
    """Adds the extended catalogue (PRD-012 onward). Idempotent per
    product_code, identical pattern to seed_products in seed_sample_data.py."""
    out = {p.product_code: p for p in db.query(Product).all()}
    created = 0
    for (code, name, ptype, cat, sub, unit, length, width, height, dim_unit,
         primary_mat, finish, mat_c, hw_c, lab_c, mach_c, fin_c, pack_c,
         trans_c, other_c, overhead, margin, cost, selling) in EXTENDED_PRODUCT_ROWS:
        if code in out:
            continue
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
        created += 1
    db.commit()
    logger.info("Extended products: created %d, existing %d", created, len(out) - created)
    return out


# ==========================================================================
# BOM - Section 7 of the brief names these specific products as the
# required minimum BOM set. King Storage Bed / 6-Seater Dining Table /
# TV Storage Unit / Three-Door Wardrobe are covered by the ORIGINAL
# seed_products catalogue under close equivalents; the rows below add
# the ones only the extended catalogue introduces (Modular Kitchen
# units, CNC/Laser decor pieces).
# ==========================================================================
def seed_extended_product_materials(db, products, materials):
    # Build the real, meaningful mapping by product name instead of a
    # blind code list, since the extended catalogue's codes were
    # generated programmatically (see gen.py) - matching by name keeps
    # this readable and correct even if the generation order changes.
    by_name = {p.name: p for p in products.values()}

    def bom(product_name, material_code, qty, unit):
        product = by_name.get(product_name)
        material = materials.get(material_code)
        if not product or not material:
            return None
        return (product.id, material.id, qty, unit)

    wanted = [
        # King Storage Bed (Section 7's required example) - BWP plywood
        # box base with veneer facing and a hydraulic lift fitting.
        ("King Hydraulic Storage Bed", "MAT-014", 3, "Sheets"),   # BWP Plywood 18mm (Alt Grade)
        ("King Hydraulic Storage Bed", "MAT-047", 1, "Sheets"),  # Decorative Veneer Sheet
        # Three-Door Wardrobe - BWP plywood carcass, laminate finish,
        # soft-close hinges and handles.
        ("Three-Door Wardrobe", "MAT-014", 3, "Sheets"),          # BWP Plywood 18mm (Alt Grade)
        ("Three-Door Wardrobe", "MAT-027", 2, "Sheets"),          # Matte White Laminate 1mm
        ("Three-Door Wardrobe", "MAT-006", 8, "Nos"),             # Soft Close Hinges (original MAT-006)
        ("Three-Door Wardrobe", "MAT-071", 3, "Nos"),             # Wardrobe Hanging Rod
        # Six-Seater Solid Wood Dining Table - sheesham solid wood + polish.
        ("Six-Seater Solid Wood Dining Table", "MAT-025", 4, "Cu Ft"),   # Sheesham Wood Plank
        ("Six-Seater Solid Wood Dining Table", "MAT-085", 2, "Litres"),  # Wood Polish
        # Full TV Feature Wall Unit - plywood + MDF + veneer accents.
        ("Full TV Feature Wall Unit", "MAT-014", 2, "Sheets"),    # BWP Plywood 18mm (Alt Grade)
        ("Full TV Feature Wall Unit", "MAT-017", 1, "Sheets"),    # MDF 18mm
        ("Full TV Feature Wall Unit", "MAT-047", 1, "Sheets"),    # Decorative Veneer Sheet
        # Modular Kitchen Base Cabinet - HDHMR carcass, tandem drawers.
        ("Modular Kitchen Base Cabinet", "MAT-015", 2, "Sheets"), # HDHMR 12mm
        ("Modular Kitchen Base Cabinet", "MAT-054", 1, "Sets"),   # Tandem Drawer System
        ("Modular Kitchen Base Cabinet", "MAT-048", 15, "Metres"),  # PVC Edge Band 0.8mm
        # Modular Kitchen Wall Cabinet - HDHMR carcass, hinges.
        ("Modular Kitchen Wall Cabinet", "MAT-015", 1, "Sheets"), # HDHMR 12mm
        ("Modular Kitchen Wall Cabinet", "MAT-051", 4, "Nos"),    # Concealed Hinges
        # Sink Base Cabinet - moisture-resistant HDHMR, catch fitting.
        ("Sink Base Cabinet", "MAT-015", 1, "Sheets"),            # HDHMR 12mm
        ("Sink Base Cabinet", "MAT-059", 2, "Nos"),               # Magnetic Door Catch
        # CNC Decorative Panel (generic representative) - MDF board.
        ("CNC Decorative Ceiling Panel", "MAT-017", 1, "Sheets"), # MDF 18mm
        # CNC Mandir Back Panel - HDHMR carved face over a plywood base.
        ("CNC Mandir Back Panel", "MAT-015", 1, "Sheets"),        # HDHMR 12mm (carved face)
        ("CNC Mandir Back Panel", "MAT-014", 1, "Sheets"),        # BWP Plywood 18mm (base)
        # Layered Mandala Wall Panel - multiple laser-cut MDF layers.
        ("Layered Mandala Wall Panel", "MAT-042", 3, "Sheets"),   # MDF Laser Sheet 3mm
        # Laser-Cut Pendant Lamp - birch ply laser sheet shade.
        ("Laser-Cut Pendant Lamp", "MAT-045", 1, "Sheets"),       # Birch Ply Laser Sheet 3mm
        # Laser Nameplate - acrylic base with a laser-sheet backing.
        ("Laser Nameplate - Single Name", "MAT-039", 1, "Sheets"),  # Gold Mirror Acrylic 3mm
        ("Laser Nameplate - Single Name", "MAT-042", 1, "Sheets"),  # MDF Laser Sheet 3mm
    ]
    existing_pairs = {
        (pm.product_id, pm.material_id)
        for pm in db.query(ProductMaterial.product_id, ProductMaterial.material_id).all()
    }
    count = 0
    for product_name, mat_code, qty, unit in wanted:
        row = bom(product_name, mat_code, qty, unit)
        if not row:
            continue
        product_id, material_id, qty, unit = row
        if (product_id, material_id) in existing_pairs:
            continue
        db.add(ProductMaterial(product_id=product_id, material_id=material_id,
                                quantity_required=Decimal(str(qty)), unit=unit))
        existing_pairs.add((product_id, material_id))
        count += 1
    db.commit()
    logger.info("Extended product-material BOM links: created %d", count)


# ==========================================================================
# ESTIMATES/ORDERS DIVERSIFICATION - Section 16 asks for estimate line
# items spanning "sofa, coffee table, wardrobe, dining table, TV unit,
# modular kitchen, mandala wall art, CNC panel, laser lamp, nameplate,
# bed, crockery unit" across MULTIPLE clients. The original seed
# already covers sofa/coffee table/wardrobe/dining/TV unit/kitchen;
# this adds the remaining categories (mandala, CNC panel, laser lamp,
# nameplate, bed, crockery unit) using existing Woodful-roster clients
# so nothing here needs a new Client record.
# ==========================================================================
def seed_extended_estimates_and_orders(db, clients, orders, products):
    """clients: dict from seed_clients (CL-xxx). Adds EST-010.. / a couple
    of WC-2026-01x orders using existing CL-xxx clients plus their line
    items, covering the decor/CNC/laser categories the original demo
    estimates didn't touch."""
    by_name = {p.name: p for p in products.values()}

    def prod(name):
        return by_name.get(name)

    # ---- New estimates (never converted - genuinely pending/declined,
    # matching the brief's own instruction that not every estimate
    # becomes an order) ----
    est_rows = [
        # code, client_code, status, product_name, qty, rate_override(optional), valid_until, remarks, estimate_date
        ("EST-010", "CL-004", "sent", "Layered Mandala Wall Panel", 2, None, "2026-09-10", "Mandala wall art quotation for the mandir room", "2026-08-12"),
        ("EST-011", "CL-007", "draft", "CNC Mandir Back Panel", 1, None, "2026-09-15", "CNC mandir panel quotation, awaiting site visit", "2026-08-16"),
        ("EST-012", "CL-009", "sent", "Laser-Cut Pendant Lamp", 3, None, "2026-09-12", "Laser-cut pendant lamps for the living room", "2026-08-19"),
        ("EST-013", "CL-010", "sent", "House Entrance Nameplate", 1, None, "2026-09-14", "Entrance nameplate quotation", "2026-08-20"),
    ]
    e_out = {e.estimate_code: e for e in db.query(Estimate).all()}
    e_created = 0
    for code, cl_code, status, prod_name, qty, rate_override, valid_until, remarks, edate in est_rows:
        if code in e_out:
            continue
        client = clients.get(cl_code)
        product = prod(prod_name)
        if not client or not product:
            continue
        rate = Decimal(str(rate_override)) if rate_override is not None else Decimal(str(product.selling_price))
        material_cost = rate * Decimal(str(qty))
        e = Estimate(
            estimate_code=code, client_id=client.id, order_id=None,
            material_cost=material_cost, labor_cost=Decimal("0"),
            discount=Decimal("0"), tax_percent=Decimal("18"),
            tax_amount=(material_cost * Decimal("18") / Decimal("100")).quantize(Decimal("0.01")),
            total_cost=(material_cost + material_cost * Decimal("18") / Decimal("100")).quantize(Decimal("0.01")),
            status=status, valid_until=datetime.strptime(valid_until, "%Y-%m-%d"),
            remarks=remarks, business_id=generate_business_id(db),
            created_at=datetime.strptime(edate, "%Y-%m-%d"),
            updated_at=datetime.strptime(edate, "%Y-%m-%d"),
        )
        db.add(e)
        db.flush()
        db.add(EstimateLineItem(
            estimate_id=e.id, description=prod_name, category="Furniture", quantity=Decimal(str(qty)),
            unit=product.unit, rate=rate, amount=rate * Decimal(str(qty)), sort_order=0,
            product_id=product.id,
        ))
        e_out[code] = e
        e_created += 1
    db.commit()
    logger.info("Extended estimates: created %d", e_created)

    # ---- A new order that actually carries a crockery unit + a bed,
    # so those two categories show up in real (not just estimated)
    # transactions too, per Section 17. ----
    order_rows = [
        # code, client_code, project_type, order_date, delivery_date, product_names(list of (name, qty)), status, progress, priority, supervisor, site_addr, remarks
        ("WC-2026-010", "CL-004", "Other", "2026-08-10", "2026-09-05",
         [("Glass-Front Crockery Display Unit", 1), ("King Platform Bed", 1)],
         "Material Purchase", 20, "Medium", "Pankaj", "Rau", "Crockery unit + bed, direct order"),
    ]
    o_out = {o.order_code: o for o in db.query(Order).all()}
    o_created = 0
    for code, cl_code, ptype, odate, ddate, line_items, status, progress, priority, sup, addr, remarks in order_rows:
        if code in o_out:
            continue
        client = clients.get(cl_code)
        if not client:
            continue
        total = sum(Decimal(str(prod(name).selling_price)) * qty for name, qty in line_items if prod(name))
        o = Order(
            order_code=code, client_id=client.id, project_type=ptype,
            order_date=datetime.strptime(odate, "%Y-%m-%d"), delivery_date=datetime.strptime(ddate, "%Y-%m-%d"),
            order_value=total, discount=Decimal("0"), tax_percent=Decimal("18"),
            tax_amount=(total * Decimal("18") / Decimal("100")).quantize(Decimal("0.01")),
            advance=Decimal("0"), other_received=Decimal("0"), total_received=Decimal("0"), balance=total,
            project_status=status, progress_percent=progress, priority=priority,
            supervisor=sup, site_address=addr, remarks=remarks,
            business_id=generate_business_id(db),
        )
        db.add(o)
        db.flush()
        for sort_order, (name, qty) in enumerate(line_items):
            product = prod(name)
            if not product:
                continue
            rate = Decimal(str(product.selling_price))
            db.add(OrderItem(
                order_id=o.id, description=name, category="Furniture", quantity=Decimal(str(qty)),
                unit=product.unit, rate=rate, amount=rate * qty, sort_order=sort_order,
                product_id=product.id,
            ))
        o_out[code] = o
        o_created += 1
    db.commit()
    logger.info("Extended orders: created %d", o_created)
