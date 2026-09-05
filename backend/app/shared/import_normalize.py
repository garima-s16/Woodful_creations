"""Shared normalization helpers for the Excel import modules.

Consolidates logic that was genuinely, byte-for-byte duplicated across
5-6 separate app/utils/*_import.py files (confirmed identical before
consolidating, not assumed) - normalize_match_key (used by purchase/
order/material/product/estimate imports), normalize_number (used by
all 6, including rate_card), and normalize_date (used by purchase/
order/estimate).

client_import.py's own normalize_match_key is intentionally NOT here -
it has a different signature (combines name AND phone, since Client
Recognition requires both to match), not a duplicate of this module's
single-argument version.
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def normalize_match_key(name: Optional[str]) -> str:
    """Case/whitespace-insensitive key so "  hdhmr  18mm" and
    "HDHMR   18mm" match each other without this becoming fuzzy
    matching that could pick the wrong record."""
    return re.sub(r"\s+", " ", (name or "").strip().lower())


_NUMERIC_NOISE_RE = re.compile(r"[₹$€£%,\s]")


def normalize_number(raw) -> Optional[Decimal]:
    """Real-world quantity/rate/GST% formatting -> Decimal, or None if
    nothing usable is left. None is a "couldn't parse" signal for the
    caller to report as a validation error - never a silently-defaulted
    0."""
    if raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))
    text = _NUMERIC_NOISE_RE.sub("", str(raw))
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


_DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d",
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
    "%d-%b-%Y", "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",
]
# Day-first formats are tried before month-first ones deliberately -
# this is an Indian business's purchase/order/estimate workflow, where
# "01/08/2026" means 1 August, not January 8th - so an ambiguous D/M
# vs M/D string is resolved the same way a person filling in this
# template would read it, not by guessing per-cell.


def normalize_date(raw) -> Optional[datetime]:
    """Real-world date formatting -> datetime, or None if nothing in
    _DATE_FORMATS matches. An unparseable or impossible date (e.g.
    31 Feb) is never silently accepted - None means the caller reports
    it as a validation error."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def enforce_workbook_row_limit(workbook, max_rows: int = 50000) -> None:
    """Rejects a workbook whose total row
    count (summed across every sheet) exceeds a generous but bounded
    limit, before any row-by-row parsing begins. Protects against a
    file that is small on disk (and so passes the raw upload byte-size
    limit easily) but expands to an enormous number of rows once
    parsed - .xlsx files are themselves zip archives, and highly
    repetitive spreadsheet data compresses extremely well, so file
    size alone is not a reliable signal of parsing cost. 50,000 rows
    is far beyond any realistic business import this app's own import
    templates are designed for, while still comfortably covering
    genuine bulk imports."""
    total_rows = sum(ws.max_row or 0 for ws in workbook.worksheets)
    if total_rows > max_rows:
        raise ValueError(
            f"This file has {total_rows:,} rows, which is more than the {max_rows:,} row limit "
            f"for a single import. Please split it into smaller files."
        )

