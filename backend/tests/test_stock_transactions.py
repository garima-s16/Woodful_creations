"""Exercises StockService against the live Purchase/Issue flow, using the
shared db_session fixture from conftest.py (in-memory SQLite, same engine
the FastAPI app itself uses in tests) rather than a standalone engine.
"""
import pytest
from datetime import datetime

from app.models.material import Material
from app.models.supplier import Supplier
from app.services.stock_service import StockService
from app.schemas.purchase import PurchaseCreate
from app.schemas.issue import IssueCreate


@pytest.fixture
def material(db_session):
    m = Material(
        material_code="MAT-TEST-1", name="Test Mat", unit="Nos",
        opening_stock=10, current_stock=10, minimum_stock=5, average_rate=100,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def supplier(db_session):
    s = Supplier(supplier_code="SUP-TEST-1", name="Test Supplier")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def test_add_purchase_updates_stock(db_session, material, supplier):
    data = PurchaseCreate(
        date=datetime.utcnow(), supplier_id=supplier.id, material_id=material.id,
        quantity=5, unit="Nos", rate=100, gst_percent=0,
    )
    StockService.record_purchase(db_session, data)
    db_session.refresh(material)
    assert material.current_stock == 15


def test_record_issue_blocks_if_insufficient(db_session, material):
    data = IssueCreate(
        date=datetime.utcnow(), material_id=material.id,
        quantity_issued=20, unit="Nos",
    )
    with pytest.raises(Exception):
        StockService.record_issue(db_session, data)
