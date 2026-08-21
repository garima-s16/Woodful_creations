"""Tests for Family 10 (Document & File Management): the generic,
polymorphic document system covering order/supplier/purchase/employee
documents, and the chatbot's permission-checked document lookup."""
import io


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


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
    from app.core.security import hash_password
    from app.models.user import User
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
    from app.core.security import hash_password
    from app.models.user import User
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
    from app.core.security import hash_password
    from app.models.user import User
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
