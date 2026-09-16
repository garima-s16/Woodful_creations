"""Tests for the generic, polymorphic document system covering
order/supplier/purchase/employee documents, and the chatbot's
permission-checked document lookup. Also covers payment documents
specifically - a genuine gap against "protect transaction documents"
that implied such documents should exist. All payment-document
operations are master-only, matching payments.py's own existing
strict-authorization pattern (payments have no open-read anywhere)."""
import io
from tests.helpers import _login


def test_upload_and_download_order_document(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Doc Test Client", "phone": "9000010080"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "5000", "advance": "0",
    }).json()

    files = {"file": ("site_photo.jpg", io.BytesIO(b"fake jpg bytes"), "image/jpeg")}
    upload = client.post(f"/api/documents/order/{order['id']}", files=files, data={"description": "Site photo"})
    assert upload.status_code == 201

    download = client.get(f"/api/documents/order/{order['id']}/{upload.json()['id']}/download")
    assert download.status_code == 200


def test_invalid_parent_type_rejected(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/documents/not-a-real-type/1")
    assert resp.status_code == 400


def test_order_documents_are_open_read(client, test_user, db_session):
    """order is not in SENSITIVE_PARENT_TYPES - a non-master employee
    should be able to list order documents."""
    from app.platform.security import hash_password
    from app.modules.auth.auth import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Doc Open Read Client", "phone": "9000010081"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "3000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Order Doc Open Read Employee"}).json()
    user = User(
        username="orderdocopenreaduser", email="orderdocopenreaduser@example.com",
        full_name="Order Doc Open Read User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "orderdocopenreaduser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/documents/order/{order['id']}")
    assert resp.status_code == 200


def test_employee_documents_require_master_to_read(client, test_user, db_session):
    """employee IS in SENSITIVE_PARENT_TYPES - a non-master employee
    must be blocked from even listing employee documents."""
    from app.platform.security import hash_password
    from app.modules.auth.auth import User
    _login(client, test_user)
    target_employee = client.post("/api/employees/", json={"name": "Employee Doc Sensitive Target"}).json()
    other_employee = client.post("/api/employees/", json={"name": "Employee Doc Sensitive Other"}).json()
    user = User(
        username="empdocsensitiveuser", email="empdocsensitiveuser@example.com",
        full_name="Emp Doc Sensitive User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=other_employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "empdocsensitiveuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/documents/employee/{target_employee['id']}")
    assert resp.status_code == 403


def test_upload_requires_master_regardless_of_parent_type(client, test_user, db_session):
    from app.platform.security import hash_password
    from app.modules.auth.auth import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Upload Perm Client", "phone": "9000010082"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "1000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Upload Perm Employee"}).json()
    user = User(
        username="uploadpermuser", email="uploadpermuser@example.com",
        full_name="Upload Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "uploadpermuser@example.com", "password": "EmpPass1!"})

    files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    resp = client.post(f"/api/documents/order/{order['id']}", files=files)
    assert resp.status_code == 403


def test_download_rejects_mismatched_parent_id(client, test_user):
    """The core IDOR protection - a real document_id under the WRONG
    parent_id in the URL must not be accessible."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "IDOR Doc Client", "phone": "9000010083"}).json()["id"]
    order_a = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "1000", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "2000", "advance": "0",
    }).json()
    files = {"file": ("real.pdf", io.BytesIO(b"%PDF-1.4 real"), "application/pdf")}
    doc = client.post(f"/api/documents/order/{order_a['id']}", files=files).json()

    resp = client.get(f"/api/documents/order/{order_b['id']}/{doc['id']}/download")
    assert resp.status_code == 404


def test_upload_rejects_nonexistent_parent(client, test_user):
    _login(client, test_user)
    files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    resp = client.post("/api/documents/order/999999", files=files)
    assert resp.status_code == 404


def test_chatbot_find_documents(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Mayank", "phone": "9000010084"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    files = {"file": ("drawing.pdf", io.BytesIO(b"%PDF-1.4 drawing"), "application/pdf")}
    client.post(f"/api/documents/order/{order['id']}", files=files, data={"description": "Design drawing"})

    resp = client.post("/api/chat/", json={"message": "find documents for mayank"})
    assert resp.status_code == 200
    data = resp.json()
    assert "1 document" in data["response"]
    assert any(r["label"] == "drawing.pdf" for r in data["records"])


def test_chatbot_find_documents_no_documents(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Brajwal", "phone": "9000010085"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "1000", "advance": "0",
    })
    resp = client.post("/api/chat/", json={"message": "find documents for brajwal"})
    assert resp.status_code == 200
    assert "no documents" in resp.json()["response"].lower()


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
    from app.platform.security import hash_password
    from app.modules.auth.auth import User
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
    from app.platform.audit import AuditLog
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Doc Audit Client", "phone": "9000010125"}).json()["id"]
    payment = _make_payment(client, client_id)

    files = {"file": ("audited.pdf", io.BytesIO(b"%PDF-1.4 audited"), "application/pdf")}
    client.post(f"/api/payments/{payment['id']}/documents", files=files)

    log_entry = db_session.query(AuditLog).filter(AuditLog.action == "upload_payment_document").first()
    assert log_entry is not None


# ===========================================================================
# Client documents (from the former CRM test segment)
# ===========================================================================
def test_upload_and_download_client_document(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Document Upload Test Client", "phone": "9000010106"}).json()["id"]
    files = {"file": ("contract.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")}
    upload = client.post(f"/api/clients/{client_id}/documents", files=files, data={"description": "Signed contract"})
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    download = client.get(f"/api/clients/{client_id}/documents/{doc_id}/download")
    assert download.status_code == 200


def test_document_upload_rejects_disallowed_extension(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Bad Extension Test Client", "phone": "9000010107"}).json()["id"]
    files = {"file": ("virus.exe", io.BytesIO(b"not a real exe"), "application/octet-stream")}
    resp = client.post(f"/api/clients/{client_id}/documents", files=files)
    assert resp.status_code == 400


def test_document_upload_requires_master(client, test_user, db_session):
    from app.platform.security import hash_password
    from app.modules.auth.auth import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Doc Upload Permission Client", "phone": "9000010108"}).json()["id"]
    employee = client.post("/api/employees/", json={"name": "Doc Upload Permission Employee"}).json()
    user = User(
        username="docuploadpermuser", email="docuploadpermuser@example.com",
        full_name="Doc Upload Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "docuploadpermuser@example.com", "password": "EmpPass1!"})

    files = {"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    resp = client.post(f"/api/clients/{client_id}/documents", files=files)
    assert resp.status_code == 403


def test_document_download_rejects_mismatched_client_id(client, test_user):
    """The core IDOR protection - a real document_id under the WRONG
    client_id in the URL must not be accessible."""
    _login(client, test_user)
    client_a = client.post("/api/clients/", json={"name": "IDOR Test Client A", "phone": "9000010109"}).json()["id"]
    client_b = client.post("/api/clients/", json={"name": "IDOR Test Client B", "phone": "9000010110"}).json()["id"]
    files = {"file": ("real.pdf", io.BytesIO(b"%PDF-1.4 real content"), "application/pdf")}
    doc = client.post(f"/api/clients/{client_a}/documents", files=files).json()

    resp = client.get(f"/api/clients/{client_b}/documents/{doc['id']}/download")
    assert resp.status_code == 404
