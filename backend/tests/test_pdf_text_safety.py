"""Tests for the PDF text-escaping fix (Section 22) - user-controlled
text (remarks, client names, bank names) interpolated into reportlab
Paragraph markup must not break rendering or let a user inject fake
formatting tags into a generated document."""
from app.utils.document_style import pdf_text


def test_escapes_ampersand_and_angle_brackets():
    assert pdf_text("Sharma & Sons") == "Sharma &amp; Sons"
    assert pdf_text("<b>fake bold</b>") == "&lt;b&gt;fake bold&lt;/b&gt;"


def test_none_becomes_empty_string():
    assert pdf_text(None) == ""


def test_plain_text_unaffected():
    assert pdf_text("Siddharth Residence") == "Siddharth Residence"


def test_non_string_values_are_stringified():
    assert pdf_text(42) == "42"


def test_order_pdf_generates_with_malicious_remarks(client, test_user):
    """The real, end-to-end guarantee - a remarks field crafted to
    break XML parsing must not crash PDF generation."""
    resp_login = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp_login.status_code == 200

    client_id = client.post("/api/clients/", json={"name": "PDF Safety Client", "phone": "9000010170"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "10000", "advance": "0",
        "remarks": '<b onclick="evil()">Fake &injected tag</b> & unescaped <ampersand',
    }).json()

    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000
