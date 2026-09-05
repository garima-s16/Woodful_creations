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

from app.modules.inventory.models import Material, Purchase, Supplier
from app.modules.operations.models import Issue
from app.modules.ai.schemas import ProposedAction
from app.modules.inventory.imports.material_interpreter import extract_thickness, interpret_material_name

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

    issues = db.query(Issue).filter(Issue.material_id == material.id).order_by(Issue.date.desc()).all()
    if not issues:
        return f"{material.name} has never been issued.", [], []

    by_order = {}
    for i in issues:
        key = i.order.order_code if i.order else "No project"
        by_order[key] = by_order.get(key, 0) + float(i.quantity_issued)
    top_orders = sorted(by_order.items(), key=lambda kv: kv[1], reverse=True)[:3]
    top_summary = ", ".join(f"{code}: {qty:g} {material.unit}" for code, qty in top_orders)

    lines = [
        f"{material.name}: {float(material.total_issued or 0):g} {material.unit} issued in total across {len(issues)} issue(s).",
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
    purchases = db.query(Purchase).filter(Purchase.payment_status != "Paid").all()
    if not purchases:
        return "No purchases are currently pending payment to suppliers.", [], []
    records = [{
        "type": "Purchase", "label": p.purchase_code,
        "sublabel": f"{p.supplier.name if p.supplier else 'Supplier'} - {p.payment_status}",
        "path": "/purchases",
    } for p in purchases[:10]]
    return f"{len(purchases)} purchases are pending payment to suppliers.", [], records


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

    purchases = db.query(Purchase).filter(Purchase.supplier_id == supplier.id).all()
    if not purchases:
        return f"{supplier.name}: no purchases on record yet.", [], [{
            "type": "Supplier", "label": supplier.name, "sublabel": supplier.category or "",
            "path": f"/suppliers/{supplier.id}",
        }]

    with_expected = [p for p in purchases if p.expected_delivery_date]
    on_time = [p for p in with_expected if p.receipt_status == "Received"]
    lines = [f"{supplier.name}: {len(purchases)} purchase(s) on record."]
    if with_expected:
        lines.append(f"{len(on_time)}/{len(with_expected)} with a tracked delivery date were fully received.")
    if user_role in ("master",):
        total_value = sum(float(p.invoice_total or 0) for p in purchases)
        lines.append(f"Total purchase value Rs {total_value:,.2f}.")

    records = [{
        "type": "Supplier", "label": supplier.name, "sublabel": f"{len(purchases)} purchases", "path": f"/suppliers/{supplier.id}",
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
