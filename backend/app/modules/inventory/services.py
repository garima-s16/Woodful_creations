"""Chatbot inventory-domain query/action handlers - material stock
questions, low-stock/replenishment/usage summaries, purchases, and
the "add material" command parser (English and Hindi phrasing). Split
out of the former monolithic chat_service.py, which mixed every
domain's deterministic chat handlers together in one 55-method,
2250-line class. The dispatch table itself (process_message/_dispatch)
stays in chat_service.py - see its own docstring for why."""
import re
import difflib
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase, Supplier
from app.modules.operations.models import Issue
from app.modules.ai.contracts import ProposedAction
from app.modules.inventory.imports import extract_thickness, interpret_material_name
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload
from app.modules.procurement.models import Purchase
from app.modules.inventory.models import Location, StockTransfer, StockAdjustment, StockLedgerEntry
from app.modules.procurement.models import SupplierMaterial
from app.modules.operations.schemas import IssueCreate
from app.modules.inventory.schemas import StockTransferCreate, StockAdjustmentCreate
from app.platform.ids import generate_unique_code, generate_business_id
from app.modules.sales.models import Order, OrderItem
from app.modules.catalog.models import ProductMaterial


ADD_MATERIAL_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                              "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def parse_add_material_command(m: str) -> Optional[dict]:
    """Parses "add N <material description> [to <destination>]" style
    messages - "add one hdhmr sheet of 6mm in list", "add 5 hdhmr 18mm
    sheets to my purchase cart". Returns None if the message doesn't
    start with "add" at all (not this kind of command). Verified against
    every example phrase in the product brief before being wired into
    the chat service, not assumed correct from the regex alone."""
    if not m.startswith("add "):
        return None
    rest = m[4:]

    # Critical guard: "add" is a generic verb this parser used to claim
    # for ANY object, including ones that are a completely different
    # entity type - "add client Ramesh 9812345670" was silently parsed
    # as a material named "client Ramesh 9812345670" and proposed for
    # creation, because nothing here ever checked what was actually
    # being added. Bail out immediately for a message that's clearly
    # about client/customer, supplier/vendor, or another entity this
    # parser has no business touching - it falls through to that
    # entity's own handler (or, for client - which has no chat-write
    # path at all by design - to a normal conversational response)
    # instead of being silently reinterpreted as a material.
    other_entity_words = (
        "client", "customer", "supplier", "vendor", "employee", "staff",
        "estimate", "quotation", "order", "payment", "invoice",
    )
    filler_words = {"a", "an", "the", "new", "another"}
    words = [w.lower().rstrip(".,!?") for w in rest.strip().split()]
    # Skip leading filler ("add A NEW client..." must still be caught,
    # not just "add client...") - checked within the first few real
    # words, not the whole message, so a material description that
    # merely mentions "order" or "supplier" somewhere later isn't
    # wrongly blocked.
    significant_leading_words = [w for w in words if w not in filler_words][:2]
    if any(w in other_entity_words for w in significant_leading_words):
        return None

    qty_match = re.match(r"(\d+(?:\.\d+)?)\s+(.*)", rest)
    if qty_match:
        quantity = float(qty_match.group(1))
        rest = qty_match.group(2)
    else:
        word_match = re.match(r"(" + "|".join(ADD_MATERIAL_WORD_NUMBERS.keys()) + r")\s+(.*)", rest)
        if word_match:
            quantity = ADD_MATERIAL_WORD_NUMBERS[word_match.group(1)]
            rest = word_match.group(2)
        else:
            quantity = 1  # "add plywood" with no number stated - assume 1

    # "add 4 sheets to Ishu's project" is a different action (issue to a
    # project) this parser doesn't resolve - must not fall through to
    # material creation with the project reference leaking into the name.
    project_match = re.search(r"to\s+([a-z]+)'s\s+project", rest)
    if project_match:
        return {"destination": "project_issue", "project_name": project_match.group(1), "quantity": quantity}

    destination = "material_list"  # default when no destination is stated - matches the brief's own worked example
    dest_patterns = [
        (r"\s+to\s+(?:my\s+)?purchase\s+cart\.?$", "cart"),
        (r"\s+to\s+(?:my\s+)?cart\.?$", "cart"),
        (r"\s+to\s+(?:my\s+)?purchase\s+list\.?$", "cart"),
        (r"\s+to\s+(?:my\s+)?material\s+list\.?$", "material_list"),
        (r"\s+in\s+list\.?$", "material_list"),
        (r"\s+to\s+stock\.?$", "stock"),
    ]
    for pattern, dest in dest_patterns:
        if re.search(pattern, rest):
            destination = dest
            rest = re.sub(pattern, "", rest)
            break

    description = rest.strip().rstrip(".")
    description = re.sub(r"\s+sheets?\s+of\s+", " ", description)
    description = re.sub(r"\s+(sheets?|pairs?|pcs?|pieces?)$", "", description)
    unit_match = re.search(r"\b(sheets?|pairs?|pcs?|pieces?)\b", rest)
    unit = unit_match.group(1).rstrip("s") if unit_match else None
    description = description.strip()
    # "add 4 sheet" - no real material name given, just the bare unit
    # word left over. The suffix-strip above only handles a unit word
    # AFTER a real name ("hdhmr sheets" -> "hdhmr"); it can't catch the
    # case where the unit word IS the entire remaining text, since that
    # pattern requires a leading space that isn't there. Must not
    # confidently propose a material literally named "sheet" - clearing
    # it here lets the existing "I didn't catch what material" check
    # downstream correctly ask for clarification instead.
    if re.fullmatch(r"(sheets?|pairs?|pcs?|pieces?)", description):
        description = ""

    return {"quantity": quantity, "description": description, "unit": unit, "destination": destination}


def extract_material_query(m: str):
    """"How much HDHMR 18mm do we have", "which supplier supplied
    plywood" - extracts (query_type, material_text) so the assistant
    answers about the SPECIFIC named material, not a generic inventory
    summary. Returns None for a deictic reference ("this material",
    "the material") - that's page-context dependent and handled by
    _answer_from_context instead, not a literal name to search for.
    Tested against every example phrase in the product brief before
    being wired into the chat service."""
    patterns = [
        (r"how much (.+?) do we have", "stock"),
        (r"current stock of (.+?)$", "stock"),
        (r"stock of (.+?)$", "stock"),
        (r"which supplier (?:supplied|supplies) (?:this |the )?(.+?)$", "supplier"),
        (r"who (?:supplied|supplies) (?:this |the )?(.+?)$", "supplier"),
        (r"^(.+?)\s+kitn[ae]\s+(?:h|hai|hain|bacha|bache|pada|pade)\b", "stock"),
        (r"^stock\s+(.+?)$", "stock"),
    ]
    # Only for the new bare "stock X" pattern - "stock dashboard"/"stock
    # report" must fall through to the general stock summary, not
    # confidently claim it couldn't find a material named "dashboard".
    non_material_words = {"dashboard", "report", "summary", "levels", "status", "overview", "page"}
    for pattern, qtype in patterns:
        match = re.search(pattern, m)
        if match:
            text = match.group(1).strip().rstrip("?.")
            if text in ("material", "this material", "the material", "it") or text in non_material_words:
                return None
            return qtype, text
    return None


def _route_material_query(m: str, db: Session):
    """Handles "how much X do we have" and "which supplier supplied
    X" - resolves X against the real Material table (same
    significant-word ILIKE matching pattern as
    _route_material_action), not a generic inventory summary."""
    parsed = extract_material_query(m)
    if not parsed:
        return None
    query_type, material_text = parsed

    significant_words = [w for w in material_text.split() if len(w) > 2]
    if not significant_words:
        return None
    query = db.query(Material)
    for word in significant_words:
        like = f"%{word}%"
        query = query.filter(or_(
            Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
        ))
    material = query.first()
    if not material:
        # Exact substring search found nothing - try a typo-tolerant
        # fallback before giving up. "hdhr" is genuinely not a
        # substring of "HDHMR" (a letter is missing), which ILIKE
        # alone can never bridge - this is the specific, confirmed
        # gap from the brief's own "6mm hdhr kitna h" example.
        all_names = [n for (n,) in db.query(Material.name).all()]
        close = difflib.get_close_matches(material_text, [n.lower() for n in all_names], n=1, cutoff=0.6)
        if close:
            material = db.query(Material).filter(Material.name.ilike(close[0])).first()
    if not material:
        return f"I couldn't find a material matching \"{material_text}\".", [], []

    if query_type == "stock":
        return (
            f"{material.name}: {material.current_stock} {material.unit} in stock "
            f"({material.stock_status}, reorder level {material.minimum_stock} {material.unit}).",
            [], [{
                "type": "Material", "label": material.name,
                "sublabel": f"{material.current_stock} {material.unit} - {material.stock_status}",
                "path": f"/materials/{material.id}",
            }],
        )

    # query_type == "supplier"
    if material.primary_supplier:
        return (
            f"{material.name} is supplied by {material.primary_supplier.name}"
            + (f" ({material.primary_supplier.contact_person})" if material.primary_supplier.contact_person else "") + ".",
            [], [{
                "type": "Supplier", "label": material.primary_supplier.name,
                "sublabel": f"Supplies {material.name}", "path": f"/suppliers/{material.primary_supplier.id}",
            }],
        )
    return f"{material.name} has no primary supplier on record.", [], []


def _stock_summary(db: Session, user_role: str = "user"):
    material_count = db.query(func.count(Material.id)).scalar() or 0
    if user_role in ("master",):
        total_value = float(db.query(func.coalesce(func.sum(Material.stock_value), 0)).scalar() or 0)
        return (
            f"You have {material_count} materials tracked, worth Rs {total_value:,.2f} in current stock.",
            ["Check low stock", "Show pending orders"], [],
        )
    return (
        f"You have {material_count} materials tracked.",
        ["Check low stock", "Show out of stock"], [],
    )


def _at_risk_orders(db: Session):
    """Which open orders currently have a real, current material
    shortage - Family 130 section 15's "which materials will run
    short" target question, framed the more actionable way: not just
    which material, but which customer order it actually threatens."""
    at_risk = StockService.calculate_at_risk_orders(db)
    if not at_risk:
        return "No open orders are currently at risk of a material shortage.", [], []
    records = []
    for row in at_risk[:10]:
        top_material = row["materials"][0]
        extra = f" (+{row['total_shortage_lines'] - 1} more material)" if row["total_shortage_lines"] > 1 else ""
        records.append({
            "type": "Order", "label": f"{row['order_code']} - {row['client_name'] or 'Client'}",
            "sublabel": f"Short on {top_material['material_name']}{extra}",
            "path": f"/orders/{row['order_id']}",
            "actions": [{"label": "View Order", "path": f"/orders/{row['order_id']}"}],
        })
    return f"{len(at_risk)} order(s) are at risk of a material shortage.", [], records


def _low_stock(db: Session, user_role: str):
    low = db.query(Material).filter(Material.current_stock <= Material.minimum_stock).all()
    if not low:
        return "All materials are above minimum stock levels.", [], []
    is_privileged = user_role in ("master",)
    records = []
    for m in low[:10]:
        actions = [{"label": "View Material", "path": f"/materials/{m.id}"}]
        if is_privileged:
            actions.append({"label": "View Purchase History", "path": f"/materials/{m.id}?tab=Purchases"})
        records.append({
            "type": "Material", "label": m.name,
            "sublabel": f"{m.current_stock}/{m.minimum_stock} {m.unit}",
            "path": f"/materials/{m.id}",
            "actions": actions,
        })
    return f"{len(low)} materials at or below minimum stock.", [], records


def _replenishment_requirements(db: Session, user_role: str):
    """"what needs reordering" - the shortfall shown is honest
    arithmetic on two real stored values (minimum_stock minus
    current_stock), never a fabricated target level - this app has
    no "ideal stock" field to invent one from, and the AI must not
    pretend otherwise."""
    materials = db.query(Material).filter(Material.current_stock <= Material.minimum_stock).all()
    if not materials:
        return "Nothing currently needs reordering - all materials are above their minimum stock level.", [], []
    records = []
    for m in materials[:10]:
        shortfall = (m.minimum_stock or 0) - (m.current_stock or 0)
        sublabel = f"Need {shortfall} {m.unit} to reach minimum stock"
        if m.primary_supplier:
            sublabel += f" - usually supplied by {m.primary_supplier.name}"
        records.append({
            "type": "Material", "label": m.name, "sublabel": sublabel, "path": f"/materials/{m.id}",
        })
    return f"{len(materials)} material(s) need reordering to reach their minimum stock level.", [], records


def _material_usage_summary(m: str, db: Session):
    """"hdhmr usage summary" - a genuine summary of real Issue
    records for this material, not a fabricated narrative.
    total_issued is confirmed kept in sync by stock_service.py on
    every issue - but it's gross issued, not net of any later
    returns, so it's labeled that way rather than implied to be
    "net consumed"."""
    patterns = [
        r"summarize\s+(.+?)\s+usage",
        r"usage\s+(?:of|for)\s+(.+?)$",
        r"(.+?)\s+usage(?:\s+summary)?\b",
    ]
    material_text = None
    for pattern in patterns:
        match = re.search(pattern, m)
        if match:
            material_text = match.group(1).strip()
            break
    if not material_text:
        return None

    significant_words = [w for w in material_text.split() if len(w) > 2]
    if not significant_words:
        return None
    query = db.query(Material)
    for word in significant_words:
        like = f"%{word}%"
        query = query.filter(or_(
            Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
        ))
    material = query.first()
    if not material:
        all_names = [n for (n,) in db.query(Material.name).all()]
        close = difflib.get_close_matches(material_text, [n.lower() for n in all_names], n=1, cutoff=0.6)
        if close:
            material = db.query(Material).filter(Material.name.ilike(close[0])).first()
    if not material:
        return None

    # Defect repair (F138 P1): previously loaded every Issue row ever
    # recorded against this material (a real, only-growing
    # transactional table) just to compute a count and a per-order
    # breakdown - a heavily-issued material could mean a very large
    # fetch for a one-line chat summary. The count and per-order totals
    # are now computed in SQL (count/group-by-sum), not a Python loop
    # over every fetched row.
    issue_count = db.query(func.count(Issue.id)).filter(Issue.material_id == material.id).scalar() or 0
    if not issue_count:
        return f"{material.name} has never been issued.", [], []

    order_totals = (
        db.query(Order.order_code, func.sum(Issue.quantity_issued))
        .select_from(Issue).outerjoin(Order, Issue.order_id == Order.id)
        .filter(Issue.material_id == material.id)
        .group_by(Order.order_code)
        .all()
    )
    by_order = {(code or "No project"): float(total or 0) for code, total in order_totals}
    top_orders = sorted(by_order.items(), key=lambda kv: kv[1], reverse=True)[:3]
    top_summary = ", ".join(f"{code}: {qty:g} {material.unit}" for code, qty in top_orders)

    lines = [
        f"{material.name}: {float(material.total_issued or 0):g} {material.unit} issued in total across {issue_count} issue(s).",
        f"Top consumers - {top_summary}.",
    ]
    records = [{
        "type": "Material", "label": material.name, "sublabel": f"{material.current_stock} {material.unit} in stock",
        "path": f"/materials/{material.id}",
    }]
    return " ".join(lines), [], records


def _out_of_stock(db: Session, user_role: str):
    """Distinct from _low_stock - specifically materials at zero,
    not just at-or-below their reorder level."""
    zero = db.query(Material).filter(Material.current_stock <= 0).all()
    if not zero:
        return "No materials are currently out of stock.", [], []
    is_privileged = user_role in ("master",)
    records = []
    for m in zero[:10]:
        actions = [{"label": "View Material", "path": f"/materials/{m.id}"}]
        if is_privileged:
            actions.append({"label": "View Purchase History", "path": f"/materials/{m.id}?tab=Purchases"})
        records.append({
            "type": "Material", "label": m.name,
            "sublabel": f"0 {m.unit} - reorder level {m.minimum_stock} {m.unit}",
            "path": f"/materials/{m.id}",
            "actions": actions,
        })
    return f"{len(zero)} materials are completely out of stock.", [], records


def _recent_purchases(db: Session):
    purchases = db.query(Purchase).order_by(Purchase.date.desc()).limit(10).all()
    if not purchases:
        return "No purchases recorded yet.", [], []
    records = [{
        "type": "Purchase", "label": p.material.name if p.material else "Material",
        "sublabel": f"{p.quantity} {p.unit} from {p.supplier.name if p.supplier else 'supplier'} on {p.date.strftime('%d %b %Y')}",
        "path": "/purchases",
    } for p in purchases]
    return f"Most recent {len(purchases)} purchases:", [], records


def _pending_purchases(db: Session):
    # Defect repair (F138 P1): previously loaded every pending-payment
    # Purchase (a real, only-growing transactional table) into memory
    # just to report a count and show 10 - now counts in SQL and pulls
    # only the 10 rows actually shown, matching _recent_purchases'
    # own limit(10) idiom above.
    total = db.query(func.count(Purchase.id)).filter(Purchase.payment_status != "Paid").scalar() or 0
    if not total:
        return "No purchases are currently pending payment to suppliers.", [], []
    purchases = (
        db.query(Purchase).filter(Purchase.payment_status != "Paid")
        .order_by(Purchase.date.desc()).limit(10).all()
    )
    records = [{
        "type": "Purchase", "label": p.purchase_code,
        "sublabel": f"{p.supplier.name if p.supplier else 'Supplier'} - {p.payment_status}",
        "path": "/purchases",
    } for p in purchases]
    return f"{total} purchases are pending payment to suppliers.", [], records


def _route_material_action(m: str, db: Session, user_role: str):
    """Handles "add N <material> to my material list/cart" style
    commands. Searches across name,
    thickness_size, AND brand_grade for each significant word - a
    real material is frequently "HDHMR Board" with thickness_size
    "6mm" as a separate column, not "HDHMR 6mm" as one name string,
    so a name-only search would miss real matches."""
    parsed = parse_add_material_command(m)
    if not parsed:
        return None

    if parsed["destination"] == "project_issue":
        return (
            f"I can't yet issue material to a project through chat - please use the Issues "
            f"page to record what's being issued to {parsed['project_name'].title()}'s project.",
            [], None, None, [],
        )

    if parsed["destination"] == "stock":
        return (
            "I can't yet receive stock directly through chat - stock is recorded by creating "
            "a purchase on the Purchases page, which updates inventory automatically.",
            [], None, None, [],
        )

    description = parsed["description"]
    if not description:
        return (
            "I didn't catch what material you'd like to add. Try something like "
            "\"add 5 HDHMR 18mm sheets to my material list\".",
            [], None, None, [],
        )

    significant_words = [w for w in description.split() if len(w) > 2]
    query = db.query(Material)
    for word in significant_words:
        like = f"%{word}%"
        query = query.filter(or_(
            Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
        ))
    existing = query.first()

    if parsed["destination"] == "cart":
        if not existing:
            return (
                f"I couldn't find an existing material matching \"{description}\". "
                f"Would you like me to create it in Material Master first?",
                [], None, None, [],
            )
        proposal = ProposedAction(
            action_type="add_to_cart",
            summary=f"Add {parsed['quantity']:g} {existing.unit} of {existing.name} to your purchase cart",
            payload={
                "materialId": existing.id, "name": existing.name, "unit": existing.unit,
                # Same redaction the personal-cart REST endpoint applies
                # (_serialize_cart_items) - a material's rate is
                # master-only, so the chatbot's proposed action must not
                # hand a non-master user that figure just because it
                # takes a different path to the same cart feature.
                "rate": float(existing.average_rate) if user_role in ("master",) else None,
                "quantity": parsed["quantity"],
                "currentStock": existing.current_stock,
            },
        )
        return (
            f"I've prepared adding {parsed['quantity']:g} {existing.unit} of {existing.name} to your cart.",
            [], proposal, None, [],
        )

    # destination == "material_list"
    if existing:
        return (
            f"{existing.name} already exists in Material Master - current stock is "
            f"{existing.current_stock} {existing.unit}. Nothing to create.",
            [], None, None, [{
                "type": "Material", "label": existing.name,
                "sublabel": f"{existing.current_stock} {existing.unit} in stock",
                "path": f"/materials/{existing.id}",
            }],
        )

    if user_role not in ("master",):
        return "Creating materials requires a master account.", [], None, None, []

    # A reasonable guess for the new material - never created
    # without explicit confirmation, matching the brief's exact UX.
    # Python's plain .title() mangles unit suffixes ("6mm" ->
    # "6Mm"), so capitalize word-by-word instead, leaving any token
    # that's not purely alphabetic untouched.
    guessed_name = " ".join(w.capitalize() if w.isalpha() else w for w in description.split())
    thickness = extract_thickness(description)
    unit = (parsed["unit"] or "sheet").title() + "s"

    # Same interpretation logic the material creation form's
    # "intelligent defaults" uses - only applied here (subcategory
    # pre-filled on the proposal) when it's actually confident;
    # otherwise the material is proposed uncategorized, same as
    # before, and the user assigns a category themselves.
    interpretation = interpret_material_name(db, description)
    payload = {"name": guessed_name, "unit": unit, "thickness_size": thickness, "opening_stock": 0, "minimum_stock": 0}
    summary_extra = ""
    if interpretation["confidence"] != "none":
        payload["subcategory_id"] = interpretation["subcategory_id"]
        summary_extra = f", category: {interpretation['subcategory_name']}"
    proposal = ProposedAction(
        action_type="create_material",
        summary=f"Create \"{guessed_name}\"" + (f" ({thickness})" if thickness else "") + f", unit: {unit}" + summary_extra,
        payload=payload,
    )
    lines = ["I couldn't find an exact matching material. I interpreted this as:", guessed_name]
    if thickness:
        lines.append(f"Thickness: {thickness}.")
    if interpretation["confidence"] != "none":
        lines.append(f"Category: {interpretation['subcategory_name']}.")
    lines.append(f"Unit: {unit}. Create this material?")
    return " ".join(lines), [], proposal, None, []


def _summarize_supplier(m: str, db: Session, user_role: str):
    """"summarize supplier X" - a genuine summary derived from this
    supplier's real purchase history, not a fabricated narrative.
    On-time-vs-delayed ratio is computed only from purchases that
    actually have an expected_delivery_date set - a purchase never
    given a delivery expectation contributes to neither count."""
    if not any(w in m for w in ["summarize supplier", "supplier summary"]):
        return None
    match = re.search(r"(.+?)\s+supplier\s+summary", m) or re.search(r"summarize supplier\s+(.+?)$", m)
    if not match:
        return None
    name_text = match.group(1).strip()
    if name_text in ("", "summary"):
        return None

    suppliers = db.query(Supplier).filter(Supplier.name.ilike(f"%{name_text}%")).all()
    if not suppliers:
        all_names = [n for (n,) in db.query(Supplier.name).all()]
        close = difflib.get_close_matches(name_text, [n.lower() for n in all_names], n=1, cutoff=0.6)
        if close:
            suppliers = db.query(Supplier).filter(Supplier.name.ilike(close[0])).all()
    if len(suppliers) != 1:
        return None
    supplier = suppliers[0]

    # Defect repair (F138 P1): previously loaded every Purchase this
    # supplier has ever had (a real, only-growing transactional table)
    # into memory just to derive counts/sums - a supplier active for
    # years could mean thousands of rows fetched for a one-line chat
    # summary. Every figure below is now a bulk SQL count/sum, not a
    # Python loop over fetched rows.
    total_count = db.query(func.count(Purchase.id)).filter(Purchase.supplier_id == supplier.id).scalar() or 0
    if not total_count:
        return f"{supplier.name}: no purchases on record yet.", [], [{
            "type": "Supplier", "label": supplier.name, "sublabel": supplier.category or "",
            "path": f"/suppliers/{supplier.id}",
        }]

    with_expected_count = db.query(func.count(Purchase.id)).filter(
        Purchase.supplier_id == supplier.id, Purchase.expected_delivery_date.isnot(None),
    ).scalar() or 0
    on_time_count = db.query(func.count(Purchase.id)).filter(
        Purchase.supplier_id == supplier.id, Purchase.expected_delivery_date.isnot(None),
        Purchase.receipt_status == "Received",
    ).scalar() or 0
    lines = [f"{supplier.name}: {total_count} purchase(s) on record."]
    if with_expected_count:
        lines.append(f"{on_time_count}/{with_expected_count} with a tracked delivery date were fully received.")
    if user_role in ("master",):
        total_value = float(
            db.query(func.coalesce(func.sum(Purchase.invoice_total), 0))
            .filter(Purchase.supplier_id == supplier.id).scalar() or 0
        )
        lines.append(f"Total purchase value Rs {total_value:,.2f}.")

    records = [{
        "type": "Supplier", "label": supplier.name, "sublabel": f"{total_count} purchases", "path": f"/suppliers/{supplier.id}",
    }]
    return " ".join(lines), [], records


HINDI_ADD_VERBS = ["add kr do", "add kar do", "add karo", "add kro", "daal do", "daal dena", "daal dijiye"]


HINDI_FILLER_WORDS = {"ki", "ka", "ke", "wali", "wala", "sheet", "sheets", "add"}


def _route_ambiguous_hindi_add(m: str, db: Session):
    """"4 sheet add kr do 12mm ki" - Hindi/Hinglish often places the
    verb mid-sentence rather than "add X" at the start, a genuinely
    different shape from parse_add_material_command's English-order
    parsing. When the message has a quantity, "sheet", and a Hindi
    add-verb, but no word in it actually matches a real material
    (just a bare spec like "12mm" with nothing else), this asks
    which material rather than ever proposing to create or add
    anything - never a confident guess from a thickness number
    alone. Returns None (not this ambiguous shape, or a real
    material WAS found) so the message falls through normally."""
    has_qty = bool(re.search(r"\b\d+(?:\.\d+)?\b", m))
    has_sheet = bool(re.search(r"\bsheets?\b", m))
    has_hindi_verb = any(v in m for v in HINDI_ADD_VERBS)
    if not (has_qty and has_sheet and has_hindi_verb):
        return None

    words = [w.strip(".,?!") for w in m.split()]
    candidate_words = [w for w in words if len(w) > 2 and w not in HINDI_FILLER_WORDS
                        and not re.fullmatch(r"\d+(?:\.\d+)?", w)]
    found_real_material = False
    for word in candidate_words:
        like = f"%{word}%"
        if db.query(Material).filter(or_(
            Material.name.ilike(like), Material.thickness_size.ilike(like), Material.brand_grade.ilike(like),
        )).first():
            found_real_material = True
            break

    if found_real_material:
        return None  # a real material name is present - let this fall through normally
    return "Konsi wali sheet? Please tell me the material - e.g. plywood, HDHMR, or laminate.", [], None, None, []


# --- stock_service.py (StockService: purchase/issue/transfer/adjustment,
# stock ledger, material-requirement/shortage calculation) ---
"""Keeps Material.current_stock / total_purchased / total_issued consistent
with the Purchase and Issue registers. All writes go through here rather
than routes touching Material directly, so stock can never drift from its
transaction history."""

class StockService:

    @staticmethod
    def _apply_stock_receipt(db: Session, material: Material, quantity: Decimal, rate: Decimal, supplier_id: int = None, material_id_for_link: int = None, reference_id: int = None, location_id: int = None):
        """The actual stock-increase math, shared by record_purchase
        (when goods are received immediately, the default and existing
        behavior) and mark_purchase_received (when a purchase was
        recorded as Ordered and goods arrive later) - one implementation,
        so the weighted-average-rate calculation can't drift between the
        two call sites. Also writes the permanent ledger entry for this
        receipt - reference_id links it back to the actual Purchase row.

        location_id records WHERE the stock landed (falls back to the
        material's own primary location_id when not given, so unlocated
        materials/receipts behave exactly as before). If the material had
        no primary location yet, the first receipt's location becomes it -
        a material's location_id then stays a genuine "primary/most
        recent" location for the existing single-location consumers,
        while the ledger keeps the full per-location breakdown."""
        resolved_location_id = location_id or material.location_id
        if resolved_location_id and not material.location_id:
            loc = db.query(Location).filter(Location.id == resolved_location_id).first()
            if loc:
                material.location_id = loc.id
                material.location = loc.full_path

        material.total_purchased = (material.total_purchased or 0) + quantity
        material.current_stock = (material.current_stock or 0) + quantity
        prior_value = Decimal(str(material.average_rate or 0)) * Decimal(str((material.current_stock or 0) - quantity))
        new_value = prior_value + (quantity * rate)
        if material.current_stock:
            material.average_rate = (new_value / Decimal(str(material.current_stock))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        db.add(material)
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Receipt", quantity_delta=quantity,
            balance_after=material.current_stock, reference_type="purchase", reference_id=reference_id,
            location_id=resolved_location_id,
        ))

        if supplier_id and material_id_for_link:
            link = db.query(SupplierMaterial).filter(
                SupplierMaterial.supplier_id == supplier_id, SupplierMaterial.material_id == material_id_for_link
            ).first()
            if link:
                link.last_purchase_price = rate
                db.add(link)

    @staticmethod
    def record_issue(db: Session, data: IssueCreate) -> Issue:
        material = db.query(Material).filter(Material.id == data.material_id).with_for_update().first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        # Defect repair (F138 P13.1): Issue.unit is a separate, free-text
        # field from Material.unit, and this quantity is subtracted
        # straight from Material.current_stock/total_issued with no
        # conversion step anywhere in the codebase - same gap, same fix,
        # as ProcurementService.record_purchase's unit check. With no
        # unit-conversion model, a mismatched unit must be rejected, not
        # silently subtracted as if it were the material's own unit.
        if data.unit.strip().lower() != (material.unit or "").strip().lower():
            raise HTTPException(
                status_code=400,
                detail=f"Unit mismatch: this issue is recorded in '{data.unit}' but {material.name} "
                       f"is tracked in '{material.unit}'. Record the issue in the material's own unit.",
            )

        issue_code = generate_unique_code(db, Issue, "issue_code", "ISS-")

        if data.quantity_issued > (material.current_stock or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot issue {data.quantity_issued} {data.unit} - only {material.current_stock} in stock",
            )

        resolved_location_id = data.location_id or material.location_id
        if data.location_id:
            # A location was explicitly requested - it must actually have
            # enough stock, not just the material overall (a material can
            # be split across racks; issuing from an empty rack while
            # another rack is full must be rejected even though the
            # material-wide total would cover it).
            location_balance = StockService._location_balance(db, material.id, resolved_location_id)
            if data.quantity_issued > location_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot issue {data.quantity_issued} {data.unit} from that location - only {location_balance} available there",
                )

        issue = Issue(
            issue_code=issue_code, date=data.date, order_id=data.order_id,
            material_id=data.material_id, quantity_issued=data.quantity_issued, unit=data.unit,
            issued_to=data.issued_to, department=data.department, purpose=data.purpose,
            approved_by=data.approved_by, remarks=data.remarks, location_id=data.location_id,
            rate_at_issue=material.average_rate,
        )
        db.add(issue)
        db.flush()  # assigns issue.id without committing, needed as the ledger entry's reference_id below

        material.total_issued = (material.total_issued or 0) + data.quantity_issued
        material.current_stock = (material.current_stock or 0) - data.quantity_issued
        db.add(material)
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Issue", quantity_delta=-data.quantity_issued,
            balance_after=material.current_stock, reference_type="issue", reference_id=issue.id,
            location_id=resolved_location_id,
        ))

        db.commit()
        db.refresh(issue)
        return issue

    @staticmethod
    def record_transfer(db: Session, data: StockTransferCreate) -> StockTransfer:
        """Logs a location move and updates Material's single
        location_id/location fields - not a second stock-by-location
        number (see the model's own docstring for why)."""
        material = db.query(Material).filter(Material.id == data.material_id).with_for_update().first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        to_location = db.query(Location).filter(Location.id == data.to_location_id).first()
        if not to_location:
            raise HTTPException(status_code=404, detail="Destination location not found")
        if data.quantity <= 0:
            raise HTTPException(status_code=400, detail="Transfer quantity must be positive")
        if data.quantity > (material.current_stock or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transfer {data.quantity} {material.unit} - only {material.current_stock} in stock.",
            )

        from_location_id = data.from_location_id or material.location_id
        if from_location_id == data.to_location_id:
            # A transfer has no business meaning when the source and
            # destination are the same location - net stock movement is
            # zero, but recording it anyway would still create two
            # offsetting ledger rows that look like real activity.
            raise HTTPException(
                status_code=400, detail="Source and destination location cannot be the same.",
            )
        if from_location_id:
            from_balance = StockService._location_balance(db, material.id, from_location_id)
            if data.quantity > from_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot transfer {data.quantity} {material.unit} - only {from_balance} at the source location.",
                )

        transfer = StockTransfer(
            material_id=data.material_id, quantity=data.quantity, from_location_id=from_location_id,
            to_location_id=data.to_location_id, transferred_by=data.transferred_by, remarks=data.remarks,
            business_id=generate_business_id(db),
        )
        db.add(transfer)
        db.flush()  # assigns transfer.id, needed as the ledger entries' reference_id below

        # Total material-wide stock never changes on a transfer - only
        # WHERE it sits. Two ledger entries whose quantity_delta sums to
        # zero (a decrease at from_location, an increase at to_location)
        # keep verify_stock_matches_ledger's material-wide reconciliation
        # untouched while still letting per-location balances be derived
        # from the ledger, same as receipts/issues/adjustments.
        # Always write the "from" entry, even when from_location_id is
        # None (a material with no location history yet) - its balance
        # must still be debited from wherever the ledger currently
        # attributes that stock (the "Unassigned" bucket), or the
        # per-location total would stop summing to the material-wide total.
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Transfer", quantity_delta=-data.quantity,
            balance_after=material.current_stock, reference_type="stock_transfer", reference_id=transfer.id,
            location_id=from_location_id, remarks=f"Transferred to {to_location.full_path}",
        ))
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Transfer", quantity_delta=data.quantity,
            balance_after=material.current_stock, reference_type="stock_transfer", reference_id=transfer.id,
            location_id=data.to_location_id, remarks=f"Transferred from {from_location_id or 'unassigned'}",
        ))

        # material.location_id/location keep meaning "primary/most recent
        # location" for the existing single-location consumers (dashboard,
        # PDF, chatbot) - unchanged behavior, now backed by real
        # per-location detail in the ledger for anything that wants it.
        material.location_id = data.to_location_id
        material.location = to_location.full_path
        db.add(material)

        db.commit()
        db.refresh(transfer)
        return transfer

    @staticmethod
    def record_adjustment(db: Session, data: StockAdjustmentCreate) -> StockAdjustment:
        """Every change to current_stock outside a purchase/issue must
        go through here - never a silent direct edit. Records the exact
        before/after so the adjustment is fully auditable, and rejects
        anything that would push stock negative. "Return from Issue" is
        validated against the actual originating Issue - the returned
        quantity can never exceed what was genuinely issued minus what's
        already been returned against it, so a return can't become a
        disguised arbitrary quantity increase."""
        material = db.query(Material).filter(Material.id == data.material_id).with_for_update().first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        if data.quantity_delta == 0:
            raise HTTPException(status_code=400, detail="Adjustment quantity cannot be zero")

        if data.adjustment_type == "Return from Issue":
            if not data.related_issue_id:
                raise HTTPException(status_code=400, detail="A return must reference the issue it's returning material against.")
            if data.quantity_delta <= 0:
                raise HTTPException(status_code=400, detail="A return must increase stock (a positive quantity).")
            issue = db.query(Issue).filter(Issue.id == data.related_issue_id).first()
            if not issue:
                raise HTTPException(status_code=404, detail="The referenced issue was not found.")
            if issue.material_id != data.material_id:
                raise HTTPException(status_code=400, detail="The referenced issue is for a different material.")
            already_returned = db.query(StockAdjustment).filter(
                StockAdjustment.related_issue_id == data.related_issue_id,
            ).with_entities(StockAdjustment.quantity_delta).all()
            already_returned_total = sum((r[0] for r in already_returned), Decimal("0"))
            remaining = (issue.quantity_issued or Decimal("0")) - already_returned_total
            if data.quantity_delta > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot return {data.quantity_delta} {material.unit} - only {remaining} {material.unit} "
                           f"from this issue remains un-returned.",
                )

        stock_before = material.current_stock or 0
        stock_after = stock_before + data.quantity_delta
        if stock_after < 0:
            raise HTTPException(
                status_code=400,
                detail=f"This adjustment would take stock negative ({stock_before} {data.quantity_delta:+} = {stock_after}).",
            )

        resolved_location_id = data.location_id or material.location_id
        if data.location_id and data.quantity_delta < 0:
            # A decrease at a specific location must not take that
            # location's own balance negative, even if the material-wide
            # total has room (stock at other locations doesn't help here).
            location_balance = StockService._location_balance(db, material.id, resolved_location_id)
            if -data.quantity_delta > location_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"This adjustment would take that location's stock negative - only {location_balance} recorded there.",
                )

        adjustment = StockAdjustment(
            material_id=data.material_id, adjustment_type=data.adjustment_type,
            related_issue_id=data.related_issue_id,
            quantity_delta=data.quantity_delta, stock_before=stock_before, stock_after=stock_after,
            reason=data.reason, adjusted_by=data.adjusted_by, business_id=generate_business_id(db),
            location_id=data.location_id,
        )
        db.add(adjustment)
        db.flush()  # assigns adjustment.id without committing, needed as the ledger entry's reference_id below

        material.current_stock = stock_after
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Adjustment", quantity_delta=data.quantity_delta,
            balance_after=stock_after, reference_type="stock_adjustment", reference_id=adjustment.id,
            remarks=data.reason, location_id=resolved_location_id,
        ))
        db.add(material)

        db.commit()
        db.refresh(adjustment)
        return adjustment

    @staticmethod
    def verify_stock_matches_ledger(db: Session, material_id: int) -> dict:
        """Proves (or disproves) that Material.current_stock genuinely
        equals opening_stock + every ledger entry ever recorded for
        this material - the actual verification the "ledger is the
        source of truth" requirement depends on, not just a claim that
        a ledger exists alongside current_stock. Returns a dict rather
        than raising, so this can be used both as a route response and
        directly in tests without needing to catch an exception."""
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        entries = db.query(StockLedgerEntry).filter(StockLedgerEntry.material_id == material_id).all()
        ledger_sum = sum((e.quantity_delta for e in entries), Decimal("0"))
        computed_stock = (material.opening_stock or Decimal("0")) + ledger_sum
        current_stock = material.current_stock or Decimal("0")
        return {
            "material_id": material_id, "matches": computed_stock == current_stock,
            "current_stock": current_stock, "computed_stock": computed_stock,
            "opening_stock": material.opening_stock or Decimal("0"), "ledger_entry_count": len(entries),
        }

    @staticmethod
    def _location_balance(db: Session, material_id: int, location_id: Optional[int]) -> Decimal:
        """The derived balance for one material at one location - the
        ledger entries for that (material_id, location_id) pair, summed,
        plus opening_stock if this location is where the opening stock
        was originally recorded (opening_stock predates the ledger, so
        it must count here too or a location-specific check could
        wrongly reject a valid issue/transfer/adjustment against
        genuinely available opening stock). Never a stored number;
        always computed on read - same rule get_location_balances
        follows for the full breakdown.

        Every ledger entry's location_id is a fixed fact about that row
        (see migration 0061, which backfilled legacy pre-multi-location
        rows once) - it is matched exactly here, never re-derived from
        the material's current (mutable) primary location, so a later
        change to Material.location_id can't retroactively move where
        old entries appear to belong."""
        material = db.query(Material).filter(Material.id == material_id).first()
        query = db.query(StockLedgerEntry.quantity_delta).filter(
            StockLedgerEntry.material_id == material_id, StockLedgerEntry.location_id == location_id,
        )
        balance = sum((e[0] for e in query.all()), Decimal("0"))
        opening_location_id = material.opening_stock_location_id if material else None
        if material and opening_location_id == location_id:
            balance += material.opening_stock or Decimal("0")
        return balance

    @staticmethod
    def get_location_balances(db: Session, material_id: int) -> dict:
        """The genuine per-location breakdown of a material's stock,
        derived entirely from the ledger - e.g. HDHMR 18mm: Rack A2 -> 12,
        Rack B1 -> 6, Total -> 18. Never a second, independently edited
        stock number: this is StockLedgerEntry.quantity_delta grouped by
        location_id, nothing else.

        Each entry's location_id is used exactly as stored - never
        re-derived from the material's current primary location, so a
        material being relocated later can't retroactively move where
        old stock appears to have been. Old ledger rows written before
        multi-location support existed were backfilled once, in
        migration 0061, onto whatever the material's location was at
        that time; a material that never had any location keeps
        location_id = NULL on those rows, shown as an explicit
        "Unassigned" bucket rather than a fabricated one."""
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        entries = db.query(StockLedgerEntry).filter(StockLedgerEntry.material_id == material_id).all()
        balances: dict[Optional[int], Decimal] = {}
        # opening_stock predates the ledger (it's the material's baseline,
        # not itself a ledger entry) but must still be included or the
        # location breakdown would under-count the material-wide total -
        # attributed to wherever it was originally recorded
        # (opening_stock_location_id), not the material's current
        # primary location, for the same reason as ledger entries above.
        opening = material.opening_stock or Decimal("0")
        if opening:
            key = material.opening_stock_location_id
            balances[key] = balances.get(key, Decimal("0")) + opening
        for entry in entries:
            balances[entry.location_id] = balances.get(entry.location_id, Decimal("0")) + entry.quantity_delta

        location_ids = [loc_id for loc_id in balances.keys() if loc_id is not None]
        locations_by_id = {}
        if location_ids:
            for loc in db.query(Location).filter(Location.id.in_(location_ids)).all():
                locations_by_id[loc.id] = loc

        rows = []
        for loc_id, qty in balances.items():
            if qty == 0:
                continue  # a location that's been fully drawn down/transferred out has nothing to show
            loc = locations_by_id.get(loc_id) if loc_id else None
            rows.append({
                "location_id": loc_id,
                "location_name": loc.full_path if loc else "Unassigned",
                "quantity": qty,
            })
        rows.sort(key=lambda r: r["location_name"])

        return {
            "material_id": material.id, "material_name": material.name, "unit": material.unit,
            "total": material.current_stock or Decimal("0"), "locations": rows,
        }

    @staticmethod
    def calculate_reserved_stock(db: Session, material_ids: list, exclude_order_id: int = None) -> dict:
        """Reserved Qty (spec section 9.2/5.4): unfulfilled BOM demand
        for the given materials across every still-open order
        (project_status not in "Completed"/"Cancelled" - the two
        terminal states where a material's demand no longer counts
        against future planning). "Unfulfilled" means the order's own
        BOM requirement for that material, minus whatever has already
        actually been issued against that same order+material pair -
        an order that's already had its materials issued no longer
        reserves anything further for them.

        Computed fresh every call, not a stored column - this can
        never silently drift out of sync the way a stored reservation
        record could (nothing to release on order cancellation/
        completion; the exclusion above already handles that).

        exclude_order_id: when checking "how much of this material is
        reserved by OTHER orders" for a specific order's own shortage
        calculation, that order's own demand must not double-count
        against itself.

        Returns {material_id: reserved_quantity}; a material with no
        open-order demand is simply absent from the dict (treat a
        missing key as zero).
        """
        if not material_ids:
            return {}

        orders_query = db.query(Order.id).filter(Order.project_status.notin_(["Completed", "Cancelled"]))
        if exclude_order_id is not None:
            orders_query = orders_query.filter(Order.id != exclude_order_id)
        open_order_ids = [row[0] for row in orders_query.all()]
        if not open_order_ids:
            return {}

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id.in_(open_order_ids), OrderItem.product_id.isnot(None))
            .all()
        )
        product_ids = list({item.product_id for item in items})
        if not product_ids:
            return {}

        bom_rows = (
            db.query(ProductMaterial)
            .filter(ProductMaterial.product_id.in_(product_ids), ProductMaterial.material_id.in_(material_ids))
            .all()
        )
        bom_by_product: dict = {}
        for row in bom_rows:
            bom_by_product.setdefault(row.product_id, []).append(row)
        if not bom_by_product:
            return {}

        required_by_order_material: dict = {}
        for item in items:
            for bom_line in bom_by_product.get(item.product_id, []):
                key = (item.order_id, bom_line.material_id)
                needed = Decimal(str(item.quantity)) * bom_line.quantity_required
                required_by_order_material[key] = required_by_order_material.get(key, Decimal("0")) + needed

        issued_rows = (
            db.query(Issue.order_id, Issue.material_id, Issue.quantity_issued)
            .filter(Issue.order_id.in_(open_order_ids), Issue.material_id.in_(material_ids))
            .all()
        )
        issued_by_order_material: dict = {}
        for order_id, material_id, quantity_issued in issued_rows:
            key = (order_id, material_id)
            issued_by_order_material[key] = issued_by_order_material.get(key, Decimal("0")) + quantity_issued

        reserved_by_material: dict = {}
        for (order_id, material_id), required in required_by_order_material.items():
            issued = issued_by_order_material.get((order_id, material_id), Decimal("0"))
            unfulfilled = max(Decimal("0"), required - issued)
            if unfulfilled > 0:
                reserved_by_material[material_id] = reserved_by_material.get(material_id, Decimal("0")) + unfulfilled

        return reserved_by_material

    @staticmethod
    def calculate_order_material_requirements(db: Session, order_id: int) -> dict:
        """Material Requirement + Shortage Intelligence (Phase B, section
        9.3): for every ordered Product with a BOM (ProductMaterial),
        multiply quantity_required by the ordered quantity to get real
        material demand, then compare against current_stock and any
        purchase already placed but not yet received (Purchase rows
        with receipt_status != "Received" for the same material).

        Formula per spec: Shortage = max(0, Required - Available -
        Relevant Pending Supply), where Available = Current Stock -
        Reserved Qty (this order excluded from the reservation count -
        see calculate_reserved_stock). Worked example: 5 sheets
        required, 2 available, 1 already-pending purchase -> shortage
        2 (not 3; the pending purchase is netted directly into the
        shortage figure, not applied as a separate later adjustment).
        gap_before_pending_supply (required - available, before netting
        pending) is kept alongside it purely for explanation/
        traceability, not as the number to act on.

        Every number here traces to a real row - no estimate, no
        forecast. Reserved Qty is computed fresh from every other open
        order's own unfulfilled BOM demand (see
        calculate_reserved_stock), not a stored field - matching the
        client reference's Reserved Qty/Available Qty concept (see
        docs/ARCHITECTURE.md) without the drift risk of a stored
        reservation record.
        """
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order_id, OrderItem.product_id.isnot(None))
            .all()
        )
        product_ids = list({item.product_id for item in items})
        if not product_ids:
            return {"order_id": order_id, "materials": []}

        bom_rows = db.query(ProductMaterial).filter(ProductMaterial.product_id.in_(product_ids)).all()
        bom_by_product = {}
        for row in bom_rows:
            bom_by_product.setdefault(row.product_id, []).append(row)

        required_by_material: dict = {}
        for item in items:
            for bom_line in bom_by_product.get(item.product_id, []):
                needed = Decimal(str(item.quantity)) * bom_line.quantity_required
                required_by_material[bom_line.material_id] = (
                    required_by_material.get(bom_line.material_id, Decimal("0")) + needed
                )

        if not required_by_material:
            return {"order_id": order_id, "materials": []}

        material_ids = list(required_by_material.keys())
        materials_by_id = {m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()}

        pending_purchases = (
            db.query(Purchase)
            .filter(Purchase.material_id.in_(material_ids), Purchase.receipt_status != "Received")
            .all()
        )
        pending_by_material: dict = {}
        for p in pending_purchases:
            pending_by_material[p.material_id] = pending_by_material.get(p.material_id, Decimal("0")) + p.quantity

        # What OTHER open orders have already claimed against this same
        # stock - this order's own demand must not double-count against
        # itself, hence exclude_order_id.
        reserved_by_material = StockService.calculate_reserved_stock(db, material_ids, exclude_order_id=order_id)

        results = []
        for material_id, required in required_by_material.items():
            material = materials_by_id.get(material_id)
            if not material:
                continue
            reserved_by_others = reserved_by_material.get(material_id, Decimal("0"))
            available = max(Decimal("0"), (material.current_stock or Decimal("0")) - reserved_by_others)
            pending = pending_by_material.get(material_id, Decimal("0"))
            # Formula per spec section 9.3: Shortage = max(0, Required -
            # Available - Relevant Pending Supply). "Relevant" here means
            # already scoped to this exact material_id (not a blind
            # subtraction across unrelated purchases) and to receipt_status
            # != "Received" (an already-received purchase is already
            # inside current_stock, not still "pending").
            shortage = max(Decimal("0"), required - available - pending)
            # Kept for traceability/explanation (spec: "explain
            # recommendation inputs") - the raw gap before pending supply
            # is netted in, so a user can see *why* the shortage is lower
            # than a naive required-minus-available would suggest.
            gap_before_pending = max(Decimal("0"), required - available)
            results.append({
                "material_id": material.id, "material_name": material.name, "unit": material.unit,
                "required": required, "available": available,
                "reserved_by_other_orders": reserved_by_others,
                "gap_before_pending_supply": gap_before_pending,
                "pending_purchase_quantity": pending,
                "shortage": shortage,
                "recommended_purchase_quantity": shortage,
            })
        results.sort(key=lambda r: r["shortage"], reverse=True)

        shortage_material_ids = [r["material_id"] for r in results if r["shortage"] > 0]
        from app.modules.procurement.services import ProcurementService
        supplier_options = ProcurementService._supplier_options_for_materials(db, shortage_material_ids)
        for row in results:
            row["supplier_options"] = supplier_options.get(row["material_id"], [])

        return {"order_id": order_id, "materials": results}

    @staticmethod
    def calculate_at_risk_orders(db: Session, limit: Optional[int] = None) -> list:
        """Business-wide version of calculate_order_material_requirements -
        which open orders have a real, current material shortage, computed
        once across the whole open-order book rather than by looping the
        per-order function (which would be its own N+1 at this scale: ~9
        queries per order). Same formula, same semantics, same source
        data - this only changes where the reserved-by-other-orders
        subtraction comes from (derived from a business-wide total
        already in memory instead of a second per-order query); it is
        not a second, independent way of computing a shortage that
        could drift from the per-order figure used elsewhere.

        Returns one entry per at-risk order (shortage > 0 on at least
        one material), sorted so the most materially at-risk order
        (highest total shortage across its materials) is first. Each
        order's materials list uses the same field names
        calculate_order_material_requirements returns, so a dashboard
        card and the order detail page can share one frontend
        rendering path.

        Defect repair (P1-6): `limit` is optional and defaults to None,
        so every existing caller that needs the true, complete at-risk
        set (the alerts/automation job, the operations at-risk flag
        lookup) is unaffected. Only the dashboard widget - which has
        never rendered more than its top 4 - passes a limit, so the
        per-material supplier-options enrichment below (a real query)
        and the final per-order result assembly only run for the
        orders that will actually be shown, instead of for the whole
        open-order book on every dashboard load. The shortage
        calculation itself (which requires seeing every open order to
        even know which ones are at risk and how to rank them) still
        runs in full either way - that part was already bulk/N+1-free
        and cannot be shortcut without changing which orders qualify.
        """
        open_orders = (
            db.query(Order)
            .options(selectinload(Order.client))
            .filter(Order.project_status.notin_(["Completed", "Cancelled"]))
            .all()
        )
        if not open_orders:
            return []
        orders_by_id = {o.id: o for o in open_orders}
        open_order_ids = list(orders_by_id.keys())

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id.in_(open_order_ids), OrderItem.product_id.isnot(None))
            .all()
        )
        product_ids = list({item.product_id for item in items})
        if not product_ids:
            return []

        bom_rows = db.query(ProductMaterial).filter(ProductMaterial.product_id.in_(product_ids)).all()
        bom_by_product: dict = {}
        for row in bom_rows:
            bom_by_product.setdefault(row.product_id, []).append(row)
        if not bom_by_product:
            return []

        # required(order, material) - identical multiplication the
        # per-order function uses, just keyed by order this time
        # instead of scoped to a single order.
        required_by_order_material: dict = {}
        for item in items:
            for bom_line in bom_by_product.get(item.product_id, []):
                key = (item.order_id, bom_line.material_id)
                needed = Decimal(str(item.quantity)) * bom_line.quantity_required
                required_by_order_material[key] = required_by_order_material.get(key, Decimal("0")) + needed
        if not required_by_order_material:
            return []

        material_ids = list({key[1] for key in required_by_order_material})

        issued_rows = (
            db.query(Issue.order_id, Issue.material_id, Issue.quantity_issued)
            .filter(Issue.order_id.in_(open_order_ids), Issue.material_id.in_(material_ids))
            .all()
        )
        issued_by_order_material: dict = {}
        for order_id, material_id, quantity_issued in issued_rows:
            key = (order_id, material_id)
            issued_by_order_material[key] = issued_by_order_material.get(key, Decimal("0")) + quantity_issued

        # unfulfilled(order, material) = max(0, required - issued) - this
        # order's own still-outstanding claim. Summing it across every
        # open order for one material, then subtracting one order's own
        # share, gives exactly what calculate_reserved_stock computes
        # per-order via a second query - derived here from rows already
        # in memory instead of queried again.
        unfulfilled_by_order_material: dict = {}
        total_unfulfilled_by_material: dict = {}
        for key, required in required_by_order_material.items():
            issued = issued_by_order_material.get(key, Decimal("0"))
            unfulfilled = max(Decimal("0"), required - issued)
            unfulfilled_by_order_material[key] = unfulfilled
            material_id = key[1]
            total_unfulfilled_by_material[material_id] = (
                total_unfulfilled_by_material.get(material_id, Decimal("0")) + unfulfilled
            )

        materials_by_id = {m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()}

        pending_purchases = (
            db.query(Purchase)
            .filter(Purchase.material_id.in_(material_ids), Purchase.receipt_status != "Received")
            .all()
        )
        pending_by_material: dict = {}
        for p in pending_purchases:
            pending_by_material[p.material_id] = pending_by_material.get(p.material_id, Decimal("0")) + p.quantity

        at_risk: dict = {}
        for (order_id, material_id), required in required_by_order_material.items():
            material = materials_by_id.get(material_id)
            if not material:
                continue
            this_order_unfulfilled = unfulfilled_by_order_material.get((order_id, material_id), Decimal("0"))
            reserved_by_others = total_unfulfilled_by_material.get(material_id, Decimal("0")) - this_order_unfulfilled
            available = max(Decimal("0"), (material.current_stock or Decimal("0")) - reserved_by_others)
            pending = pending_by_material.get(material_id, Decimal("0"))
            shortage = max(Decimal("0"), required - available - pending)
            if shortage <= 0:
                continue
            at_risk.setdefault(order_id, []).append({
                "material_id": material.id, "material_name": material.name, "unit": material.unit,
                "required": required, "available": available,
                "shortage": shortage, "recommended_purchase_quantity": shortage,
            })

        # Rank every at-risk order by its total shortage before doing
        # any further per-order enrichment - this in-memory sort costs
        # nothing extra (no query) and is required to know which
        # orders are the top N regardless of whether limit is used.
        ranked_order_ids = sorted(
            at_risk.keys(),
            key=lambda oid: sum(m["shortage"] for m in at_risk[oid]),
            reverse=True,
        )
        order_ids_to_build = ranked_order_ids[:limit] if limit is not None else ranked_order_ids

        all_shortage_material_ids = list({
            m["material_id"] for oid in order_ids_to_build for m in at_risk[oid]
        })
        from app.modules.procurement.services import ProcurementService
        supplier_options = ProcurementService._supplier_options_for_materials(db, all_shortage_material_ids)

        results = []
        for order_id in order_ids_to_build:
            materials = at_risk[order_id]
            order = orders_by_id[order_id]
            for m in materials:
                m["supplier_options"] = supplier_options.get(m["material_id"], [])
            materials.sort(key=lambda m: m["shortage"], reverse=True)
            results.append({
                "order_id": order.id, "order_code": order.order_code,
                "client_name": order.client.name if order.client else None,
                "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                "project_status": order.project_status,
                "total_shortage_lines": len(materials),
                "materials": materials,
            })
        # order_ids_to_build is already ranked highest-shortage-first,
        # so results is already in the same order the old unconditional
        # results.sort(...) produced - no re-sort needed.
        return results
