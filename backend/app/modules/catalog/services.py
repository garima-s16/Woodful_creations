"""Chatbot catalog-domain query/action handlers - product search,
add/delete product actions, and cart-optimization (cheapest-supplier
comparison across cart items). Split out of the former monolithic
chat_service.py - see chat_inventory.py's docstring for why."""
import re
from decimal import Decimal

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from app.modules.inventory.models import Material
from app.modules.procurement.models import SupplierMaterial
from app.modules.catalog.models import Product
from app.modules.sales.models import OrderItem, EstimateLineItem
from app.modules.ai.schemas import ProposedAction


def _route_product_search(m: str, db: Session, user_role: str):
    """"find dining tables", "show products containing dining",
    "find PROD-001", "what is PROD-001", "show active dining
    products" - read-only, results always
    come from the actual Product Master, never invented."""
    code_match = re.search(r"\bprd-\d+\b", m, re.IGNORECASE)
    if code_match:
        product = db.query(Product).filter(Product.product_code.ilike(code_match.group(0))).first()
        if not product:
            return f"I couldn't find a product with code {code_match.group(0).upper()}.", [], None, None, []
        price = f"Rs {float(product.selling_price):,.2f}" if product.selling_price is not None else "no default rate set"
        lines = [f"{product.product_code} - {product.name}. {product.category or 'Uncategorized'}, "
                 f"unit: {product.unit}, {price}, {'Active' if product.is_active else 'Inactive'}."]
        return " ".join(lines), [], None, None, [{
            "type": "Product", "label": product.name, "sublabel": product.product_code,
            "path": f"/products/{product.id}",
        }]

    triggered = (
        any(w in m for w in ["find", "search product", "products containing"])
        or re.search(r"\bshow\b.*\bproducts?\b", m)
    )
    if not triggered:
        return None

    want_active_only = "active" in m
    # Strip the trigger phrasing to isolate the search term - a
    # short, deliberately simple extraction (not a full NLU parse)
    # matching the style of the other chat parsers in this file.
    # Word-boundary regex, not naive substring replace - "product"
    # is a substring of "products", so a plain .replace() would
    # mangle "products" into a stray "s" once "product" was
    # stripped out of the middle of it.
    term = m
    for phrase in ["find product", "find", "search product", "products containing", "show", "products", "product", "active"]:
        term = re.sub(rf"\b{re.escape(phrase)}\b", " ", term)
    term = re.sub(r"\s+", " ", term).strip()
    if not term or len(term) < 3:
        return "What product would you like to search for? Try at least 3 characters of the name.", [], None, None, []

    query = db.query(Product).filter(or_(
        Product.name.ilike(f"%{term}%"), Product.product_code.ilike(f"%{term}%"),
    ))
    if want_active_only:
        query = query.filter(Product.is_active == True)  # noqa: E712
    matches = query.order_by(Product.name).limit(8).all()
    if not matches:
        return f"No products found matching \"{term}\".", [], None, None, []

    records = [{
        "type": "Product", "label": p.name, "sublabel": p.product_code, "path": f"/products/{p.id}",
    } for p in matches]
    summary = "; ".join(f"{p.product_code} - {p.name}" for p in matches)
    return f"Found {len(matches)} product(s): {summary}.", [], None, None, records


def _route_add_product_action(m: str, db: Session, user_role: str):
    """"Add a new product called 6 Seater Dining Table, category
    Dining, unit Piece, rate 25000 and GST 18%" - same proposal-then-confirm architecture as
    _route_add_employee_action/_route_material_action: the chatbot
    never writes to the database directly, it builds a
    ProposedAction the frontend executes via the SAME authorized
    POST /api/products/ endpoint the UI form uses, after the user
    confirms - so validation, RBAC, and audit logging all happen
    exactly once, in one place."""
    match = re.match(r"^add\s+(?:a\s+|an\s+|new\s+)*product\s+(?:called\s+|named\s+)?(.+)", m, re.IGNORECASE)
    if not match:
        return None
    if user_role not in ("master",):
        return "Creating products requires a master account.", [], None, None, []

    rest = match.group(1)
    # "6 seater dining table, category dining, unit piece, rate 25000 and gst 18%"
    name_part = re.split(r",|\bcategory\b|\bunit\b|\brate\b|\bgst\b", rest, maxsplit=1)[0].strip().rstrip(".")
    if not name_part:
        return "What should the new product be called?", [], None, None, []

    category_match = re.search(r"category\s+([a-zA-Z ]+?)(?:,|\bunit\b|\brate\b|\bgst\b|$)", rest, re.IGNORECASE)
    unit_match = re.search(r"unit\s+([a-zA-Z ]+?)(?:,|\bcategory\b|\brate\b|\bgst\b|$)", rest, re.IGNORECASE)
    rate_match = re.search(r"rate\s+(?:rs\.?\s*)?([\d,]+)", rest, re.IGNORECASE)
    gst_match = re.search(r"gst\s+([\d.]+)\s*%?", rest, re.IGNORECASE)

    display_name = " ".join(w.capitalize() for w in name_part.split())

    # Duplicate check - blocked, not just
    # warned, for the chat path specifically: a short natural-
    # language message is a poor place to review a "possible
    # duplicate" match list, unlike the UI form's confirm dialog.
    existing = db.query(Product).filter(Product.name.ilike(f"%{name_part}%")).first()
    if existing:
        return (
            f"A product called \"{existing.name}\" ({existing.product_code}) already exists. Nothing created.",
            [], None, None, [{
                "type": "Product", "label": existing.name, "sublabel": existing.product_code,
                "path": f"/products/{existing.id}",
            }],
        )

    payload = {"name": display_name}
    summary_parts = [display_name]
    if category_match:
        payload["category"] = category_match.group(1).strip().title()
        summary_parts.append(f"category: {payload['category']}")
    if unit_match:
        payload["unit"] = unit_match.group(1).strip().title()
        summary_parts.append(f"unit: {payload['unit']}")
    if rate_match:
        payload["selling_price"] = float(rate_match.group(1).replace(",", ""))
        summary_parts.append(f"rate: Rs {payload['selling_price']:,.2f}")
    if gst_match:
        payload["gst_percent"] = float(gst_match.group(1))
        summary_parts.append(f"GST: {payload['gst_percent']}%")

    proposal = ProposedAction(
        action_type="create_product",
        summary="Create product " + ", ".join(summary_parts),
        payload=payload,
    )
    return f"Create a new product \"{display_name}\"" + (f" ({', '.join(summary_parts[1:])})" if len(summary_parts) > 1 else "") + "?", [], proposal, None, []


def _route_delete_product_action(m: str, db: Session, user_role: str):
    """"Delete PROD-001" - Master only,
    checked here first (before the DB lookup even runs, so a non-
    master gets a clear refusal rather than a confusing "not
    found"); historically-referenced products are refused with a
    deactivation suggestion, matching the UI's own delete-route
    behavior exactly (same historical-reference queries)."""
    match = re.match(r"^delete\s+(prd-\d+)\b", m, re.IGNORECASE)
    if not match:
        return None
    if user_role not in ("master",):
        return "You do not have permission to delete products.", [], None, None, []

    code = match.group(1).upper()
    product = db.query(Product).filter(Product.product_code == code).first()
    if not product:
        return f"I couldn't find a product with code {code}.", [], None, None, []

    has_orders = db.query(OrderItem).filter(OrderItem.product_id == product.id).first() is not None
    has_estimates = db.query(EstimateLineItem).filter(EstimateLineItem.product_id == product.id).first() is not None
    if has_orders or has_estimates:
        return (
            f"{product.product_code} ({product.name}) is used in historical "
            f"{'orders' if has_orders else 'estimates'} and cannot be deleted. Deactivate it instead.",
            [], None, None, [{"type": "Product", "label": product.name, "sublabel": product.product_code,
                               "path": f"/products/{product.id}"}],
        )

    proposal = ProposedAction(
        action_type="delete_product",
        summary=f"Permanently delete {product.product_code} - {product.name}",
        payload={"productId": product.id, "productCode": product.product_code},
    )
    return f"Permanently delete {product.product_code} - {product.name}? This cannot be undone.", [], proposal, None, []


def _optimize_cart(db: Session, cart_items):
    """For each cart line, finds the real cheapest available
    supplier (via SupplierMaterial pricing, falling back to the
    material's average_rate if no supplier is linked at all), groups
    the cart by chosen supplier, and reports genuine savings -
    cheapest total vs. what the same cart would cost if every item
    were bought at its most expensive available option. Never
    invents a price or a saving; a material with only one price
    source contributes zero to the savings figure, honestly."""
    supplier_groups = {}  # supplier_name -> [{material, quantity, rate, amount}]
    unresolved = []
    total_cheapest = Decimal("0")
    total_worst_case = Decimal("0")

    # Batch both lookups once instead of querying Material and
    # SupplierMaterial separately inside the loop for every cart item -
    # a cart with N items previously ran up to 2N+ queries (plus a
    # further N for link.supplier if not eager-loaded); this runs 2
    # fixed queries regardless of cart size.
    material_ids = [item.material_id for item in cart_items]
    materials_by_id = {
        m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()
    } if material_ids else {}
    links_by_material_id = {}
    if material_ids:
        all_links = (
            db.query(SupplierMaterial)
            .options(selectinload(SupplierMaterial.supplier))
            .filter(SupplierMaterial.material_id.in_(material_ids), SupplierMaterial.supplier_price.isnot(None))
            .all()
        )
        for link in all_links:
            links_by_material_id.setdefault(link.material_id, []).append(link)

    for item in cart_items:
        material = materials_by_id.get(item.material_id)
        if not material:
            continue
        links = links_by_material_id.get(item.material_id, [])
        qty = Decimal(str(item.quantity))

        if links:
            prices = [(link.supplier.name if link.supplier else "Unknown Supplier", link.supplier_price) for link in links]
            cheapest_name, cheapest_price = min(prices, key=lambda p: p[1])
            worst_price = max(p[1] for p in prices)
        elif material.average_rate:
            cheapest_name, cheapest_price = "Primary Supplier", material.average_rate
            worst_price = material.average_rate
        else:
            unresolved.append(material.name)
            continue

        amount = (cheapest_price * qty).quantize(Decimal("0.01"))
        total_cheapest += amount
        total_worst_case += (worst_price * qty).quantize(Decimal("0.01"))
        supplier_groups.setdefault(cheapest_name, []).append(
            {"material": material.name, "quantity": float(qty), "unit": material.unit, "amount": float(amount)}
        )

    if not supplier_groups:
        return "I couldn't find pricing for any of the materials in your cart yet.", [], []

    lines = [f"Estimated purchase value: Rs {float(total_cheapest):,.2f}, grouped by the cheapest available supplier per item."]
    savings = total_worst_case - total_cheapest
    if savings > 0:
        lines.append(f"Choosing the best price for each item saves Rs {float(savings):,.2f} compared to the most expensive option for each.")
    for supplier_name, items in supplier_groups.items():
        item_desc = ", ".join(f"{i['quantity']:g} {i['unit']} {i['material']}" for i in items)
        supplier_total = sum(i["amount"] for i in items)
        lines.append(f"{supplier_name}: {item_desc} - Rs {supplier_total:,.2f}.")
    if unresolved:
        lines.append(f"No pricing found for: {', '.join(unresolved)} - add a supplier price for these to include them.")

    return " ".join(lines), [], []
