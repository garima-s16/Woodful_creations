"""Rate card import - commit-to-DB persistence chain. Previously
untested: rate-card-imports/commit had only ever been proven to
return HTTP 200, never proven to actually write a real RateCard row
to the database, or that an update genuinely follows the
create-new-version discipline (deactivate old, create new
superseding row) rather than mutating history in place. Mirrors
test_inventory_import.py's pattern - re-fetch via a separate
client.get() call, which the app's per-request session override
makes a genuine fresh-session read-back, not just trusting the
commit response body."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def _valid_row(**overrides):
    row = {
        "category": "Material", "item_name": "Rate Import Test Item", "uom": "Sheet",
        "woodful_selling_rate": "1500.00", "source_type": "MANUAL_VERIFIED", "confidence": "HIGH",
    }
    row.update(overrides)
    return row


def test_rate_card_import_commit_creates_real_persisted_rate(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row()]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["error"] is None
    rate_id = body["rate_ids"][0]

    persisted = client.get(f"/api/rate-cards/{rate_id}").json()
    assert persisted["item_name"] == "Rate Import Test Item"
    assert float(persisted["woodful_selling_rate"]) == 1500.0
    assert persisted["is_active"] is True


def test_rate_card_import_commit_update_deactivates_old_and_creates_new(client, test_user):
    """An update must never mutate the matched row's price fields in
    place - it deactivates that row and creates a new one that
    supersedes it, preserving rate history."""
    _login(client, test_user)
    first = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row(item_name="Rate Import Update Test Item")]})
    original_id = first.json()["rate_ids"][0]

    second = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row(
        item_name="Rate Import Update Test Item", woodful_selling_rate="1800.00", matched_rate_id=original_id,
    )]})
    assert second.status_code == 200
    body = second.json()
    assert body["updated"] == 1
    new_id = body["rate_ids"][0]
    assert new_id != original_id

    old_persisted = client.get(f"/api/rate-cards/{original_id}").json()
    assert old_persisted["is_active"] is False
    assert float(old_persisted["woodful_selling_rate"]) == 1500.0  # history preserved, not mutated

    new_persisted = client.get(f"/api/rate-cards/{new_id}").json()
    assert new_persisted["is_active"] is True
    assert float(new_persisted["woodful_selling_rate"]) == 1800.0
    assert new_persisted["supersedes_id"] == original_id


def test_rate_card_import_commit_requires_master(client, db_session):
    employee = User(
        username="rateimportuser", email="rateimportuser@example.com", full_name="Rate Import User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "rateimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row()]})
    assert resp.status_code == 403
