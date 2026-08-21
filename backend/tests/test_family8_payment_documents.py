"""Tests for Family 8 (Finance & Payments): payment documents - a
genuine gap against the brief's "protect transaction documents"
security item, which implied such documents should exist. All
operations are master-only, matching payments.py's own existing
strict-authorization pattern (payments have no open-read anywhere)."""
import io


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _make_payment(client, client_id):
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    return client.post("/api/payments/", json={
        "date": "2026-08-19T00:00:00", "order_id": order["id"], "payment_type": "Advance",
        "payment_mode": "UPI", "amount": "5000",
    }).json()


def test_upload_and_download_payment_document(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Doc Test Client", "phone": "9000010121"}).json()["id"]
    payment = _make_payment(client, client_id)

    files = {"file": ("upi_screenshot.png", io.BytesIO(b"fake png bytes"), "image/png")}
    upload = client.post(f"/api/payments/{payment['id']}/documents", files=files, data={"description": "UPI proof"})
    assert upload.status_code == 201

    download = client.get(f"/api/payments/{payment['id']}/documents/{upload.json()['id']}/download")
    assert download.status_code == 200


def test_payment_document_upload_rejects_disallowed_extension(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Doc Bad Ext Client", "phone": "9000010122"}).json()["id"]
    payment = _make_payment(client, client_id)

    files = {"file": ("data.docx", io.BytesIO(b"not allowed for payments"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp = client.post(f"/api/payments/{payment['id']}/documents", files=files)
    assert resp.status_code == 400


def test_payment_document_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Doc Permission Client", "phone": "9000010123"}).json()["id"]
    payment = _make_payment(client, client_id)
    employee = client.post("/api/employees/", json={"name": "Payment Doc Permission Employee"}).json()
    user = User(
        username="paymentdocpermuser", email="paymentdocpermuser@example.com",
        full_name="Payment Doc Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "paymentdocpermuser@example.com", "password": "EmpPass1!"})

    files = {"file": ("proof.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    resp = client.post(f"/api/payments/{payment['id']}/documents", files=files)
    assert resp.status_code == 403


def test_payment_document_download_rejects_mismatched_payment_id(client, test_user):
    """The core IDOR protection - a real document_id under the WRONG
    payment_id in the URL must not be accessible."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Doc IDOR Client", "phone": "9000010124"}).json()["id"]
    payment_a = _make_payment(client, client_id)
    payment_b = _make_payment(client, client_id)
    files = {"file": ("real.pdf", io.BytesIO(b"%PDF-1.4 real content"), "application/pdf")}
    doc = client.post(f"/api/payments/{payment_a['id']}/documents", files=files).json()

    resp = client.get(f"/api/payments/{payment_b['id']}/documents/{doc['id']}/download")
    assert resp.status_code == 404


def test_payment_document_upload_logs_are_audited(client, test_user, db_session):
    from app.models.audit import AuditLog
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Doc Audit Client", "phone": "9000010125"}).json()["id"]
    payment = _make_payment(client, client_id)

    files = {"file": ("audited.pdf", io.BytesIO(b"%PDF-1.4 audited"), "application/pdf")}
    client.post(f"/api/payments/{payment['id']}/documents", files=files)

    log_entry = db_session.query(AuditLog).filter(AuditLog.action == "upload_payment_document").first()
    assert log_entry is not None
