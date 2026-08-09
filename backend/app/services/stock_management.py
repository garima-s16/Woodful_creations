from collections import defaultdict
from datetime import datetime, timezone

from app.models.stock_management import Material


def current_stock(material: Material) -> float:
    purchased = sum((row.quantity or 0) for row in material.stock_ins)
    issued = sum((row.quantity or 0) for row in material.stock_outs)
    return round((material.opening_stock or 0) + purchased - issued, 2)


def stock_status(current: float, minimum: float) -> str:
    if current <= 0:
        return "OUT OF STOCK"
    if current <= minimum:
        return "LOW STOCK"
    return "STOCK OK"


def suggested_reorder_quantity(current: float, minimum: float, reorder_buffer: float = 1.2) -> float:
    if current > minimum:
        return 0.0
    target = max(minimum * reorder_buffer, minimum)
    return round(max(target - current, 1), 2)


def material_to_view(material: Material, reorder_buffer: float = 1.2) -> dict:
    curr = current_stock(material)
    status = stock_status(curr, material.minimum_stock or 0)
    return {
        "id": material.id,
        "name": material.name,
        "category": material.category,
        "unit": material.unit,
        "opening_stock": material.opening_stock,
        "minimum_stock": material.minimum_stock,
        "unit_price": material.unit_price,
        "supplier_id": material.supplier_id,
        "current_stock": curr,
        "status": status,
        "suggested_reorder_quantity": suggested_reorder_quantity(curr, material.minimum_stock or 0, reorder_buffer),
    }


def dashboard_data(materials: list[Material], reorder_buffer: float = 1.2) -> dict:
    material_views = [material_to_view(m, reorder_buffer) for m in materials]

    total_stock_value = round(sum(item["current_stock"] * (item["unit_price"] or 0) for item in material_views), 2)
    low_stock_items = [item for item in material_views if item["status"] == "LOW STOCK"]
    out_of_stock_items = [item for item in material_views if item["status"] == "OUT OF STOCK"]

    purchase_value = 0.0
    category_map: dict[str, dict] = defaultdict(lambda: {"category": "", "item_count": 0, "stock_quantity": 0.0, "stock_value": 0.0})
    for material, view in zip(materials, material_views):
        purchase_value += sum((row.quantity or 0) * (row.unit_price if row.unit_price is not None else (material.unit_price or 0)) for row in material.stock_ins)

        bucket = category_map[view["category"]]
        bucket["category"] = view["category"]
        bucket["item_count"] += 1
        bucket["stock_quantity"] = round(bucket["stock_quantity"] + view["current_stock"], 2)
        bucket["stock_value"] = round(bucket["stock_value"] + (view["current_stock"] * (view["unit_price"] or 0)), 2)

    return {
        "total_stock_value": total_stock_value,
        "low_stock_items": len(low_stock_items),
        "out_of_stock_items": len(out_of_stock_items),
        "purchase_value": round(purchase_value, 2),
        "category_summary": sorted(category_map.values(), key=lambda x: x["category"]),
        "low_stock_action_list": [
            {
                "material": item["name"],
                "current_stock": item["current_stock"],
                "minimum_stock": item["minimum_stock"],
                "status": item["status"],
                "suggested_reorder_quantity": item["suggested_reorder_quantity"],
            }
            for item in material_views
            if item["status"] in {"LOW STOCK", "OUT OF STOCK"}
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
