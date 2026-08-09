from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.stock_management import AppSetting, Material, StockIn, StockOut, Supplier
from app.services.stock_management import current_stock, stock_status, suggested_reorder_quantity


client = TestClient(app)


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_stock_calculation_helpers():
    reset_db()
    db = SessionLocal()
    try:
        material = Material(name="Test Ply", category="Plywood", opening_stock=10, minimum_stock=8, unit_price=100)
        db.add(material)
        db.commit()
        db.refresh(material)

        db.add_all([
            StockIn(material_id=material.id, quantity=5, unit_price=110),
            StockOut(material_id=material.id, quantity=9),
        ])
        db.commit()
        db.refresh(material)

        assert current_stock(material) == 6
        assert stock_status(0, 5) == "OUT OF STOCK"
        assert stock_status(4, 5) == "LOW STOCK"
        assert stock_status(8, 5) == "STOCK OK"
        assert suggested_reorder_quantity(4, 10, 1.2) == 8
    finally:
        db.close()


def test_dashboard_and_excel_download():
    reset_db()
    supplier = client.post('/api/stock-management/suppliers', json={"name": "ABC Supplier"})
    supplier_id = supplier.json()["id"]

    material = client.post(
        '/api/stock-management/materials',
        json={
            "name": "MDF Sheet",
            "category": "MDF",
            "unit": "sheet",
            "opening_stock": 2,
            "minimum_stock": 5,
            "unit_price": 50,
            "supplier_id": supplier_id,
        },
    )
    material_id = material.json()["id"]

    client.post('/api/stock-management/stock-in', json={"material_id": material_id, "quantity": 3, "unit_price": 50})
    client.post('/api/stock-management/stock-out', json={"material_id": material_id, "quantity": 4, "issued_to": "Workshop A"})

    dashboard = client.get('/api/stock-management/dashboard')
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["total_stock_value"] == 50
    assert payload["low_stock_items"] == 1
    assert payload["out_of_stock_items"] == 0
    assert payload["purchase_value"] == 150
    assert payload["low_stock_action_list"][0]["status"] == "LOW STOCK"

    excel = client.get('/api/stock-management/reports/stock/download')
    assert excel.status_code == 200
    assert excel.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=" in excel.headers["content-disposition"]
    assert excel.content[:2] == b"PK"
