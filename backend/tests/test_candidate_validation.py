def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_valid_indian_mobile_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Valid Phone Candidate", "phone": "9876543210"})
    assert resp.status_code == 201
    assert resp.json()["phone"] == "9876543210"


def test_phone_not_starting_6to9_rejected(client, test_user):
    """The brief's exact recommended pattern (^[6-9][0-9]{9}$) - a
    10-digit number starting with 0-5 is not a valid Indian mobile
    number, even though it's the right length."""
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Bad Prefix Candidate", "phone": "5123456789"})
    assert resp.status_code == 422


def test_phone_wrong_length_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Short Phone Candidate", "phone": "98765"})
    assert resp.status_code == 422


def test_invalid_email_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Bad Email Candidate", "email": "not-an-email"})
    assert resp.status_code == 422


def test_experience_outside_controlled_options_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Bad Experience Candidate", "experience": "a decade or so"})
    assert resp.status_code == 422


def test_experience_valid_option_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Good Experience Candidate", "experience": "2-5 years"})
    assert resp.status_code == 201
    assert resp.json()["experience"] == "2-5 years"


def test_candidate_still_gets_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Business ID Check Candidate"})
    assert resp.status_code == 201
    assert len(resp.json()["business_id"]) == 10
