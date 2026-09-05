"""Interprets a free-typed material name (e.g. "HDHMR 6mm") into a
thickness/specification and a suggested Category/Subcategory - the
shared logic behind both the chatbot's existing material-creation
proposal (chat_inventory._route_material_action) and the material
creation form's "intelligent defaults".

Category/Subcategory names are entirely user-defined (Category ->
Subcategory -> Material, never hard-coded per the product's own
principle - see MaterialCategory/MaterialSubcategory docstrings), so
this can never hard-code "HDHMR means Board & Wood Materials". Instead
it matches the typed name against subcategories and materials the
business has ALREADY created - the same "search across name and
thickness_size" approach the chatbot already uses elsewhere
(_route_material_action, _route_ambiguous_hindi_add) - and only
returns a suggestion when it's actually confident, never a guess
dressed up as a fact.
"""
import re
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.modules.inventory.models import Material, MaterialSubcategory

# Matches "6mm", "18 mm", "12.5mm" - the same thickness pattern the
# chatbot's own material-creation proposal already extracts with
# (chat_service._route_material_action). Kept here as the single
# definition so both call sites can never drift apart.
THICKNESS_RE = re.compile(r"(\d+(?:\.\d+)?\s*mm)", re.IGNORECASE)

_STOPWORDS = {"the", "a", "an", "of", "for", "sheet", "sheets", "board", "boards"}


def extract_thickness(name: str) -> Optional[str]:
    """"HDHMR 6mm" -> "6mm". None if no thickness-like token is present -
    never invented from an unrelated number."""
    match = THICKNESS_RE.search(name or "")
    return match.group(1).replace(" ", "") if match else None


def _base_tokens(name: str) -> list:
    """The name with any thickness token and units/stopwords stripped,
    e.g. "HDHMR 6mm Sheet" -> ["hdhmr"] - what's left is the part that
    actually identifies the material type, used to match against
    existing subcategories/materials."""
    without_thickness = THICKNESS_RE.sub("", name or "")
    words = re.findall(r"[A-Za-z]+", without_thickness.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


def interpret_material_name(db: Session, name: str) -> dict:
    """Returns a suggestion dict:
        {
          "thickness_size": "6mm" | None,
          "category_id": int | None, "category_name": str | None,
          "subcategory_id": int | None, "subcategory_name": str | None,
          "confidence": "high" | "medium" | "none",
          "matched_on": str,  # human-readable explanation, for transparency
        }
    Never raises, never invents a category that doesn't already exist.
    The caller (route/chatbot) decides whether "none" confidence means
    showing no suggestion at all - this function's job is only to say
    how sure it is, not to force a value into the form.
    """
    thickness = extract_thickness(name)
    tokens = _base_tokens(name)

    result = {
        "thickness_size": thickness,
        "category_id": None, "category_name": None,
        "subcategory_id": None, "subcategory_name": None,
        "confidence": "none", "matched_on": "",
    }
    if not tokens:
        return result

    # 1) HIGH confidence: an existing Subcategory's own name appears in
    # (or contains) what was typed - e.g. typing "HDHMR 6mm" when a
    # "HDHMR" subcategory already exists under some category.
    subcategories = db.query(MaterialSubcategory).all()
    best_subcategory = None
    best_len = 0
    lowered_name = (name or "").lower()
    for sub in subcategories:
        sub_lower = sub.name.lower()
        if sub_lower in lowered_name or any(sub_lower == t for t in tokens):
            if len(sub_lower) > best_len:
                best_subcategory = sub
                best_len = len(sub_lower)
    if best_subcategory:
        result.update({
            "category_id": best_subcategory.category_id,
            "category_name": best_subcategory.category.name if best_subcategory.category else None,
            "subcategory_id": best_subcategory.id, "subcategory_name": best_subcategory.name,
            "confidence": "high",
            "matched_on": f"matches existing subcategory \"{best_subcategory.name}\"",
        })
        return result

    # 2) MEDIUM confidence: an existing Material whose own name shares a
    # significant word already has a subcategory/category assigned -
    # e.g. "HDHMR 6mm" typed when "HDHMR 18mm" already exists and is
    # filed under Board & Wood Materials > HDHMR. Same word-matching
    # approach _route_material_action already uses for material search.
    query = db.query(Material).filter(Material.subcategory_id.isnot(None))
    query = query.filter(or_(*[Material.name.ilike(f"%{t}%") for t in tokens]))
    existing = query.first()
    if existing and existing.subcategory:
        result.update({
            "category_id": existing.subcategory.category_id,
            "category_name": existing.subcategory.category.name if existing.subcategory.category else None,
            "subcategory_id": existing.subcategory_id, "subcategory_name": existing.subcategory.name,
            "confidence": "medium",
            "matched_on": f"similar to existing material \"{existing.name}\"",
        })
        return result

    # Nothing to go on - explicitly "none", so the caller shows no
    # suggestion rather than a fabricated one.
    return result
