import pytest
from app.core.db import SessionLocal, engine, Base
from app.models import Material, Purchase, Issue
from app.models_extra import StockMovement
from app.services.stock_service import StockService
from datetime import date

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_add_purchase_updates_stock(db):
    m = Material(material_id="MAT-TEST-1", name="Test Mat", unit="Nos", opening_stock=10, current_stock=10, minimum_stock=5, unit_cost=100)
    db.add(m); db.commit(); db.refresh(m)
    purchase = Purchase(purchase_no="PUR-TEST-1", date=date.today(), supplier_id=None, material_id=m.id, quantity=5, unit="Nos", rate=100, taxable_value=500, gst_percent=0, gst_amount=0, invoice_total=500, payment_status="Paid")
    svc = StockService(db)
    svc.add_purchase(purchase)
    db.refresh(m)
    assert m.current_stock == 15

def test_record_issue_blocks_if_insufficient(db):
    m = db.query(Material).filter(Material.material_id=="MAT-TEST-1").first()
    svc = StockService(db)
    issue = Issue(issue_no="ISS-TEST-1", date=date.today(), material_id=m.id, quantity_issued=20, unit="Nos")
    with pytest.raises(Exception):
        svc.record_issue(issue, allow_negative=False)
