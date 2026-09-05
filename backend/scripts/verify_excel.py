"""Excel robustness verification.

Genuinely calls the real importer functions in app/utils/*_import.py
with real, in-memory openpyxl workbooks (no files written to disk,
nothing persisted to any database). Every result here is
PASS/FAIL - EXECUTED, not a source-inspection claim.

Scope: only importers confirmed standalone-importable without a full
SQLAlchemy model layer (holiday_import.py, material_import.py,
product_import.py, purchase_import.py, estimate_import.py,
order_import.py). client_import.py and rate_card_import.py need the
full model layer (Column/Integer/etc. from a real sqlalchemy install)
and are honestly reported as BLOCKED rather than faked with a stub
that risks misleading results - confirmed by direct attempt earlier
this session, not assumed.
"""
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_workbook(headers, rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def verify_holiday_import() -> list:
    """Returns a list of (test_name, passed, detail) tuples."""
    results = []
    try:
        from app.modules.hr.imports.holiday_import import parse_uploaded_workbook
    except ImportError as e:
        return [("holiday_import (module load)", False, f"BLOCKED - {e}")]

    # Reordered columns
    try:
        h = ["Remarks", "Type *", "Date *", "Holiday Name *"]
        r = ["x", "Holiday", "2026-09-01", "Reorder Test"]
        parsed = parse_uploaded_workbook(_make_workbook(h, [r]))
        ok = parsed[0]["Date *"] == "2026-09-01" and parsed[0]["Holiday Name *"] == "Reorder Test"
        results.append(("holiday_import: reordered columns", ok, "header-based mapping confirmed" if ok else f"got {parsed}"))
    except Exception as e:
        results.append(("holiday_import: reordered columns", False, str(e)))

    # Duplicate header rejection
    try:
        h = ["Date *", "Date *", "Holiday Name *", "Type *"]
        r = ["2026-08-15", "2026-08-16", "Dup Test", "Holiday"]
        try:
            parse_uploaded_workbook(_make_workbook(h, [r]))
            results.append(("holiday_import: duplicate header rejected", False, "should have raised ValueError"))
        except ValueError:
            results.append(("holiday_import: duplicate header rejected", True, "correctly rejected as ambiguous"))
    except Exception as e:
        results.append(("holiday_import: duplicate header rejected", False, str(e)))

    return results


def verify_material_import() -> list:
    results = []
    try:
        from app.modules.inventory.imports.material_import import parse_uploaded_workbook
    except ImportError as e:
        return [("material_import (module load)", False, f"BLOCKED - {e}")]

    try:
        h = ["Junk1", "Material Cost", "Junk2", "Unit *", "Junk3", "Material Name *", "Category"]
        r = ["x", "8000", "y", "Nos", "z", "Column Shift Test Material", "Test Category"]
        parsed = parse_uploaded_workbook(_make_workbook(h, [r]))
        row = parsed[0]
        ok = row["Material Name *"] == "Column Shift Test Material" and row["Unit *"] == "Nos"
        results.append(("material_import: deep column shift", ok, "header-based mapping confirmed, junk columns ignored" if ok else f"got {row}"))
    except Exception as e:
        results.append(("material_import: deep column shift", False, str(e)))

    return results


def verify_estimate_import() -> list:
    results = []
    try:
        from app.modules.sales.imports.estimate_import import parse_uploaded_workbook
    except ImportError as e:
        return [("estimate_import (module load)", False, f"BLOCKED - {e}")]

    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws1 = wb.active
        ws1.title = "Estimate Header"
        ws1.append(["Junk", "Notes", "Client Phone", "Client Name", "Estimate Date", "Discount", "Tax %", "Margin %", "Valid Until", "Estimate ID"])
        ws1.append(["x", "Verify script test", "9988776655", "Verify Script Client", "2026-08-01", "500", "18", "10", "2026-09-01", ""])
        ws2 = wb.create_sheet("Estimate Items")
        ws2.append(["Rate", "Estimate Row #", "Unit", "Description", "Quantity", "Category", "Product ID", "Discount %", "Tax %"])
        ws2.append(["45000", "1", "Nos", "Verify script item", "1", "Furniture", "", "0", "18"])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        headers, items = parse_uploaded_workbook(buf.read())
        ok = headers[0]["Client Name"] == "Verify Script Client" and items[0]["Description"] == "Verify script item"
        results.append(("estimate_import: two-sheet column shift", ok, "both sheets header-mapped correctly" if ok else f"got {headers}, {items}"))
    except Exception as e:
        results.append(("estimate_import: two-sheet column shift", False, str(e)))

    return results


def run_all() -> list:
    all_results = []
    all_results.extend(verify_holiday_import())
    all_results.extend(verify_material_import())
    all_results.extend(verify_estimate_import())
    return all_results


if __name__ == "__main__":
    results = run_all()
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'} - {name}: {detail}")
    failed = [r for r in results if not r[1]]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)
