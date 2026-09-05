"""Shared helpers used identically across every Excel import feature
(estimate/order/material/product/purchase/rate_card) - confirmed
programmatically byte-for-byte identical before being extracted here,
rather than assumed safe from matching function names alone.

Note: material/product/purchase/rate_card/holiday import each define
their own separate _normalize_header_cell/_resolve_header_row(values)
pair, deliberately NOT unified with resolve_header_row_with_aliases
below - direct inspection confirmed they use a genuinely different,
incompatible header-normalization strategy (bare-key lookup vs this
function's active "*"-marker stripping), so merging them would risk
a real behavioral regression rather than just remove a cosmetic
duplication."""
import re


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def resolve_header_row_with_aliases(values, aliases, required_cols):
    """Matches a spreadsheet header row against an alias table, active
    "*" mandatory-field marker stripping included - the template writes
    "Client Name *" as a visual cue, but the alias table only knows the
    bare column name. Returns {canonical_column_name: column_index} if
    every required column was found and no column matched twice, else
    None."""
    resolved = {}
    for idx, raw in enumerate(values):
        if raw is None:
            continue
        key = re.sub(r"\s+", " ", str(raw).strip().lower())
        key = re.sub(r"\s*\*\s*$", "", key).strip()
        canonical = aliases.get(key)
        if canonical is None:
            continue
        if canonical in resolved:
            return None
        resolved[canonical] = idx
    if all(col in resolved for col in required_cols):
        return resolved
    return None


def resolve_header_row_bare(values, aliases, required_cols):
    """Matches a spreadsheet header row against an alias table - no "*"
    marker stripping (unlike resolve_header_row_with_aliases above),
    matching material/product/purchase/rate_card import's confirmed-
    identical behavior: whitespace/case differences only, never a
    partial or fuzzy match. Returns {canonical_column_name: column_index}
    if every required column was found and no column matched twice,
    else None."""
    resolved = {}
    for idx, raw in enumerate(values):
        if raw is None:
            continue
        key = re.sub(r"\s+", " ", str(raw).strip().lower())
        canonical = aliases.get(key)
        if canonical is None:
            continue
        if canonical in resolved:
            return None
        resolved[canonical] = idx
    if all(col in resolved for col in required_cols):
        return resolved
    return None


def normalize_phone_key(phone):
    """Digits only, for matching a phone number regardless of spacing/
    dashes/country-code formatting differences between two records."""
    return re.sub(r"\D", "", phone or "")
